"""
Key Detection Utility.
Run this script and press any key (Fn, Right Alt, Right Ctrl, Menu, etc.)
to see its exact Virtual Key Code and Scan Code in Windows.
"""

import ctypes
from ctypes import wintypes
import time
import sys

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_SYSKEYDOWN = 0x0104

class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_ulonglong),
    ]

HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_longlong, ctypes.c_int, wintypes.WPARAM, ctypes.POINTER(KBDLLHOOKSTRUCT))
user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD]
user32.SetWindowsHookExW.restype = wintypes.HHOOK
user32.CallNextHookEx.argtypes = [wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, ctypes.POINTER(KBDLLHOOKSTRUCT)]
user32.CallNextHookEx.restype = wintypes.LRESULT

VK_NAMES = {
    0xA5: "Right Alt (VK_RMENU)",
    0xA4: "Left Alt (VK_LMENU)",
    0x12: "Alt (VK_MENU)",
    0xA3: "Right Ctrl (VK_RCONTROL)",
    0xA2: "Left Ctrl (VK_LCONTROL)",
    0x11: "Ctrl (VK_CONTROL)",
    0x5D: "Context Menu / Apps / Fn Key (VK_APPS)",
    0x5C: "Right Windows Key (VK_RWIN)",
    0x5B: "Left Windows Key (VK_LWIN)",
    0x20: "Spacebar",
    0x1B: "Escape",
}


def main():
    print("=" * 60)
    print("  Windows Key Detection Utility")
    print("  Press ANY key on your keyboard to detect its code.")
    print("  (Press Ctrl+C or Escape to exit)")
    print("=" * 60)

    running = True

    def hook_proc(nCode, wParam, lParam):
        nonlocal running
        if nCode >= 0 and lParam:
            if wParam in (WM_KEYDOWN, WM_SYSKEYDOWN):
                kb = lParam.contents
                vk = kb.vkCode
                scan = kb.scanCode
                flags = kb.flags
                name = VK_NAMES.get(vk, f"Unknown ({hex(vk)})")
                is_extended = bool(flags & 0x01)
                print(f"[KEY PRESSED] VK: {hex(vk)} ({vk}) | ScanCode: {hex(scan)} | Extended: {is_extended} | Name: {name}")

                if vk == 0x1B:  # Esc
                    running = False
                    user32.PostQuitMessage(0)

        return user32.CallNextHookEx(None, nCode, wParam, lParam)

    c_proc = HOOKPROC(hook_proc)
    h_hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, c_proc, None, 0)

    if not h_hook:
        print(f"Failed to install hook! Error: {kernel32.GetLastError()}")
        return 1

    print("\nHook installed! Waiting for key presses...\n")

    msg = wintypes.MSG()
    try:
        while running and user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
    except KeyboardInterrupt:
        pass
    finally:
        user32.UnhookWindowsHookEx(h_hook)
        print("\nHook uninstalled. Done.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
