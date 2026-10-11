"""
Text Injector module using Win32 SendInput KEYEVENTF_UNICODE.
Types Unicode characters (Hebrew, English, symbols) directly into the active caret
without relying on keyboard layout, avoiding bidi reversal and preventing clipboard corruption.
Includes optional clipboard copy as a safety net.
"""

import ctypes
from ctypes import wintypes
import time
import logging
from typing import Optional
from .window_manager import WindowManager

logger = logging.getLogger(__name__)

user32 = ctypes.windll.user32

# Win32 SendInput constants
INPUT_KEYBOARD = 1
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_SCANCODE = 0x0008

VK_CONTROL = 0x11
VK_V = 0x56
VK_RETURN = 0x0D

# Structures for SendInput
class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_ulonglong),
    ]

class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_ulonglong),
    ]

class _INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("ki", KEYBDINPUT),
        ("mi", MOUSEINPUT),
        ("hi", HARDWAREINPUT),
    ]

class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.DWORD),
        ("u", _INPUT_UNION),
    ]


class TextInjector:
    def __init__(
        self,
        window_manager: Optional[WindowManager] = None,
        method: str = "unicode",
        restore_target_window: bool = True,
        char_delay_ms: int = 0,
        copy_to_clipboard: bool = True,
    ):
        self.window_manager = window_manager
        self.method = method
        self.restore_target_window = restore_target_window
        self.char_delay_ms = char_delay_ms
        self.copy_to_clipboard = copy_to_clipboard

    def copy_text_to_clipboard(self, text: str):
        """Copies text to Windows Clipboard via ctypes Win32 API."""
        try:
            GMEM_MOVEABLE = 0x0002
            CF_UNICODETEXT = 13
            kernel32 = ctypes.windll.kernel32

            encoded = text.encode("utf-16-le") + b"\x00\x00"
            h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(encoded))
            if not h_mem:
                return

            ptr = kernel32.GlobalLock(h_mem)
            if not ptr:
                kernel32.GlobalFree(h_mem)
                return

            ctypes.memmove(ptr, encoded, len(encoded))
            kernel32.GlobalUnlock(h_mem)

            if user32.OpenClipboard(0):
                user32.EmptyClipboard()
                user32.SetClipboardData(CF_UNICODETEXT, h_mem)
                user32.CloseClipboard()
                logger.debug("Safety copy saved to Windows Clipboard.")
        except Exception as e:
            logger.warning(f"Failed to copy text to clipboard: {e}")

    def send_unicode_string(self, text: str):
        """
        Injects a string character by character using SendInput with KEYEVENTF_UNICODE.
        This correctly renders mixed Hebrew and English regardless of active keyboard layout.
        """
        if not text:
            return

        events = []
        for ch in text:
            if ch == "\r":
                continue
            elif ch == "\n":
                # Send Enter
                down = INPUT(type=INPUT_KEYBOARD)
                down.u.ki = KEYBDINPUT(wVk=VK_RETURN, wScan=0, dwFlags=0, time=0, dwExtraInfo=0)
                up = INPUT(type=INPUT_KEYBOARD)
                up.u.ki = KEYBDINPUT(wVk=VK_RETURN, wScan=0, dwFlags=KEYEVENTF_KEYUP, time=0, dwExtraInfo=0)
                events.extend([down, up])
            else:
                code_point = ord(ch)
                down = INPUT(type=INPUT_KEYBOARD)
                down.u.ki = KEYBDINPUT(wVk=0, wScan=code_point, dwFlags=KEYEVENTF_UNICODE, time=0, dwExtraInfo=0)
                up = INPUT(type=INPUT_KEYBOARD)
                up.u.ki = KEYBDINPUT(wVk=0, wScan=code_point, dwFlags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, time=0, dwExtraInfo=0)
                events.extend([down, up])

        if not events:
            return

        total_events = len(events)
        input_array = (INPUT * total_events)(*events)

        if self.char_delay_ms > 0:
            # Send character pairs with delay
            for i in range(0, total_events, 2):
                chunk = (INPUT * 2)(events[i], events[i + 1])
                user32.SendInput(2, chunk, ctypes.sizeof(INPUT))
                time.sleep(self.char_delay_ms / 1000.0)
        else:
            # Batch send all inputs in a single kernel call for zero latency
            sent = user32.SendInput(total_events, input_array, ctypes.sizeof(INPUT))
            if sent != total_events:
                logger.warning(f"SendInput sent {sent}/{total_events} events.")

    def paste_via_clipboard(self, text: str):
        """Pastes text via clipboard and simulates Ctrl+V."""
        self.copy_text_to_clipboard(text)
        time.sleep(0.02)
        
        # Simulate Ctrl+V
        inputs = (INPUT * 4)(
            INPUT(type=INPUT_KEYBOARD, u=_INPUT_UNION(ki=KEYBDINPUT(wVk=VK_CONTROL, wScan=0, dwFlags=0, time=0, dwExtraInfo=0))),
            INPUT(type=INPUT_KEYBOARD, u=_INPUT_UNION(ki=KEYBDINPUT(wVk=VK_V, wScan=0, dwFlags=0, time=0, dwExtraInfo=0))),
            INPUT(type=INPUT_KEYBOARD, u=_INPUT_UNION(ki=KEYBDINPUT(wVk=VK_V, wScan=0, dwFlags=KEYEVENTF_KEYUP, time=0, dwExtraInfo=0))),
            INPUT(type=INPUT_KEYBOARD, u=_INPUT_UNION(ki=KEYBDINPUT(wVk=VK_CONTROL, wScan=0, dwFlags=KEYEVENTF_KEYUP, time=0, dwExtraInfo=0))),
        )
        user32.SendInput(4, inputs, ctypes.sizeof(INPUT))

    def inject(self, text: str) -> bool:
        """
        Main entry point for text injection.
        Restores the target window focus if requested, then injects text.
        """
        text = text.strip()
        if not text:
            return False

        # Add a trailing space if appropriate for natural dictation flow
        text = text + " "

        # Optional clipboard safety copy
        if self.copy_to_clipboard:
            self.copy_text_to_clipboard(text)

        # Restore target window focus
        if self.restore_target_window and self.window_manager:
            self.window_manager.restore_target_window(timeout_ms=150)
            time.sleep(0.02)

        logger.info(f"Injecting {len(text)} characters into active window...")
        start = time.time()
        
        if self.method == "clipboard":
            self.paste_via_clipboard(text)
        else:
            self.send_unicode_string(text)

        logger.info(f"Injection completed in {(time.time() - start)*1000:.1f}ms.")
        return True
