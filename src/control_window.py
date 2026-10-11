"""
Control Center Window for Speech-to-Text Dictation Service.
Provides an interactive desktop GUI dashboard for:
- Live status verification (GPU acceleration, Whisper model, audio capture)
- Live Hotkey Tester (displays real-time keypresses & VK codes)
- Live Microphone Visualizer (real-time RMS volume meter)
- Interactive Dictation Test Sandbox
- One-click configuration adjustments (models, audio devices, sound cues)
- Clean minimize-to-tray and background service monitoring
"""

import os
import subprocess
import logging
from typing import Optional, List, Callable
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot

logger = logging.getLogger(__name__)


class ModernProgressBar(QtWidgets.QProgressBar):
    """Custom stylized audio volume meter."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTextVisible(False)
        self.setFixedHeight(10)
        self.setRange(0, 100)
        self.setValue(0)
        self.setStyleSheet("""
            QProgressBar {
                background-color: #1E2330;
                border-radius: 5px;
                border: 1px solid #2D3748;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #10B981, stop:0.7 #3B82F6, stop:1.0 #EF4444);
                border-radius: 4px;
            }
        """)


class ControlCenterWindow(QtWidgets.QMainWindow):
    # Cross-thread signals
    sig_update_key_event = pyqtSignal(str, bool)  # key_desc, is_trigger
    sig_update_audio_rms = pyqtSignal(float)
    sig_dictation_received = pyqtSignal(str)

    def __init__(
        self,
        on_change_model: Callable[[str], None],
        on_change_device: Callable[[Optional[int]], None],
        on_toggle_sound: Callable[[bool], None],
        on_toggle_lock: Callable[[bool], None],
        on_toggle_restore: Callable[[bool], None],
        on_test_hud: Callable[[], None],
        on_exit_app: Callable[[], None],
        initial_model: str = "small",
        initial_device_idx: Optional[int] = None,
        sound_enabled: bool = True,
        lock_enabled: bool = True,
        restore_window_enabled: bool = True,
        device_list: Optional[List[tuple[int, str]]] = None,
        config_path: str = "config.yaml",
    ):
        super().__init__()
        self.on_change_model = on_change_model
        self.on_change_device = on_change_device
        self.on_toggle_sound = on_toggle_sound
        self.on_toggle_lock = on_toggle_lock
        self.on_toggle_restore = on_toggle_restore
        self.on_test_hud = on_test_hud
        self.on_exit_app = on_exit_app

        self.current_model = initial_model
        self.current_device_idx = initial_device_idx
        self.sound_enabled = sound_enabled
        self.lock_enabled = lock_enabled
        self.restore_window_enabled = restore_window_enabled
        self.device_list = device_list or []
        self.config_path = config_path

        self.setWindowTitle("Speech-to-Text Studio | בקרת תמלול קולי")
        self.resize(720, 620)
        self.setMinimumSize(600, 500)

        # Connect signals
        self.sig_update_key_event.connect(self._slot_update_key_event)
        self.sig_update_audio_rms.connect(self._slot_update_audio_rms)
        self.sig_dictation_received.connect(self._slot_dictation_received)

        self._apply_theme()
        self._build_ui()

    def _apply_theme(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0F121C;
                color: #F3F4F6;
            }
            QWidget {
                color: #E2E8F0;
                font-family: 'Segoe UI', 'Segoe UI Variable', system-ui, sans-serif;
                font-size: 13px;
            }
            QGroupBox {
                background-color: #161B29;
                border: 1px solid #232D42;
                border-radius: 10px;
                margin-top: 14px;
                padding-top: 14px;
                font-weight: 600;
                color: #94A3B8;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 14px;
                padding: 0 6px;
                color: #60A5FA;
            }
            QLabel {
                color: #CBD5E1;
            }
            QComboBox {
                background-color: #1F273B;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 6px 12px;
                color: #F8FAFC;
                min-height: 20px;
            }
            QComboBox:hover {
                border-color: #3B82F6;
            }
            QComboBox::drop-down {
                border: none;
                width: 24px;
            }
            QComboBox QAbstractItemView {
                background-color: #1F273B;
                border: 1px solid #334155;
                color: #F8FAFC;
                selection-background-color: #2563EB;
            }
            QCheckBox {
                spacing: 8px;
                color: #CBD5E1;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 1px solid #475569;
                background-color: #1E293B;
            }
            QCheckBox::indicator:checked {
                background-color: #2563EB;
                border-color: #3B82F6;
            }
            QTextEdit {
                background-color: #131722;
                border: 1px solid #252F47;
                border-radius: 8px;
                padding: 10px;
                color: #F1F5F9;
                font-size: 14px;
                selection-background-color: #2563EB;
            }
            QPushButton {
                background-color: #1E293B;
                color: #F8FAFC;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #283548;
                border-color: #475569;
            }
            QPushButton:pressed {
                background-color: #0F172A;
            }
            QPushButton#primaryBtn {
                background-color: #2563EB;
                border: 1px solid #3B82F6;
                color: #FFFFFF;
                font-weight: 600;
            }
            QPushButton#primaryBtn:hover {
                background-color: #1D4ED8;
            }
            QPushButton#dangerBtn {
                background-color: rgba(239, 68, 68, 0.15);
                border: 1px solid rgba(239, 68, 68, 0.4);
                color: #F87171;
            }
            QPushButton#dangerBtn:hover {
                background-color: rgba(239, 68, 68, 0.25);
            }
        """)

    def _build_ui(self):
        central_widget = QtWidgets.QWidget(self)
        self.setCentralWidget(central_widget)

        main_layout = QtWidgets.QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 18, 20, 18)
        main_layout.setSpacing(14)

        # 1. Header Card (Status & GPU Engine)
        header_card = QtWidgets.QFrame()
        header_card.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #1E293B, stop:1 #172033);
                border: 1px solid #334155;
                border-radius: 12px;
                padding: 12px;
            }
        """)
        h_layout = QtWidgets.QHBoxLayout(header_card)
        h_layout.setContentsMargins(12, 10, 12, 10)

        # Status icon & text
        v_status = QtWidgets.QVBoxLayout()
        status_row = QtWidgets.QHBoxLayout()
        dot = QtWidgets.QLabel("●")
        dot.setStyleSheet("color: #10B981; font-size: 18px; font-weight: bold;")
        title = QtWidgets.QLabel("שירות תמלול פעיל ומאזין ברקע")
        title.setStyleSheet("color: #FFFFFF; font-size: 16px; font-weight: bold;")
        status_row.addWidget(dot)
        status_row.addWidget(title)
        status_row.addStretch()

        subtitle = QtWidgets.QLabel("NVIDIA GeForce RTX 5060 Ti | CUDA FP16 | מודל: Faster-Whisper")
        subtitle.setStyleSheet("color: #94A3B8; font-size: 12px;")
        v_status.addLayout(status_row)
        v_status.addWidget(subtitle)
        h_layout.addLayout(v_status)
        h_layout.addStretch()

        btn_hud_test = QtWidgets.QPushButton("הצג HUD Dynamic Island")
        btn_hud_test.clicked.connect(self.on_test_hud)
        h_layout.addWidget(btn_hud_test)

        main_layout.addWidget(header_card)

        # 2. Live Diagnostics Row: Key Monitor & Mic Meter
        diag_layout = QtWidgets.QHBoxLayout()
        diag_layout.setSpacing(12)

        # Box 1: Hotkey Monitor
        key_group = QtWidgets.QGroupBox("ניטור מקש חם (Hotkey Monitor)")
        v_key = QtWidgets.QVBoxLayout(key_group)
        v_key.setContentsMargins(14, 14, 14, 14)
        v_key.setSpacing(6)

        lbl_configured = QtWidgets.QLabel("מקש מוגדר: Right Alt / Fn / Right Ctrl")
        lbl_configured.setStyleSheet("color: #94A3B8; font-size: 12px;")
        v_key.addWidget(lbl_configured)

        self.key_status_label = QtWidgets.QLabel("ממתין להקשה... (הקש על Right Alt לבדיקה)")
        self.key_status_label.setStyleSheet("""
            background-color: #111420;
            border: 1px dashed #334155;
            border-radius: 6px;
            padding: 8px;
            color: #64748B;
            font-size: 12px;
        """)
        self.key_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v_key.addWidget(self.key_status_label)
        diag_layout.addWidget(key_group, 1)

        # Box 2: Audio Level Meter
        mic_group = QtWidgets.QGroupBox("מד עוצמת שמע מיקרופון (Live Audio Meter)")
        v_mic = QtWidgets.QVBoxLayout(mic_group)
        v_mic.setContentsMargins(14, 14, 14, 14)
        v_mic.setSpacing(8)

        self.mic_name_label = QtWidgets.QLabel("מיקרופון פעיל: ברירת מחדל של Windows")
        self.mic_name_label.setStyleSheet("color: #94A3B8; font-size: 12px;")
        v_mic.addWidget(self.mic_name_label)

        self.volume_meter = ModernProgressBar()
        v_mic.addWidget(self.volume_meter)
        diag_layout.addWidget(mic_group, 1)

        main_layout.addLayout(diag_layout)

        # 3. Live Test Dictation Sandbox
        sandbox_group = QtWidgets.QGroupBox("אזור בדיקת הכתבה חי (Live Dictation Sandbox)")
        v_sandbox = QtWidgets.QVBoxLayout(sandbox_group)
        v_sandbox.setContentsMargins(14, 12, 14, 14)
        v_sandbox.setSpacing(8)

        tip_lbl = QtWidgets.QLabel("💡 החזק Right Alt / Fn ודבר בעברית או באנגלית. הטקסט יוקלד כאן או בכל תוכנה אחרת:")
        tip_lbl.setStyleSheet("color: #A5B4FC; font-size: 12px;")
        v_sandbox.addWidget(tip_lbl)

        self.test_text_area = QtWidgets.QTextEdit()
        self.test_text_area.setPlaceholderText("הטקסט המתומלל יופיע כאן בזמן אמת...")
        self.test_text_area.setMinimumHeight(110)
        v_sandbox.addWidget(self.test_text_area)

        # Clear text button
        btn_clear = QtWidgets.QPushButton("נקה טקסט")
        btn_clear.setFixedWidth(100)
        btn_clear.clicked.connect(lambda: self.test_text_area.clear())
        v_sandbox.addWidget(btn_clear, alignment=Qt.AlignmentFlag.AlignRight)

        main_layout.addWidget(sandbox_group)

        # 4. Settings Grid
        settings_group = QtWidgets.QGroupBox("הגדרות מהירות (Quick Settings)")
        v_sett = QtWidgets.QVBoxLayout(settings_group)
        v_sett.setContentsMargins(14, 12, 14, 14)
        v_sett.setSpacing(10)

        # Dropdowns row
        drop_layout = QtWidgets.QHBoxLayout()
        drop_layout.setSpacing(14)

        # Model selector
        v_m = QtWidgets.QVBoxLayout()
        v_m.addWidget(QtWidgets.QLabel("מודל תמלול Faster-Whisper:"))
        self.model_combo = QtWidgets.QComboBox()
        for m in ["small", "base", "medium", "large-v3-turbo", "tiny"]:
            label = f"{m} (מומלץ ומהיר)" if m == "small" else m
            self.model_combo.addItem(label, m)
        idx = self.model_combo.findData(self.current_model)
        if idx >= 0:
            self.model_combo.setCurrentIndex(idx)
        self.model_combo.currentIndexChanged.connect(self._on_model_changed)
        v_m.addWidget(self.model_combo)
        drop_layout.addLayout(v_m, 1)

        # Audio device selector
        v_d = QtWidgets.QVBoxLayout()
        v_d.addWidget(QtWidgets.QLabel("מיקרופון קלט:"))
        self.device_combo = QtWidgets.QComboBox()
        self.device_combo.addItem("ברירת מחדל של המערכת", None)
        for dev_idx, dev_name in self.device_list:
            self.device_combo.addItem(f"[{dev_idx}] {dev_name}", dev_idx)
        self.device_combo.currentIndexChanged.connect(self._on_device_changed)
        v_d.addWidget(self.device_combo)
        drop_layout.addLayout(v_d, 2)

        v_sett.addLayout(drop_layout)

        # Checkboxes row
        chk_layout = QtWidgets.QHBoxLayout()
        chk_layout.setSpacing(18)

        self.chk_sound = QtWidgets.QCheckBox("צלילי חיווי בהתחלה וסיום")
        self.chk_sound.setChecked(self.sound_enabled)
        self.chk_sound.toggled.connect(self.on_toggle_sound)
        chk_layout.addWidget(self.chk_sound)

        self.chk_lock = QtWidgets.QCheckBox("נעילה בלחיצה כפולה (דיבור חופשי)")
        self.chk_lock.setChecked(self.lock_enabled)
        self.chk_lock.toggled.connect(self.on_toggle_lock)
        chk_layout.addWidget(self.chk_lock)

        self.chk_restore = QtWidgets.QCheckBox("שמירת חלון יעד מקורי")
        self.chk_restore.setChecked(self.restore_window_enabled)
        self.chk_restore.toggled.connect(self.on_toggle_restore)
        chk_layout.addWidget(self.chk_restore)

        chk_layout.addStretch()
        v_sett.addLayout(chk_layout)

        main_layout.addWidget(settings_group)

        # 5. Bottom Action Bar
        action_layout = QtWidgets.QHBoxLayout()
        action_layout.setSpacing(10)

        btn_open_cfg = QtWidgets.QPushButton("ערוך config.yaml")
        btn_open_cfg.clicked.connect(self._open_config_file)
        action_layout.addWidget(btn_open_cfg)

        action_layout.addStretch()

        btn_minimize = QtWidgets.QPushButton("מזער למגש המערכת (Minimize to Tray)")
        btn_minimize.setObjectName("primaryBtn")
        btn_minimize.clicked.connect(self.hide_to_tray)
        action_layout.addWidget(btn_minimize)

        btn_exit = QtWidgets.QPushButton("יציאה מלאה (Exit)")
        btn_exit.setObjectName("dangerBtn")
        btn_exit.clicked.connect(self.on_exit_app)
        action_layout.addWidget(btn_exit)

        main_layout.addLayout(action_layout)

    def _on_model_changed(self):
        selected_model = self.model_combo.currentData()
        if selected_model:
            self.current_model = selected_model
            self.on_change_model(selected_model)

    def _on_device_changed(self):
        selected_idx = self.device_combo.currentData()
        self.current_device_idx = selected_idx
        self.on_change_device(selected_idx)
        dev_name = self.device_combo.currentText()
        self.mic_name_label.setText(f"מיקרופון פעיל: {dev_name}")

    def _open_config_file(self):
        try:
            if os.path.exists(self.config_path):
                os.startfile(os.path.abspath(self.config_path))
        except Exception as e:
            logger.error(f"Error opening config: {e}")

    def update_device_list(self, devices: List[tuple[int, str]]):
        self.device_list = devices
        self.device_combo.blockSignals(True)
        self.device_combo.clear()
        self.device_combo.addItem("ברירת מחדל של המערכת", None)
        for dev_idx, dev_name in devices:
            self.device_combo.addItem(f"[{dev_idx}] {dev_name}", dev_idx)
        self.device_combo.blockSignals(False)

    @pyqtSlot(str, bool)
    def _slot_update_key_event(self, key_desc: str, is_trigger: bool):
        if is_trigger:
            self.key_status_label.setText(f"✓ זוהה מקש חם: {key_desc} (פעיל!)")
            self.key_status_label.setStyleSheet("""
                background-color: rgba(16, 185, 129, 0.2);
                border: 1px solid #10B981;
                border-radius: 6px;
                padding: 8px;
                color: #34D399;
                font-size: 12px;
                font-weight: bold;
            """)
        else:
            self.key_status_label.setText(f"הקשה נקלטה: {key_desc}")
            self.key_status_label.setStyleSheet("""
                background-color: rgba(59, 130, 246, 0.15);
                border: 1px solid #3B82F6;
                border-radius: 6px;
                padding: 8px;
                color: #93C5FD;
                font-size: 12px;
            """)

    @pyqtSlot(float)
    def _slot_update_audio_rms(self, rms: float):
        percent = int(min(1.0, rms * 15.0) * 100)
        self.volume_meter.setValue(percent)

    @pyqtSlot(str)
    def _slot_dictation_received(self, text: str):
        if text.strip():
            self.test_text_area.append(text.strip())

    def hide_to_tray(self):
        """Hides the control window to tray while keeping service alive."""
        self.hide()

    def closeEvent(self, event):
        """Intercepts window close button to minimize to tray instead of quitting."""
        event.ignore()
        self.hide_to_tray()
