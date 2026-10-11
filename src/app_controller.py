"""
Central Application Orchestrator for the Speech-to-Text Dictation Service.
Coordinates the Keyboard Hook, Window Manager, Audio Capture, Faster-Whisper Transcriber,
Text Injector, Audio Feedback, Dynamic Island HUD, and System Tray.
Supports both Hold-to-Talk (Push-to-Talk) and Double-Tap Lock (Hands-Free Dictation).
"""

import logging
import threading
import time
from typing import Dict, Any, Optional

from .window_manager import WindowManager
from .keyboard_hook import LowLevelKeyboardHook
from .audio_capture import AudioCapture
from .transcriber import WhisperTranscriber
from .injector import TextInjector
from .audio_feedback import AudioFeedback
from .hud_overlay import DynamicIslandHUD
from .tray_app import TrayApplication

logger = logging.getLogger(__name__)


class DictationController:
    def __init__(
        self,
        config: Dict[str, Any],
        hud: DynamicIslandHUD,
        tray: TrayApplication,
        control_window: Optional[Any] = None,
    ):
        self.config = config
        self.hud = hud
        self.tray = tray
        self.control_window = control_window

        # State flags
        self.is_recording = False
        self.is_locked = False
        self._streaming_thread: Optional[threading.Thread] = None
        self._state_lock = threading.Lock()

        # Double-Tap Lock Settings
        hk_cfg = config.get("hotkey", {})
        self.double_tap_lock_enabled = hk_cfg.get("double_tap_lock_enabled", True)
        self.double_tap_threshold = float(hk_cfg.get("double_tap_threshold_ms", 350)) / 1000.0
        self.last_press_time = 0.0
        self.last_release_time = 0.0
        self._pending_release_timer: Optional[threading.Timer] = None

        # 1. Window Manager
        self.window_mgr = WindowManager()

        # 2. Text Injector
        inj_cfg = config.get("injection", {})
        self.injector = TextInjector(
            window_manager=self.window_mgr,
            method=inj_cfg.get("method", "unicode"),
            restore_target_window=inj_cfg.get("restore_target_window", True),
            char_delay_ms=inj_cfg.get("char_delay_ms", 0),
            copy_to_clipboard=inj_cfg.get("copy_to_clipboard", True),
        )

        # 3. Audio Feedback
        sound_cfg = config.get("sound_cues", {})
        self.feedback = AudioFeedback(
            enabled=sound_cfg.get("enabled", True),
            volume=sound_cfg.get("volume", 0.7),
        )

        # 4. Transcriber
        w_cfg = config.get("whisper", {})
        self.transcriber = WhisperTranscriber(
            model_size=w_cfg.get("model_size", "small"),
            device=w_cfg.get("device", "auto"),
            compute_type=w_cfg.get("compute_type", "float16"),
            language=w_cfg.get("language", None),
            initial_prompt=w_cfg.get("initial_prompt", "שלום, Hello, מדברים בעברית ובאנגלית. תמלול מדויק כולל סימני פיסוק."),
            beam_size=w_cfg.get("beam_size", 1),
            on_partial_callback=self._on_transcriber_partial,
        )

        # 5. Audio Capture
        a_cfg = config.get("audio", {})
        self.audio = AudioCapture(
            sample_rate=a_cfg.get("sample_rate", 16000),
            channels=a_cfg.get("channels", 1),
            device_index=a_cfg.get("device_index", None),
            max_duration_sec=a_cfg.get("max_recording_sec", 180),
            on_rms_update=self._on_audio_rms,
        )

        # Populate audio devices in tray and control window
        device_list = self.audio.list_input_devices()
        self.tray.update_device_list(device_list)
        if self.control_window:
            self.control_window.update_device_list(device_list)

        # 6. Low-Level Keyboard Hook
        self.hook = LowLevelKeyboardHook(
            on_press=self._on_key_press,
            on_release=self._on_key_release,
            on_any_key=self._on_key_event,
            trigger_key=hk_cfg.get("trigger_key", "AUTO_RIGHT"),
            suppress_windows_menu=hk_cfg.get("suppress_windows_menu", True),
        )

        self.streaming_interval = float(w_cfg.get("streaming_interval_sec", 0.6))

    def _on_key_event(self, vk: int, is_down: bool, is_trigger: bool):
        if is_down and self.control_window:
            vk_names = {
                0xA5: "Right Alt (VK_RMENU)",
                0xA4: "Left Alt (VK_LMENU)",
                0xA3: "Right Ctrl (VK_RCONTROL)",
                0xA2: "Left Ctrl (VK_LCONTROL)",
                0x5D: "Fn / Context Menu (VK_APPS)",
                0x5C: "Right Win (VK_RWIN)",
                0x20: "Spacebar",
                0x0D: "Enter",
            }
            desc = vk_names.get(vk, f"Key 0x{vk:02X}")
            self.control_window.sig_update_key_event.emit(desc, is_trigger)

    def start(self):
        """Starts background worker components and warms up Whisper in the background."""
        logger.info("Starting Dictation Controller...")
        self.hook.start()

        # Warm up Whisper model in a daemon thread so first push-to-talk is instantaneous
        def _warmup():
            try:
                logger.info("Warming up Whisper model...")
                self.transcriber.load_model()
                logger.info("Whisper model warmup completed.")
                if self.hud:
                    self.hud.show_welcome("🎙️ שירות הכתבה מוכן (Right Alt / Fn) | ממתין לדיבור", duration_ms=4000)
            except Exception as e:
                logger.error(f"Error during Whisper warmup: {e}")

        threading.Thread(target=_warmup, name="WhisperWarmupThread", daemon=True).start()

    def stop(self):
        """Stops all threads and releases system hooks."""
        logger.info("Stopping Dictation Controller...")
        if self._pending_release_timer:
            self._pending_release_timer.cancel()
            self._pending_release_timer = None
        with self._state_lock:
            self.is_recording = False
            self.is_locked = False
        self.hook.stop()
        if self.audio.is_recording:
            self.audio.stop_capture()

    def _on_audio_rms(self, rms: float):
        """Called from audio capture thread ~20 times a second."""
        if self.is_recording:
            self.hud.sig_update_rms.emit(rms)
        if self.control_window and self.control_window.isVisible():
            self.control_window.sig_update_audio_rms.emit(rms)

    def _on_transcriber_partial(self, partial_text: str):
        """Called when a streaming partial is produced."""
        if self.is_recording and partial_text:
            self.hud.sig_update_partial.emit(partial_text)

    def _start_recording_session(self):
        """Starts the audio capture stream and UI indicator."""
        with self._state_lock:
            if self.is_recording:
                return
            self.is_recording = True

        logger.info(">>> Starting dictation recording session.")

        # 1. Lock the active target window HWND
        self.window_mgr.lock_target_window()

        # 2. Audio start cue
        self.feedback.play_start()

        # 3. Slide down Dynamic Island HUD
        self.hud.sig_show.emit()
        self.tray.set_recording_state(True)

        # 4. Start audio stream
        try:
            self.audio.start_capture()
        except Exception as e:
            logger.error(f"Could not start audio capture: {e}")
            self.hud.sig_update_status.emit("ERR", "#EF4444")
            self.feedback.play_error()
            with self._state_lock:
                self.is_recording = False
            return

        # 5. Start streaming inference loop
        self._streaming_thread = threading.Thread(
            target=self._streaming_inference_loop,
            name="StreamingInferenceLoop",
            daemon=True,
        )
        self._streaming_thread.start()

    def _streaming_inference_loop(self):
        """Periodically samples accumulated audio and updates HUD live partial."""
        last_run = time.time()
        while self.is_recording:
            time.sleep(0.1)
            now = time.time()
            if now - last_run >= self.streaming_interval:
                last_run = now
                if not self.is_recording:
                    break
                audio_data = self.audio.get_current_audio()
                if len(audio_data) >= 16000 * 0.4:
                    self.transcriber.transcribe_audio_chunk(audio_data, is_final=False)

    def _on_key_press(self):
        """Triggered on Right Alt key press."""
        now = time.time()

        # Case 1: In locked hands-free mode -> user taps once to finish!
        if self.is_locked:
            logger.info(">>> Right Alt pressed while in LOCKED mode: Unlocking and finalizing dictation.")
            self.is_locked = False
            self._trigger_finalize()
            return

        # Cancel any pending release timer from a prior tap
        if self._pending_release_timer:
            self._pending_release_timer.cancel()
            self._pending_release_timer = None

        # Case 2: Double-tap detection
        time_since_release = now - self.last_release_time
        if self.double_tap_lock_enabled and (time_since_release <= self.double_tap_threshold) and self.last_release_time > 0:
            logger.info(f">>> Double-tap detected ({time_since_release*1000:.1f}ms <= {self.double_tap_threshold*1000:.0f}ms)! Engaging Hands-Free Lock.")
            self.is_locked = True
            self.last_press_time = now
            self.feedback.play_lock()
            self.hud.sig_update_status.emit("נעול 🔒", "#0284C7")
            self.hud.sig_update_partial.emit("מצב דיבור חופשי 🔒 (לחץ שוב על Right Alt לסיום)")

            # Ensure recording session is active
            if not self.is_recording:
                self._start_recording_session()
            return

        # Case 3: Normal first press (Push-to-Talk)
        self.last_press_time = now
        if not self.is_recording:
            self._start_recording_session()

    def _on_key_release(self):
        """Triggered on Right Alt key release."""
        now = time.time()
        press_duration = now - self.last_press_time
        self.last_release_time = now

        # If in locked mode, releasing the key does NOT stop recording
        if self.is_locked:
            logger.debug("Right Alt released, but dictation is LOCKED. Continuing hands-free recording.")
            return

        if not self.is_recording:
            return

        # If double-tap lock is enabled and press duration was brief (<280ms),
        # wait up to double_tap_threshold to check if a second tap follows
        if self.double_tap_lock_enabled and press_duration < 0.28:
            logger.debug(f"Quick tap ({press_duration*1000:.1f}ms). Waiting for potential second tap...")

            def _deferred_check():
                if not self.is_locked and self.is_recording:
                    logger.info("Single tap window expired without second tap. Finalizing dictation.")
                    self._trigger_finalize()

            self._pending_release_timer = threading.Timer(self.double_tap_threshold, _deferred_check)
            self._pending_release_timer.daemon = True
            self._pending_release_timer.start()
            return

        # Otherwise (standard hold > 280ms), finalize immediately for zero latency!
        self._trigger_finalize()

    def _trigger_finalize(self):
        """Stops recording and triggers background transcription + text injection."""
        with self._state_lock:
            if not self.is_recording:
                return
            self.is_recording = False
            self.is_locked = False

        logger.info("<<< Finalizing dictation session...")
        self.tray.set_recording_state(False)
        self.hud.sig_update_status.emit("מעבד...", "#F59E0B")

        # Stop audio capture and get complete audio array
        full_audio = self.audio.stop_capture()

        # Finalize transcription in a dedicated thread to avoid blocking keyboard hook
        threading.Thread(
            target=self._finalize_and_inject,
            args=(full_audio,),
            name="FinalizeThread",
            daemon=True,
        ).start()

    def _finalize_and_inject(self, audio_data):
        try:
            start_t = time.time()
            if len(audio_data) < 16000 * 0.25:
                # Under 250ms of audio, likely an accidental tap or silence
                logger.info("Audio duration too short (<250ms), discarding.")
                self.hud.sig_hide.emit()
                return

            if self.transcriber.model is None:
                self.hud.sig_update_partial.emit("טוען מודל Whisper...")
                self.hud.sig_update_status.emit("טוען...", "#F59E0B")

            # Final high-quality transcription
            final_text = self.transcriber.transcribe_audio_chunk(audio_data, is_final=True)
            elapsed_ms = (time.time() - start_t) * 1000
            logger.info(f"Final transcription completed in {elapsed_ms:.1f}ms: '{final_text}'")

            if final_text:
                self.hud.sig_update_partial.emit(final_text)
                self.hud.sig_update_status.emit("הושלם ✓", "#10B981")
                self.feedback.play_stop()
                self.tray.add_dictation_to_history(final_text)

                if self.control_window:
                    self.control_window.sig_dictation_received.emit(final_text)

                # Inject text into original target window
                self.injector.inject(final_text)

                # Keep HUD visible briefly so user sees the checkmark
                time.sleep(0.4)
            else:
                logger.info("Empty transcription output (silence or non-speech).")
                time.sleep(0.15)

        except Exception as e:
            logger.error(f"Error finalizing transcription: {e}")
            self.feedback.play_error()
        finally:
            self.hud.sig_hide.emit()

    # Dynamic settings handlers
    def change_model(self, model_size: str):
        logger.info(f"Changing Whisper model to {model_size}...")
        threading.Thread(target=self.transcriber.change_model, args=(model_size,), daemon=True).start()

    def change_device(self, device_idx: Optional[int]):
        logger.info(f"Changing audio input device to {device_idx}...")
        self.audio.set_device(device_idx)

    def set_sound_enabled(self, enabled: bool):
        self.feedback.enabled = enabled

    def set_restore_window_enabled(self, enabled: bool):
        self.injector.restore_target_window = enabled

    def set_lock_enabled(self, enabled: bool):
        self.double_tap_lock_enabled = enabled
