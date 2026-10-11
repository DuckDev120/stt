"""
System Tray Application module using PyQt6.
Provides an unobtrusive system tray icon with quick actions:
- Active model selector (large-v3-turbo, medium, small, etc.)
- Audio input device selector
- Toggle sound cues and target window restoration
- Recent dictations history with 1-click clipboard copy
- Config file quick-access
- Clean exit
"""

import collections
import logging
import os
from typing import Callable, List, Optional
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt

logger = logging.getLogger(__name__)


def create_tray_icon_pixmap(color_hex: str = "#3B82F6") -> QtGui.QIcon:
    """Dynamically generates a crisp 64x64 microphone icon for the system tray."""
    pixmap = QtGui.QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QtGui.QPainter(pixmap)
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

    # Outer circle badge
    painter.setBrush(QtGui.QBrush(QtGui.QColor(color_hex)))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(4, 4, 56, 56, 16, 16)

    # Inner microphone glyph
    painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255), 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    painter.setBrush(QtGui.QBrush(QtGui.QColor(255, 255, 255)))
    # Mic capsule
    painter.drawRoundedRect(24, 14, 16, 26, 8, 8)
    # Mic arc
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawArc(18, 22, 28, 26, 0, -180 * 16)
    # Mic stand
    painter.drawLine(32, 48, 32, 54)
    painter.drawLine(24, 54, 40, 54)

    painter.end()
    return QtGui.QIcon(pixmap)


class TrayApplication:
    def __init__(
        self,
        app: QtWidgets.QApplication,
        on_change_model: Callable[[str], None],
        on_change_device: Callable[[Optional[int]], None],
        on_toggle_sound: Callable[[bool], None],
        on_toggle_window_restore: Callable[[bool], None],
        on_exit: Callable[[], None],
        on_open_control_window: Optional[Callable[[], None]] = None,
        initial_model: str = "large-v3-turbo",
        initial_device_idx: Optional[int] = None,
        sound_enabled: bool = True,
        restore_window_enabled: bool = True,
        config_path: str = "config.yaml",
    ):
        self.app = app
        self.on_change_model = on_change_model
        self.on_change_device = on_change_device
        self.on_toggle_sound = on_toggle_sound
        self.on_toggle_window_restore = on_toggle_window_restore
        self.on_exit = on_exit
        self.on_open_control_window = on_open_control_window

        self.current_model = initial_model
        self.current_device_idx = initial_device_idx
        self.sound_enabled = sound_enabled
        self.restore_window_enabled = restore_window_enabled
        self.config_path = config_path

        self.recent_dictations = collections.deque(maxlen=7)
        self.device_list = []

        self.tray = QtWidgets.QSystemTrayIcon(self.app)
        self.tray.setIcon(create_tray_icon_pixmap("#3B82F6"))
        self.tray.setToolTip("Speech-to-Text Dictation (Right Alt / Fn)")

        self.tray.activated.connect(self._on_tray_activated)

        self.menu = QtWidgets.QMenu()
        self._build_menu()
        self.tray.setContextMenu(self.menu)
        self.tray.show()

    def _on_tray_activated(self, reason: QtWidgets.QSystemTrayIcon.ActivationReason):
        if reason in (
            QtWidgets.QSystemTrayIcon.ActivationReason.Trigger,
            QtWidgets.QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            if self.on_open_control_window:
                self.on_open_control_window()

    def set_recording_state(self, is_recording: bool):
        """Updates tray icon color during recording."""
        if is_recording:
            self.tray.setIcon(create_tray_icon_pixmap("#EF4444"))  # Red
        else:
            self.tray.setIcon(create_tray_icon_pixmap("#3B82F6"))  # Blue

    def add_dictation_to_history(self, text: str):
        if text.strip():
            self.recent_dictations.appendleft(text.strip())
            self._rebuild_recent_menu()

    def update_device_list(self, devices: List[tuple[int, str]]):
        self.device_list = devices
        self._rebuild_device_menu()

    def _build_menu(self):
        self.menu.clear()

        # Title
        header = QtGui.QAction("🎙️ שירות הכתבה קולית (Right Alt / Fn)", self.menu)
        header.setEnabled(False)
        self.menu.addAction(header)

        # Open Control Center
        if self.on_open_control_window:
            action_gui = QtGui.QAction("🖥️ פתח מרכז שליטה (Control Center)", self.menu)
            action_gui.triggered.connect(self.on_open_control_window)
            self.menu.addAction(action_gui)

        self.menu.addSeparator()

        # 1. Model Selection Submenu
        self.model_menu = self.menu.addMenu("בחירת מודל Whisper")
        self.model_group = QtGui.QActionGroup(self.model_menu)
        self.model_group.setExclusive(True)

        for m_name in ["large-v3-turbo", "medium", "small", "base", "tiny"]:
            action = QtGui.QAction(m_name, self.model_menu, checkable=True)
            if m_name == self.current_model:
                action.setChecked(True)
            action.triggered.connect(lambda checked, m=m_name: self._handle_model_change(m))
            self.model_group.addAction(action)
            self.model_menu.addAction(action)

        # 2. Audio Device Submenu
        self.device_menu = self.menu.addMenu("בחירת מיקרופון")
        self._rebuild_device_menu()

        # 3. Sound Cues Toggle
        self.sound_action = QtGui.QAction("צלילי חיווי (Sound Cues)", self.menu, checkable=True)
        self.sound_action.setChecked(self.sound_enabled)
        self.sound_action.triggered.connect(self._handle_sound_toggle)
        self.menu.addAction(self.sound_action)

        # 4. Target Window Restoration Toggle
        self.restore_action = QtGui.QAction("שמירת חלון יעד (Window Restore)", self.menu, checkable=True)
        self.restore_action.setChecked(self.restore_window_enabled)
        self.restore_action.triggered.connect(self._handle_restore_toggle)
        self.menu.addAction(self.restore_action)

        self.menu.addSeparator()

        # 5. Recent Dictations Submenu
        self.recent_menu = self.menu.addMenu("היסטוריית הכתבות אחרונות")
        self._rebuild_recent_menu()

        self.menu.addSeparator()

        # 6. Open Config
        config_action = QtGui.QAction("עריכת הגדרות (config.yaml)", self.menu)
        config_action.triggered.connect(self._open_config)
        self.menu.addAction(config_action)

        # 7. Exit
        exit_action = QtGui.QAction("יציאה מהתוכנה", self.menu)
        exit_action.triggered.connect(self._handle_exit)
        self.menu.addAction(exit_action)

    def _rebuild_device_menu(self):
        self.device_menu.clear()
        self.device_group = QtGui.QActionGroup(self.device_menu)
        self.device_group.setExclusive(True)

        # Default system device
        default_action = QtGui.QAction("ברירת מחדל של Windows", self.device_menu, checkable=True)
        if self.current_device_idx is None:
            default_action.setChecked(True)
        default_action.triggered.connect(lambda: self._handle_device_change(None))
        self.device_group.addAction(default_action)
        self.device_menu.addAction(default_action)
        self.device_menu.addSeparator()

        for idx, dev_name in self.device_list:
            action = QtGui.QAction(f"{dev_name} (ID: {idx})", self.device_menu, checkable=True)
            if self.current_device_idx == idx:
                action.setChecked(True)
            action.triggered.connect(lambda checked, i=idx: self._handle_device_change(i))
            self.device_group.addAction(action)
            self.device_menu.addAction(action)

    def _rebuild_recent_menu(self):
        self.recent_menu.clear()
        if not self.recent_dictations:
            empty_act = QtGui.QAction("(אין היסטוריה עדיין)", self.recent_menu)
            empty_act.setEnabled(False)
            self.recent_menu.addAction(empty_act)
            return

        for text in self.recent_dictations:
            display = text if len(text) < 40 else text[:37] + "..."
            action = QtGui.QAction(f"📋 {display}", self.recent_menu)
            action.triggered.connect(lambda checked, t=text: self._copy_to_clipboard(t))
            self.recent_menu.addAction(action)

    def _copy_to_clipboard(self, text: str):
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(text)
        self.tray.showMessage("הועתק ללוח", text, QtWidgets.QSystemTrayIcon.MessageIcon.Information, 1500)

    def _open_config(self):
        if os.path.exists(self.config_path):
            os.system(f'notepad.exe "{os.path.abspath(self.config_path)}"')

    def _handle_model_change(self, model_name: str):
        self.current_model = model_name
        self.on_change_model(model_name)
        self.tray.showMessage("מודל שונה", f"המודל הפעיל כעת הוא {model_name}", QtWidgets.QSystemTrayIcon.MessageIcon.Information, 1500)

    def _handle_device_change(self, dev_idx: Optional[int]):
        self.current_device_idx = dev_idx
        self.on_change_device(dev_idx)

    def _handle_sound_toggle(self, checked: bool):
        self.sound_enabled = checked
        self.on_toggle_sound(checked)

    def _handle_restore_toggle(self, checked: bool):
        self.restore_window_enabled = checked
        self.on_toggle_window_restore(checked)

    def _handle_exit(self):
        self.on_exit()
