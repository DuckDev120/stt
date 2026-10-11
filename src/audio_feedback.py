"""
Audio Feedback module providing subtle, pleasant UI sound cues for recording start and commit.
Synthesizes smooth, chime waves in-memory using standard library wave + math / winsound,
guaranteeing 0ms latency and no missing asset dependencies.
"""

import io
import math
import struct
import wave
import winsound
import threading
import logging
from typing import Dict

logger = logging.getLogger(__name__)


def _generate_wav_bytes(frequencies: list[float], duration_sec: float, sample_rate: int = 44100, volume: float = 0.5) -> bytes:
    """Generate in-memory WAV byte buffer with smooth exponential fade-out envelope."""
    num_samples = int(sample_rate * duration_sec)
    buffer = io.BytesIO()
    
    with wave.open(buffer, "wb") as wf:
        wf.setnchannels(1)  # Mono
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)

        raw_data = bytearray()
        for i in range(num_samples):
            t = i / sample_rate
            # Smooth exponential decay envelope
            envelope = math.exp(-4.5 * (i / num_samples))
            
            # Combine frequencies
            sample_val = 0.0
            for freq in frequencies:
                sample_val += math.sin(2.0 * math.pi * freq * t)
            sample_val /= len(frequencies)
            
            # Scale to 16-bit integer range
            int_val = int(sample_val * envelope * volume * 32767.0)
            int_val = max(-32768, min(32767, int_val))
            raw_data.extend(struct.pack("<h", int_val))

        wf.writeframes(raw_data)

    return buffer.getvalue()


class AudioFeedback:
    def __init__(self, enabled: bool = True, volume: float = 0.6):
        self.enabled = enabled
        self.volume = max(0.0, min(1.0, volume))
        self._cache: Dict[str, bytes] = {}
        self._init_sounds()

    def _init_sounds(self):
        """Pre-render WAV buffers for instant non-blocking playback."""
        try:
            # Gentle, modern ascending chime for Start Recording (C6 -> G6)
            self._cache["start"] = _generate_wav_bytes(
                frequencies=[1046.5, 1567.98],
                duration_sec=0.08,
                volume=self.volume * 0.7
            )
            # Warm, pleasant resolving chime for Commit / Finish (E5 -> C5)
            self._cache["stop"] = _generate_wav_bytes(
                frequencies=[659.25, 523.25],
                duration_sec=0.12,
                volume=self.volume * 0.8
            )
            # Distinct rising double-tone chime for Lock / Hands-Free mode (G5 -> C6 -> E6)
            self._cache["lock"] = _generate_wav_bytes(
                frequencies=[783.99, 1046.50, 1318.51],
                duration_sec=0.14,
                volume=self.volume * 0.85
            )
            # Soft error chime
            self._cache["error"] = _generate_wav_bytes(
                frequencies=[261.63, 196.0],
                duration_sec=0.15,
                volume=self.volume * 0.5
            )
        except Exception as e:
            logger.error(f"Failed to generate feedback sounds: {e}")

    def _play_async(self, sound_bytes: bytes):
        if not self.enabled or not sound_bytes:
            return
        def _worker():
            try:
                winsound.PlaySound(sound_bytes, winsound.SND_MEMORY | winsound.SND_ASYNC)
            except Exception as e:
                logger.debug(f"Audio playback error: {e}")
        threading.Thread(target=_worker, daemon=True).start()

    def play_start(self):
        """Play subtle start-of-recording chime."""
        if "start" in self._cache:
            self._play_async(self._cache["start"])

    def play_lock(self):
        """Play distinct lock / hands-free mode confirmation chime."""
        if "lock" in self._cache:
            self._play_async(self._cache["lock"])

    def play_stop(self):
        """Play smooth completion chime."""
        if "stop" in self._cache:
            self._play_async(self._cache["stop"])

    def play_error(self):
        """Play soft error chime."""
        if "error" in self._cache:
            self._play_async(self._cache["error"])
