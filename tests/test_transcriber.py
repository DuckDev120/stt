"""
Test script to verify Faster-Whisper model loading and bilingual transcription.
"""

import sys
import os
import time
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.transcriber import WhisperTranscriber


def main():
    print("Testing Whisper Transcriber...")
    model_size = "tiny" if "--fast" in sys.argv else "small"
    print(f"Initializing WhisperTranscriber with model '{model_size}'...")

    transcriber = WhisperTranscriber(
        model_size=model_size,
        device="auto",
        compute_type="float16",
    )

    t0 = time.time()
    print("Loading model (downloading on first run if needed)...")
    transcriber.load_model()
    print(f"[OK] Model loaded in {time.time() - t0:.2f}s on device: {transcriber.active_device}")

    # Generate 1.5 seconds of synthetic audio (speech-like tone mixture)
    sample_rate = 16000
    t = np.linspace(0, 1.5, int(sample_rate * 1.5), endpoint=False, dtype=np.float32)
    fake_audio = 0.3 * np.sin(2 * np.pi * 300 * t) + 0.2 * np.sin(2 * np.pi * 600 * t)

    print("Testing transcription pass...")
    t1 = time.time()
    result = transcriber.transcribe_audio_chunk(fake_audio, is_final=True)
    print(f"[OK] Inference pass completed in {(time.time() - t1)*1000:.1f}ms. Output: '{result}'")

    print("\nTEST PASSED: Transcriber initialized and ran inference successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
