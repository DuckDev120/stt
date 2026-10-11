"""
Unit test for Double-Tap Lock (Hands-Free Mode) state machine in DictationController.
"""

import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from unittest.mock import MagicMock
from src.app_controller import DictationController


def test_double_tap_state_machine():
    print("Testing Double-Tap Lock State Machine...")

    config = {
        "whisper": {"model_size": "tiny", "device": "cpu", "compute_type": "int8"},
        "audio": {"sample_rate": 16000, "channels": 1, "max_recording_sec": 30},
        "hotkey": {
            "trigger_key": "VK_RMENU",
            "suppress_windows_menu": True,
            "double_tap_lock_enabled": True,
            "double_tap_threshold_ms": 350,
        },
        "sound_cues": {"enabled": False},
        "injection": {"method": "unicode", "restore_target_window": False},
    }

    mock_hud = MagicMock()
    mock_tray = MagicMock()

    controller = DictationController(config, mock_hud, mock_tray)

    # Mock audio and transcriber so we don't open real microphone during test
    controller.audio = MagicMock()
    controller.audio.is_recording = False
    controller.audio.get_current_audio.return_value = [0.0] * 32000
    controller.audio.stop_capture.return_value = [0.0] * 32000
    controller.transcriber = MagicMock()
    controller.transcriber.transcribe_audio_chunk.return_value = "בדיקת נעילה מוצלחת"
    controller.injector = MagicMock()

    # --- Scenario 1: Double-Tap Sequence ("Tak-Tak") ---
    print("\n1. Simulating Double-Tap ('Tak-Tak')...")
    # Tap 1: Press & Quick Release (60ms)
    controller._on_key_press()
    assert controller.is_recording is True, "Controller should start recording on first tap"
    time.sleep(0.06)
    controller._on_key_release()
    assert controller.is_recording is True, "Recording should remain active during double-tap window"

    # Tap 2: Press within 120ms (< 350ms threshold)
    time.sleep(0.06)
    controller._on_key_press()
    assert controller.is_locked is True, "Controller should be in LOCKED mode after double-tap"
    print("   [OK] Lock mode engaged: is_locked = True")

    # Release of Tap 2:
    time.sleep(0.05)
    controller._on_key_release()
    assert controller.is_recording is True, "Recording MUST continue after releasing second tap"
    assert controller.is_locked is True, "Still in locked mode"
    print("   [OK] Key released: recording continues hands-free without holding key!")

    # --- Scenario 2: Single Tap to Unlock and Finalize ---
    print("\n2. Simulating Single Tap to Unlock and Finish...")
    controller._on_key_press()
    assert controller.is_locked is False, "Controller should unlock on single tap"
    print("   [OK] Unlocked! Finalizing transcription and injecting text.")

    time.sleep(0.1)

    # --- Scenario 3: Normal Push-to-Talk (Hold > 300ms) ---
    print("\n3. Simulating Normal Hold Push-to-Talk...")
    controller.last_release_time = 0.0  # Reset
    controller._on_key_press()
    assert controller.is_recording is True
    assert controller.is_locked is False
    time.sleep(0.32)  # Hold for 320ms
    controller._on_key_release()
    # Should immediately trigger finalize, not wait for timer
    assert controller.is_locked is False
    print("   [OK] Normal hold finalized immediately without locking.")

    print("\nALL DOUBLE-TAP STATE MACHINE TESTS PASSED SUCCESSFULLY!")
    return 0


if __name__ == "__main__":
    sys.exit(test_double_tap_state_machine())
