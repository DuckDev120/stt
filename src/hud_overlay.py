"""
Dynamic Island HUD Overlay in PyQt6.
Floats at the top center of the screen (under webcam), slides down smoothly on push-to-talk,
displays a glowing pulsing mic, dynamic waveform, and live bilingual transcription preview.
Uses WS_EX_NOACTIVATE so it NEVER steals focus from the user's active application.
"""

import ctypes
import sys
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QPoint, pyqtSignal, pyqtSlot

# Win32 Constants for non-activating window
GWL_EXSTYLE = -20
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_TOPMOST = 0x00000008


class WaveformWidget(QtWidgets.QWidget):
    """Mini audio visualizer bars responsive to speech volume."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(60, 24)
        self.amplitude = 0.0
        self.bar_count = 5
        self.bar_heights = [4.0] * self.bar_count
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self._animate_bars)
        self.timer.start(30)  # ~33 fps

    def set_amplitude(self, amp: float):
        self.amplitude = max(0.0, min(1.0, amp))

    def _animate_bars(self):
        import random
        for i in range(self.bar_count):
            target = 4.0 + self.amplitude * 18.0 * (0.6 + 0.8 * random.random())
            # Smooth interpolation
            self.bar_heights[i] += (target - self.bar_heights[i]) * 0.35
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        bar_w = 4
        spacing = 5
        start_x = (w - (self.bar_count * bar_w + (self.bar_count - 1) * spacing)) / 2

        for i in range(self.bar_count):
            bh = max(3.0, min(float(h), self.bar_heights[i]))
            x = start_x + i * (bar_w + spacing)
            y = (h - bh) / 2

            # Red-to-pink gradient for active recording
            grad = QtGui.QLinearGradient(x, y, x, y + bh)
            grad.setColorAt(0.0, QtGui.QColor(255, 75, 90))
            grad.setColorAt(1.0, QtGui.QColor(255, 140, 100))

            painter.setBrush(QtGui.QBrush(grad))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(QtCore.QRectF(x, y, bar_w, bh), 2.0, 2.0)


class DynamicIslandHUD(QtWidgets.QWidget):
    # Signals for thread-safe cross-thread communication
    sig_show = pyqtSignal()
    sig_hide = pyqtSignal()
    sig_show_welcome = pyqtSignal(str, int)  # message, duration_ms
    sig_update_partial = pyqtSignal(str)
    sig_update_status = pyqtSignal(str, str)  # status_text, color
    sig_update_rms = pyqtSignal(float)

    def __init__(self, width: int = 520, height: int = 58, top_margin: int = 12, anim_duration: int = 200):
        super().__init__()
        self.hud_width = width
        self.hud_height = height
        self.top_margin = top_margin
        self.anim_duration = anim_duration
        self._welcome_timer = QtCore.QTimer(self)
        self._welcome_timer.setSingleShot(True)
        self._welcome_timer.timeout.connect(self._slot_hide)

        self.setFixedSize(self.hud_width, self.hud_height)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        self._apply_win32_noactivate()
        self._build_ui()
        self._setup_animation()

        # Connect signals to internal slots
        self.sig_show.connect(self._slot_show)
        self.sig_hide.connect(self._slot_hide)
        self.sig_show_welcome.connect(self._slot_show_welcome)
        self.sig_update_partial.connect(self._slot_update_partial)
        self.sig_update_status.connect(self._slot_update_status)
        self.sig_update_rms.connect(self._slot_update_rms)

        self._position_offscreen()

    def _apply_win32_noactivate(self):
        """Ensures the window never activates or steals focus on Windows OS."""
        try:
            hwnd = int(self.winId())
            user32 = ctypes.windll.user32
            cur_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            new_style = cur_style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW | WS_EX_TOPMOST
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_style)
        except Exception:
            pass

    def _build_ui(self):
        self.main_layout = QtWidgets.QHBoxLayout(self)
        self.main_layout.setContentsMargins(16, 8, 16, 8)
        self.main_layout.setSpacing(12)

        # 1. Pulsing Mic Icon
        self.mic_dot = QtWidgets.QLabel()
        self.mic_dot.setFixedSize(14, 14)
        self.mic_dot.setStyleSheet(
            "background-color: #ff3355; border-radius: 7px; border: 2px solid rgba(255, 255, 255, 0.4);"
        )
        self.main_layout.addWidget(self.mic_dot)

        # 2. Waveform Visualizer
        self.waveform = WaveformWidget(self)
        self.main_layout.addWidget(self.waveform)

        # 3. Live Transcribed Text (supports bi-directional Hebrew and English)
        self.text_label = QtWidgets.QLabel("האזנה...")
        self.text_label.setStyleSheet(
            "color: #F1F3F5; font-size: 13px; font-weight: 500; font-family: 'Segoe UI', 'Segoe UI Variable', sans-serif;"
        )
        self.text_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeading)
        self.text_label.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Preferred)
        self.main_layout.addWidget(self.text_label)

        # 4. State Badge
        self.badge = QtWidgets.QLabel("REC")
        self.badge.setStyleSheet(
            "color: #ff5577; background-color: rgba(255, 50, 80, 0.18); border-radius: 8px; padding: 3px 8px; font-size: 10px; font-weight: bold;"
        )
        self.main_layout.addWidget(self.badge)

    def paintEvent(self, event):
        """Draws the glassmorphic pill background with subtle glow and gradient border."""
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

        rect = QtCore.QRectF(1, 1, self.width() - 2, self.height() - 2)

        # Background dark pill
        bg_brush = QtGui.QBrush(QtGui.QColor(16, 18, 26, 235))
        painter.setBrush(bg_brush)

        # Border gradient
        border_pen = QtGui.QPen(QtGui.QColor(255, 255, 255, 38), 1.2)
        painter.setPen(border_pen)

        painter.drawRoundedRect(rect, 24.0, 24.0)

    def _setup_animation(self):
        self.anim = QPropertyAnimation(self, b"pos")
        self.anim.setDuration(self.anim_duration)

    def _get_screen_coords(self) -> tuple[int, int, int]:
        screen = QtGui.QGuiApplication.primaryScreen().geometry()
        x = int((screen.width() - self.hud_width) / 2)
        target_y = self.top_margin
        offscreen_y = -self.hud_height - 10
        return x, target_y, offscreen_y

    def _position_offscreen(self):
        x, _, offscreen_y = self._get_screen_coords()
        self.move(x, offscreen_y)

    @pyqtSlot()
    def _slot_show(self):
        if self._welcome_timer.isActive():
            self._welcome_timer.stop()

        self.mic_dot.setStyleSheet(
            "background-color: #ff3355; border-radius: 7px; border: 2px solid rgba(255, 255, 255, 0.4);"
        )
        x, target_y, offscreen_y = self._get_screen_coords()
        self.text_label.setText("מקליט... (שחרר לסיום)")
        self.badge.setText("REC")
        self.badge.setStyleSheet(
            "color: #ff5577; background-color: rgba(255, 50, 80, 0.18); border-radius: 8px; padding: 3px 8px; font-size: 10px; font-weight: bold;"
        )
        self.waveform.set_amplitude(0.1)

        self.anim.stop()
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.anim.setStartValue(QPoint(x, offscreen_y))
        self.anim.setEndValue(QPoint(x, target_y))

        self.show()
        self._apply_win32_noactivate()
        self.anim.start()

    @pyqtSlot(str, int)
    def _slot_show_welcome(self, message: str, duration_ms: int):
        if self._welcome_timer.isActive():
            self._welcome_timer.stop()

        self.mic_dot.setStyleSheet(
            "background-color: #10B981; border-radius: 7px; border: 2px solid rgba(255, 255, 255, 0.6);"
        )
        x, target_y, offscreen_y = self._get_screen_coords()
        self.text_label.setText(message)
        self.badge.setText("READY")
        self.badge.setStyleSheet(
            "color: #10B981; background-color: rgba(16, 185, 129, 0.18); border-radius: 8px; padding: 3px 8px; font-size: 10px; font-weight: bold;"
        )
        self.waveform.set_amplitude(0.0)

        self.anim.stop()
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.anim.setStartValue(QPoint(x, offscreen_y))
        self.anim.setEndValue(QPoint(x, target_y))

        self.show()
        self._apply_win32_noactivate()
        self.anim.start()

        if duration_ms > 0:
            self._welcome_timer.start(duration_ms)

    @pyqtSlot()
    def _slot_hide(self):
        x, target_y, offscreen_y = self._get_screen_coords()
        self.anim.stop()
        self.anim.setEasingCurve(QEasingCurve.Type.InCubic)
        self.anim.setStartValue(self.pos())
        self.anim.setEndValue(QPoint(x, offscreen_y))

        def _on_finish():
            self.hide()
            try:
                self.anim.finished.disconnect(_on_finish)
            except Exception:
                pass

        self.anim.finished.connect(_on_finish)
        self.anim.start()

    @pyqtSlot(str)
    def _slot_update_partial(self, text: str):
        if text.strip():
            self.text_label.setText(text)

    @pyqtSlot(str, str)
    def _slot_update_status(self, status_text: str, color: str):
        self.badge.setText(status_text)
        self.badge.setStyleSheet(
            f"color: {color}; background-color: rgba(255, 255, 255, 0.12); border-radius: 8px; padding: 3px 8px; font-size: 10px; font-weight: bold;"
        )

    @pyqtSlot(float)
    def _slot_update_rms(self, rms: float):
        # Scale amplitude for visualizer
        norm_amp = min(1.0, rms * 10.0)
        self.waveform.set_amplitude(norm_amp)

    def show_welcome(self, message: str = "🎙️ שירות הכתבה פעיל! החזק Right Alt או Fn כדי להכתיב", duration_ms: int = 3500):
        """Thread-safe request to slide down welcome banner."""
        self.sig_show_welcome.emit(message, duration_ms)
