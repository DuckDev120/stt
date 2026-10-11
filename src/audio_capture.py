"""
Audio Capture module using sounddevice + circular RingBuffer + VAD.
Streams 16kHz mono float32 audio seamlessly, provides real-time RMS volume metrics
for the Dynamic Island HUD animation, and handles device discovery.
"""

import collections
import logging
import threading
from typing import Callable, List, Optional, Tuple
import numpy as np
import sounddevice as sd

logger = logging.getLogger(__name__)


class RingBuffer:
    """Thread-safe circular audio buffer for raw float32 samples."""

    def __init__(self, capacity_samples: int):
        self.capacity = capacity_samples
        self.buffer = np.zeros(capacity_samples, dtype=np.float32)
        self.write_idx = 0
        self.total_written = 0
        self.lock = threading.Lock()

    def write(self, data: np.ndarray):
        with self.lock:
            n = len(data)
            if n >= self.capacity:
                self.buffer[:] = data[-self.capacity :]
                self.write_idx = 0
                self.total_written += n
                return

            end = self.write_idx + n
            if end <= self.capacity:
                self.buffer[self.write_idx : end] = data
            else:
                first_part = self.capacity - self.write_idx
                self.buffer[self.write_idx :] = data[:first_part]
                self.buffer[: end - self.capacity] = data[first_part:]

            self.write_idx = end % self.capacity
            self.total_written += n

    def get_data(self) -> np.ndarray:
        """Returns all accumulated audio samples up to buffer capacity in chronological order."""
        with self.lock:
            if self.total_written < self.capacity:
                return self.buffer[: self.write_idx].copy()
            else:
                # Buffer has wrapped around
                return np.concatenate((self.buffer[self.write_idx :], self.buffer[: self.write_idx]))

    def clear(self):
        with self.lock:
            self.buffer.fill(0)
            self.write_idx = 0
            self.total_written = 0


class AudioCapture:
    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        device_index: Optional[int] = None,
        max_duration_sec: int = 180,
        on_rms_update: Optional[Callable[[float], None]] = None,
    ):
        self.sample_rate = sample_rate
        self.channels = channels
        self.device_index = device_index
        self.max_duration_sec = max_duration_sec
        self.on_rms_update = on_rms_update

        self.ring_buffer = RingBuffer(capacity_samples=self.sample_rate * self.max_duration_sec)
        self.stream: Optional[sd.InputStream] = None
        self.is_recording = False
        self._lock = threading.Lock()
        self.current_rms = 0.0

        # Silero VAD state (lazy loaded)
        self._vad_model = None
        self._vad_enabled = True

    @staticmethod
    def list_input_devices() -> List[Tuple[int, str]]:
        """Returns a list of (device_index, device_name) for all available audio input devices."""
        devices = []
        try:
            device_list = sd.query_devices()
            for idx, dev in enumerate(device_list):
                if dev.get("max_input_channels", 0) > 0:
                    devices.append((idx, dev.get("name", f"Device {idx}")))
        except Exception as e:
            logger.error(f"Error querying audio devices: {e}")
        return devices

    def set_device(self, device_index: Optional[int]):
        """Sets the active input device index."""
        with self._lock:
            self.device_index = device_index
            if self.is_recording:
                self.stop_capture()
                self.start_capture()

    def _audio_callback(self, indata: np.ndarray, frames: int, time_info, status):
        if status:
            logger.debug(f"SoundDevice status warning: {status}")

        # Flatten mono channel
        audio_chunk = indata[:, 0].copy()
        self.ring_buffer.write(audio_chunk)

        # Compute instant RMS volume level for UI pulse / waveform
        rms = float(np.sqrt(np.mean(np.square(audio_chunk))))
        self.current_rms = rms
        if self.on_rms_update:
            try:
                self.on_rms_update(rms)
            except Exception:
                pass

    def start_capture(self):
        """Starts recording audio from the microphone into the ring buffer."""
        with self._lock:
            if self.is_recording:
                return

            self.ring_buffer.clear()
            self.current_rms = 0.0

            try:
                self.stream = sd.InputStream(
                    samplerate=self.sample_rate,
                    channels=self.channels,
                    dtype=np.float32,
                    device=self.device_index,
                    blocksize=int(self.sample_rate * 0.05),  # 50ms blocks for smooth volume updates
                    callback=self._audio_callback,
                )
                self.stream.start()
                self.is_recording = True
                logger.info(f"Audio capture started on device index {self.device_index}.")
            except Exception as e:
                logger.error(f"Failed to start audio stream: {e}")
                self.is_recording = False
                raise

    def stop_capture(self) -> np.ndarray:
        """Stops recording and returns the complete recorded audio array."""
        with self._lock:
            if not self.is_recording:
                return np.array([], dtype=np.float32)

            self.is_recording = False
            if self.stream:
                try:
                    self.stream.stop()
                    self.stream.close()
                except Exception as e:
                    logger.debug(f"Error closing audio stream: {e}")
                self.stream = None

            audio_data = self.ring_buffer.get_data()
            logger.info(f"Audio capture stopped. Total duration: {len(audio_data)/self.sample_rate:.2f}s.")
            return audio_data

    def get_current_audio(self) -> np.ndarray:
        """Retrieves accumulated audio data so far without stopping capture (for streaming)."""
        return self.ring_buffer.get_data()
