"""
Test script to verify Unicode SendInput text injection with Hebrew and English characters.
"""

import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.injector import TextInjector


def main():
    print("Testing Text Injector...")
    print("This will test Unicode SendInput synthesis without touching the clipboard.")
    print("Focus any text area (like Notepad or cursor) within 3 seconds...")
    for i in range(3, 0, -1):
        print(f"Injecting in {i}...")
        time.sleep(1)

    injector = TextInjector(
        method="unicode",
        restore_target_window=False,
        char_delay_ms=2,
        copy_to_clipboard=False,
    )

    test_phrase = "בדיקה: שלום עולם! Hello World 123 - Test successful."
    print(f"Injecting test string: '{test_phrase}'")
    success = injector.inject(test_phrase)
    print(f"Injection status: {'SUCCESS' if success else 'FAILED'}")

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
