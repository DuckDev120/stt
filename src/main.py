"""
Main entry point for the Speech-to-Text Dictation Service.
Initializes logging, single-instance mutex, configuration, PyQt6 application,
Dynamic Island HUD, System Tray, Control Center Studio, and DictationController.
"""

import ctypes
from ctypes import wintypes
import logging
import os
import signal
import sys
import yaml
from PyQt6 import QtWidgets, QtCore

from .hud_overlay import DynamicIslandHUD
from .tray_app import TrayApplication
from .control_window import ControlCenterWindow
from .app_controller import DictationController

# Win32 Mutex for single instance check
ERROR_ALREADY_EXISTS = 183
WINDOW_TITLE = "Speech-to-Text Studio | בקרת תמלול קולי"


def setup_logging():
    log_format = "%(asctime)s [%(levelname)s] (%(threadName)s) %(name)s: %(message)s"
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("speechtotext.log", encoding="utf-8"),
        ],
    )


def load_config(config_path: str = "config.yaml") -> dict:
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logging.error(f"Error reading {config_path}: {e}")
    return {}


def acquire_single_instance_mutex(mutex_name: str = "Local\\SpeechToText_Dictation_Mutex"):
    """Prevents multiple copies of the dictation service from running concurrently."""
    kernel32 = ctypes.windll.kernel32
    mutex = kernel32.CreateMutexW(None, False, mutex_name)
    last_error = kernel32.GetLastError()
    if last_error == ERROR_ALREADY_EXISTS:
        return None
    return mutex


def bring_existing_instance_to_front():
    """If another instance is running, brings its window to front and notifies the user."""
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.FindWindowW(None, WINDOW_TITLE)
        if hwnd:
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            user32.SetForegroundWindow(hwnd)

        user32.MessageBoxW(
            0,
            "שירות התמלול כבר פועל ברקע ומאזין למקש החם!\n"
            "חלון השליטה הוצג עבורך כעת.\n\n"
            "מקשי קיצור: החזק Right Alt / Fn כדי להכתיב בכל חלון.",
            "Speech-to-Text Studio",
            0x40,  # MB_OK | MB_ICONINFORMATION
        )
    except Exception as e:
        logging.warning(f"Could not focus existing window: {e}")


def main():
    setup_logging()
    logger = logging.getLogger("main")
    logger.info("Initializing Speech-to-Text Dictation Service...")

    # Single-instance check
    mutex = acquire_single_instance_mutex()
    if not mutex:
        logger.warning("Another instance of the Dictation Service is already running.")
        bring_existing_instance_to_front()
        sys.exit(0)

    config = load_config("config.yaml")
    hud_cfg = config.get("hud", {})
    whisper_cfg = config.get("whisper", {})
    audio_cfg = config.get("audio", {})
    sound_cfg = config.get("sound_cues", {})
    inj_cfg = config.get("injection", {})
    hotkey_cfg = config.get("hotkey", {})

    app = QtWidgets.QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    # Initialize HUD Overlay
    hud = DynamicIslandHUD(
        width=int(hud_cfg.get("width", 520)),
        height=int(hud_cfg.get("height", 58)),
        top_margin=int(hud_cfg.get("top_margin_px", 12)),
        anim_duration=int(hud_cfg.get("animation_duration_ms", 200)),
    )

    controller = None
    control_window = None

    def on_exit_requested():
        logger.info("Exit requested. Cleaning up and terminating...")
        if controller:
            controller.stop()
        if control_window:
            control_window.hide()
            control_window.close()
        hud.close()
        app.quit()

    def show_control_window():
        if control_window:
            control_window.show()
            control_window.raise_()
            control_window.activateWindow()

    # Initialize Control Center Window
    control_window = ControlCenterWindow(
        on_change_model=lambda m: controller.change_model(m) if controller else None,
        on_change_device=lambda d: controller.change_device(d) if controller else None,
        on_toggle_sound=lambda s: controller.set_sound_enabled(s) if controller else None,
        on_toggle_lock=lambda l: controller.set_lock_enabled(l) if controller else None,
        on_toggle_restore=lambda r: controller.set_restore_window_enabled(r) if controller else None,
        on_test_hud=lambda: hud.show_welcome("🎙️ בדיקת Dynamic Island! שירות התמלול מוכן", duration_ms=3000),
        on_exit_app=on_exit_requested,
        initial_model=whisper_cfg.get("model_size", "small"),
        initial_device_idx=audio_cfg.get("device_index", None),
        sound_enabled=sound_cfg.get("enabled", True),
        lock_enabled=hotkey_cfg.get("double_tap_lock_enabled", True),
        restore_window_enabled=inj_cfg.get("restore_target_window", True),
        config_path="config.yaml",
    )

    # Initialize System Tray
    tray = TrayApplication(
        app=app,
        on_change_model=lambda m: controller.change_model(m) if controller else None,
        on_change_device=lambda d: controller.change_device(d) if controller else None,
        on_toggle_sound=lambda s: controller.set_sound_enabled(s) if controller else None,
        on_toggle_window_restore=lambda r: controller.set_restore_window_enabled(r) if controller else None,
        on_exit=on_exit_requested,
        on_open_control_window=show_control_window,
        initial_model=whisper_cfg.get("model_size", "small"),
        initial_device_idx=audio_cfg.get("device_index", None),
        sound_enabled=sound_cfg.get("enabled", True),
        restore_window_enabled=inj_cfg.get("restore_target_window", True),
        config_path="config.yaml",
    )

    # Initialize Controller with both HUD and Control Window
    controller = DictationController(
        config=config,
        hud=hud,
        tray=tray,
        control_window=control_window,
    )
    controller.start()

    # Graceful shutdown on Ctrl+C in terminal
    def sigint_handler(*args):
        on_exit_requested()

    signal.signal(signal.SIGINT, sigint_handler)

    # Periodic timer to allow Python signal handling in Qt event loop
    sig_timer = QtCore.QTimer()
    sig_timer.timeout.connect(lambda: None)
    sig_timer.start(500)

    # Unless explicitly asked to run minimized, show the Control Center window immediately
    if "--minimized" not in sys.argv and "-m" not in sys.argv:
        show_control_window()

    logger.info("Dictation Service is active and ready. Control Center Window displayed.")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
