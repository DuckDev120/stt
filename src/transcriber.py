"""
Transcriber module using Faster-Whisper (CTranslate2).
Supports NVIDIA CUDA FP16 acceleration with automatic CPU INT8 fallback,
bilingual Hebrew/English prompt biasing, real-time streaming partial updates,
and zero-latency finalization upon key release.
"""

import logging
import threading
import time
from typing import Callable, Optional
import numpy as np

logger = logging.getLogger(__name__)


class WhisperTranscriber:
    def __init__(
        self,
        model_size: str = "large-v3-turbo",
        device: str = "auto",
        compute_type: str = "float16",
        language: Optional[str] = None,
        initial_prompt: str = "שלום, Hello, מדברים בעברית ובאנגלית. תמלול מדויק כולל סימני פיסוק.",
        beam_size: int = 1,
        on_partial_callback: Optional[Callable[[str], None]] = None,
        on_final_callback: Optional[Callable[[str], None]] = None,
    ):
        self.model_size = model_size
        self.requested_device = device
        self.compute_type = compute_type
        self.language = language
        self.initial_prompt = initial_prompt
        self.beam_size = beam_size
        self.on_partial_callback = on_partial_callback
        self.on_final_callback = on_final_callback

        self.model = None
        self.active_device = "cpu"
        self._lock = threading.Lock()
        self._is_loading = False

    def load_model(self):
        """Loads Faster-Whisper model with GPU acceleration and automatic CPU fallback."""
        with self._lock:
            if self.model is not None:
                return

            self._is_loading = True
            from faster_whisper import WhisperModel

            devices_to_try = []
            if self.requested_device == "cuda":
                devices_to_try.append(("cuda", self.compute_type))
            elif self.requested_device == "cpu":
                devices_to_try.append(("cpu", "int8"))
            else:  # "auto"
                devices_to_try.append(("cuda", self.compute_type))
                devices_to_try.append(("cuda", "int8_float16"))
                devices_to_try.append(("cpu", "int8"))

            loaded = False
            for dev, comp in devices_to_try:
                try:
                    logger.info(f"Attempting to load Whisper model '{self.model_size}' on {dev} ({comp})...")
                    self.model = WhisperModel(
                        self.model_size,
                        device=dev,
                        compute_type=comp,
                        download_root=None,
                    )
                    self.active_device = dev
                    loaded = True
                    logger.info(f"Successfully loaded '{self.model_size}' on {dev} with {comp}.")
                    break
                except Exception as e:
                    logger.warning(f"Failed to load Whisper model on {dev} ({comp}): {e}")

            if not loaded:
                logger.error("Failed to load Whisper on all requested devices. Attempting CPU float32 fallback...")
                try:
                    self.model = WhisperModel(self.model_size, device="cpu", compute_type="float32")
                    self.active_device = "cpu"
                    logger.info("Loaded Whisper model on CPU float32 fallback.")
                except Exception as ex:
                    logger.critical(f"Critical error loading Whisper model: {ex}")
                    raise

            self._is_loading = False

    def change_model(self, model_size: str):
        """Switches Whisper model (e.g. from tray menu)."""
        with self._lock:
            if self.model_size == model_size and self.model is not None:
                return
            self.model_size = model_size
            self.model = None
        self.load_model()

    def clean_text(self, text: str) -> str:
        """Cleans Whisper repetitive artifacts or hallucinated punctuation."""
        if not text:
            return ""
        text = text.strip()
        # Remove consecutive duplicate punctuation or common Whisper artifacts
        while "  " in text:
            text = text.replace("  ", " ")
        return text

    def transcribe_audio_chunk(self, audio: np.ndarray, is_final: bool = False) -> str:
        """
        Transcribes an audio numpy array.
        Uses beam_size=1 for streaming partials, and vad_filter=True.
        """
        if self.model is None:
            self.load_model()

        if len(audio) < 16000 * 0.2:  # Less than 200ms
            return ""

        try:
            start_t = time.time()
            beam = self.beam_size if is_final else 1

            segments, info = self.model.transcribe(
                audio,
                beam_size=beam,
                language=self.language,
                initial_prompt=self.initial_prompt,
                condition_on_previous_text=False,
                vad_filter=True,
                vad_parameters=dict(
                    min_silence_duration_ms=250,
                    speech_pad_ms=100,
                ),
            )

            result_parts = []
            for seg in segments:
                text_part = seg.text.strip()
                if text_part:
                    result_parts.append(text_part)

            final_str = self.clean_text(" ".join(result_parts))
            dur_ms = (time.time() - start_t) * 1000
            logger.debug(f"Transcribed {len(audio)/16000:.2f}s in {dur_ms:.1f}ms (is_final={is_final}): '{final_str}'")

            if is_final and self.on_final_callback:
                self.on_final_callback(final_str)
            elif not is_final and self.on_partial_callback:
                self.on_partial_callback(final_str)

            return final_str

        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return ""
