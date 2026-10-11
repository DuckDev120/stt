"""
Window Manager module for Windows OS.
Captures the active target window at the start of dictation, tracks focus,
and reliably restores focus to the target window prior to text injection,
even if the user switched windows, typed, or clicked elsewhere during speech.
"""

import ctypes
from ctypes import wintypes
import time
import logging

logger = logging.getLogger(__name__)

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# Win32 Constants
SW_RESTORE = 9
SW_SHOW = 5
LSFW_UNLOCK = 2

class GUITHREADINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("hwndActive", wintypes.HWND),
        ("hwndFocus", wintypes.HWND),
        ("hwndCapture", wintypes.HWND),
        ("hwndMenuOwner", wintypes.HWND),
        ("hwndMoveSize", wintypes.HWND),
        ("hwndCaret", wintypes.HWND),
        ("rcCaret", wintypes.RECT),
    ]


class WindowManager:
    def __init__(self):
        self.target_hwnd = None
        self.target_control = None
        self.target_title = ""
        self.target_thread_id = 0
        self.lock_time = 0.0

    def get_window_title(self, hwnd: int) -> str:
        """Retrieve the window title text for a given HWND."""
        if not hwnd or not user32.IsWindow(hwnd):
            return ""
        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return ""
        buff = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buff, length + 1)
        return buff.value

    def get_focused_control(self, hwnd: int) -> int:
        """Retrieve the focused control HWND inside the target window."""
        if not hwnd or not user32.IsWindow(hwnd):
            return None
        thread_id = user32.GetWindowThreadProcessId(hwnd, None)
        gui_info = GUITHREADINFO()
        gui_info.cbSize = ctypes.sizeof(GUITHREADINFO)
        if user32.GetGUIThreadInfo(thread_id, ctypes.byref(gui_info)):
            return gui_info.hwndFocus or gui_info.hwndCaret or hwnd
        return hwnd

    def lock_target_window(self) -> int:
        """
        Locks the currently active foreground window as the target window for dictation.
        Called the exact moment Push-to-Talk (Right Alt) is pressed.
        """
        self.target_hwnd = user32.GetForegroundWindow()
        self.lock_time = time.time()
        
        if self.target_hwnd and user32.IsWindow(self.target_hwnd):
            self.target_thread_id = user32.GetWindowThreadProcessId(self.target_hwnd, None)
            self.target_title = self.get_window_title(self.target_hwnd)
            self.target_control = self.get_focused_control(self.target_hwnd)
            logger.info(f"Target window locked: '{self.target_title}' (HWND: {hex(self.target_hwnd)})")
        else:
            self.target_hwnd = None
            self.target_title = ""
            self.target_control = None
            logger.warning("No foreground window active when dictation started.")
            
        return self.target_hwnd

    def restore_target_window(self, timeout_ms: int = 150) -> bool:
        """
        Brings the locked target window back to the foreground and restores focus.
        Uses Win32 AttachThreadInput and LockSetForegroundWindow unlock to guarantee
        that Windows allows the foreground switch even if the user switched windows.
        """
        if not self.target_hwnd or not user32.IsWindow(self.target_hwnd):
            logger.warning("Target window handle is no longer valid.")
            return False

        current_fg = user32.GetForegroundWindow()
        if current_fg == self.target_hwnd:
            logger.debug("Target window is already the foreground window.")
            return True

        logger.info(f"Restoring focus to target window '{self.target_title}' (HWND: {hex(self.target_hwnd)})...")
        
        # If the target window is minimized, restore it
        if user32.IsIconic(self.target_hwnd):
            user32.ShowWindow(self.target_hwnd, SW_RESTORE)

        current_thread_id = kernel32.GetCurrentThreadId()
        fg_thread_id = user32.GetWindowThreadProcessId(current_fg, None) if current_fg else 0
        target_thread_id = self.target_thread_id or user32.GetWindowThreadProcessId(self.target_hwnd, None)

        attached_fg = False
        attached_target = False

        try:
            # Unlock foreground transitions
            user32.LockSetForegroundWindow(LSFW_UNLOCK)

            # Attach thread inputs so Windows grants foreground permission
            if fg_thread_id and fg_thread_id != current_thread_id:
                attached_fg = bool(user32.AttachThreadInput(current_thread_id, fg_thread_id, True))
            if target_thread_id and target_thread_id != current_thread_id:
                attached_target = bool(user32.AttachThreadInput(current_thread_id, target_thread_id, True))

            # Force bring window to top and set foreground
            user32.BringWindowToTop(self.target_hwnd)
            user32.SetForegroundWindow(self.target_hwnd)
            
            # If target control was identified, restore focus to it
            if self.target_control and user32.IsWindow(self.target_control):
                user32.SetFocus(self.target_control)

        except Exception as e:
            logger.error(f"Error during thread input attachment: {e}")
        finally:
            # Always detach thread inputs to prevent system input queue locks
            if attached_fg:
                user32.AttachThreadInput(current_thread_id, fg_thread_id, False)
            if attached_target:
                user32.AttachThreadInput(current_thread_id, target_thread_id, False)

        # Allow Windows message pump up to timeout_ms to settle the focus
        start = time.time()
        while (time.time() - start) * 1000 < timeout_ms:
            if user32.GetForegroundWindow() == self.target_hwnd:
                logger.info(f"Successfully restored focus to '{self.target_title}'.")
                return True
            time.sleep(0.015)

        # Fallback: SwitchToThisWindow
        user32.SwitchToThisWindow(self.target_hwnd, True)
        time.sleep(0.03)
        return user32.GetForegroundWindow() == self.target_hwnd
