"""
Low-Level Global Keyboard Hook for Windows.
Monitors Right Alt (VK_RMENU), Right Ctrl (VK_RCONTROL), Apps/Menu (VK_APPS), or Fn keys.
Fixed for 64-bit Windows ctypes handle signatures to prevent error 126.
Supports auto-detection of right-hand modifier keys and suppresses default system menus.
"""

import ctypes
from ctypes import wintypes
import threading
import logging
from typing import Callable, Optional, Union, List, Set

logger = logging.getLogger(__name__)

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# Win32 Constants
WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105

VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12
VK_RCONTROL = 0xA3
VK_LMENU = 0xA4
VK_RMENU = 0xA5
VK_APPS = 0x5D       # Context Menu / Applications key (often placed where Fn is)
VK_RWIN = 0x5C       # Right Windows key

LLKHF_EXTENDED = 0x01
LLKHF_INJECTED = 0x10
LLKHF_ALTDOWN = 0x20
LLKHF_UP = 0x80

# KBDLLHOOKSTRUCT definition
class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_ulonglong),
    ]

HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_longlong, ctypes.c_int, wintypes.WPARAM, ctypes.POINTER(KBDLLHOOKSTRUCT))

# Explicit 64-bit Win32 types to prevent pointer truncation on 64-bit Windows
user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD]
user32.SetWindowsHookExW.restype = wintypes.HHOOK
user32.CallNextHookEx.argtypes = [wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, ctypes.POINTER(KBDLLHOOKSTRUCT)]
user32.CallNextHookEx.restype = ctypes.c_longlong
user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
user32.UnhookWindowsHookEx.restype = wintypes.BOOL


class LowLevelKeyboardHook:
    def __init__(
        self,
        on_press: Optional[Callable[[], None]] = None,
        on_release: Optional[Callable[[], None]] = None,
        on_any_key: Optional[Callable[[int, bool, bool], None]] = None,
        trigger_key: Union[str, List[str]] = "AUTO_RIGHT",
        suppress_windows_menu: bool = True,
    ):
        self.on_press = on_press
        self.on_release = on_release
        self.on_any_key = on_any_key
        self.trigger_key_config = trigger_key
        self.suppress_windows_menu = suppress_windows_menu

        self._target_vks: Set[int] = set()
        self._allow_any_right = False
        self._parse_trigger_keys(trigger_key)

        self._hook_handle = None
        self._hook_proc_ref = None  # Retain reference to prevent Python garbage collection
        self._thread = None
        self._thread_id = None
        self._running = False
        self._is_pressed = False
        self._lock = threading.Lock()

    def _parse_trigger_keys(self, config_val: Union[str, List[str]]):
        """Parses user key configuration into matched virtual key codes."""
        named_map = {
            "VK_RMENU": {VK_RMENU},
            "RIGHT_ALT": {VK_RMENU},
            "ALT_R": {VK_RMENU},
            "VK_RCONTROL": {VK_RCONTROL},
            "RIGHT_CTRL": {VK_RCONTROL},
            "CTRL_R": {VK_RCONTROL},
            "VK_APPS": {VK_APPS},
            "APPS": {VK_APPS},
            "MENU": {VK_APPS},
            "FN": {VK_APPS, VK_RCONTROL, VK_RMENU},  # Fn on PC keyboards often maps to Apps or RCtrl or RAlt
            "VK_RWIN": {VK_RWIN},
            "RIGHT_WIN": {VK_RWIN},
            "AUTO_RIGHT": {VK_RMENU, VK_RCONTROL, VK_APPS, VK_RWIN},
            "ANY_RIGHT": {VK_RMENU, VK_RCONTROL, VK_APPS, VK_RWIN},
        }

        if isinstance(config_val, list):
            for item in config_val:
                key_upper = str(item).upper().strip()
                if key_upper in named_map:
                    self._target_vks.update(named_map[key_upper])
        else:
            key_upper = str(config_val).upper().strip()
            if key_upper in ("AUTO_RIGHT", "ANY_RIGHT"):
                self._allow_any_right = True
                self._target_vks.update(named_map["AUTO_RIGHT"])
            elif key_upper in named_map:
                self._target_vks.update(named_map[key_upper])
            else:
                # Try hex or int
                try:
                    val = int(key_upper, 0)
                    self._target_vks.add(val)
                except ValueError:
                    logger.warning(f"Unknown trigger key '{config_val}', falling back to AUTO_RIGHT.")
                    self._allow_any_right = True
                    self._target_vks.update(named_map["AUTO_RIGHT"])

        logger.info(f"Keyboard Hook configured to trigger on VK codes: {[hex(v) for v in self._target_vks]}")

    def _is_trigger_event(self, vk_code: int, flags: int) -> bool:
        """Determines if the current key event matches the configured trigger key."""
        # 1. Direct VK match
        if vk_code in self._target_vks:
            return True

        # 2. Check for extended Alt (VK_MENU with LLKHF_EXTENDED)
        if VK_RMENU in self._target_vks and vk_code == VK_MENU and bool(flags & LLKHF_EXTENDED):
            return True

        # 3. Check for extended Control (VK_CONTROL with LLKHF_EXTENDED)
        if VK_RCONTROL in self._target_vks and vk_code == VK_CONTROL and bool(flags & LLKHF_EXTENDED):
            return True

        # 4. If AUTO_RIGHT, accept any right modifier
        if self._allow_any_right:
            if vk_code in (VK_RMENU, VK_RCONTROL, VK_APPS, VK_RWIN):
                return True
            if bool(flags & LLKHF_EXTENDED) and vk_code in (VK_MENU, VK_CONTROL):
                return True

        return False

    def _low_level_proc(self, nCode: int, wParam: int, lParam: ctypes.POINTER(KBDLLHOOKSTRUCT)) -> int:
        if nCode >= 0 and lParam:
            kb = lParam.contents
            vk = kb.vkCode
            flags = kb.flags

            # Ignore events synthesized by our own injector
            if not (flags & LLKHF_INJECTED):
                is_trigger = self._is_trigger_event(vk, flags)
                is_down = wParam in (WM_KEYDOWN, WM_SYSKEYDOWN)
                is_up = wParam in (WM_KEYUP, WM_SYSKEYUP)

                if self.on_any_key and (is_down or is_up):
                    try:
                        self.on_any_key(vk, is_down, is_trigger)
                    except Exception:
                        pass

                if is_trigger:
                    if is_down:
                        with self._lock:
                            if not self._is_pressed:
                                self._is_pressed = True
                                logger.info(f">>> Trigger key DOWN detected: vk={hex(vk)}, flags={hex(flags)}")
                                if self.on_press:
                                    try:
                                        self.on_press()
                                    except Exception as e:
                                        logger.error(f"Error in on_press callback: {e}")
                        if self.suppress_windows_menu:
                            return 1  # Swallow event so OS doesn't queue Alt/Menu navigation

                    elif is_up:
                        with self._lock:
                            if self._is_pressed:
                                self._is_pressed = False
                                logger.info(f"<<< Trigger key UP detected: vk={hex(vk)}, flags={hex(flags)}")
                                if self.on_release:
                                    try:
                                        self.on_release()
                                    except Exception as e:
                                        logger.error(f"Error in on_release callback: {e}")
                        if self.suppress_windows_menu:
                            return 1  # Swallow event to prevent opening window menu

        return user32.CallNextHookEx(self._hook_handle, nCode, wParam, lParam)

    def _message_loop(self):
        self._thread_id = kernel32.GetCurrentThreadId()
        self._hook_proc_ref = HOOKPROC(self._low_level_proc)

        # Install Low-Level Keyboard Hook (hMod=None for current process thread hook)
        self._hook_handle = user32.SetWindowsHookExW(
            WH_KEYBOARD_LL,
            self._hook_proc_ref,
            None,
            0,
        )

        if not self._hook_handle:
            err = kernel32.GetLastError()
            logger.error(f"Failed to install WH_KEYBOARD_LL hook. Error code: {err}")
            self._running = False
            return

        logger.info(f"Low-level keyboard hook installed successfully! (Hook Handle: {hex(self._hook_handle)})")
        self._running = True

        # Standard Windows message pump
        msg = wintypes.MSG()
        while self._running:
            res = user32.GetMessageW(ctypes.byref(msg), 0, 0, 0)
            if res <= 0:
                break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        # Cleanup hook upon loop exit
        if self._hook_handle:
            user32.UnhookWindowsHookEx(self._hook_handle)
            self._hook_handle = None
        logger.info("Low-level keyboard hook uninstalled cleanly.")

    def start(self):
        """Starts the keyboard hook in a background daemon thread."""
        if self._running:
            return
        self._thread = threading.Thread(target=self._message_loop, name="KeyboardHookThread", daemon=True)
        self._thread.start()

    def stop(self):
        """Stops the keyboard hook and ends the message loop."""
        self._running = False
        if self._thread_id:
            user32.PostThreadMessageW(self._thread_id, 0x0012, 0, 0)  # WM_QUIT
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
