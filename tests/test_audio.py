"""
Test script to enumerate input audio devices and test 2 seconds of audio recording and RMS levels.
"""

import sys
import os
import time
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.audio_capture import AudioCapture


def main():
    print("Testing Audio Capture...")
    devices = AudioCapture.list_input_devices()
    print("\n--- Available Input Devices ---")
    for idx, name in devices:
        print(f"[{idx}] {name}")
    print("--------------------------------\n")

    rms_values = []

    def rms_cb(rms):
        rms_values.append(rms)

    capture = AudioCapture(sample_rate=16000, channels=1, on_rms_update=rms_cb)

    print("Starting 2.5-second recording test. Please speak into your microphone...")
    capture.start_capture()
    time.sleep(2.5)
    audio = capture.stop_capture()

    print(f"\n[OK] Recorded {len(audio)} samples ({len(audio)/16000:.2f} seconds).")
    print(f"[OK] Audio dtype: {audio.dtype}, min: {np.min(audio):.4f}, max: {np.max(audio):.4f}")
    if rms_values:
        print(f"[OK] Max RMS volume detected: {max(rms_values):.4f}")
    else:
        print("[WARNING] No RMS callbacks received.")

    if len(audio) > 0 and len(rms_values) > 0:
        print("\nTEST PASSED: Microphone audio capture is functioning properly.")
        return 0
    else:
        print("\nTEST FAILED: No audio captured.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
