"""
ui/widgets.py
Reusable custom widgets for the FaceSearch Pro application.
"""
from PyQt6.QtWidgets import (
    QLabel, QFrame, QHBoxLayout, QVBoxLayout, QWidget,
    QPushButton, QSizePolicy, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QPixmap, QImage, QColor, QPainter, QPen, QFont, QBrush
import os

from .styles import *


class PhotoLabel(QLabel):
    """A QLabel that displays a photo with a scan-line overlay effect."""

    def __init__(self, placeholder_text="NO IMAGE", size=(200, 220), parent=None):
        super().__init__(parent)
        self._size = size
        self.setFixedSize(*size)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setText(placeholder_text)
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {BG_DARKEST};
                color: {TEXT_DIM};
                border: 1px solid {BORDER_LIGHT};
                font-family: Consolas;
                font-size: 11px;
                letter-spacing: 2px;
            }}
        """)
        self._scanning = False
        self._scan_y = 0
        self._timer = QTimer()
        self._timer.timeout.connect(self._tick_scan)

    def set_photo_bytes(self, data: bytes):
        if not data:
            self.clear_photo()
            return
        pix = QPixmap()
        pix.loadFromData(data)
        if not pix.isNull():
            pix = pix.scaled(self._size[0], self._size[1],
                             Qt.AspectRatioMode.KeepAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)
            self.setPixmap(pix)
            self.setText("")
        else:
            self.clear_photo()

    def set_photo_path(self, path: str):
        pix = QPixmap(path)
        if not pix.isNull():
            pix = pix.scaled(self._size[0], self._size[1],
                             Qt.AspectRatioMode.KeepAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)
            self.setPixmap(pix)
            self.setText("")
        else:
            self.clear_photo()

    def clear_photo(self):
        self.clear()
        self.setText("NO IMAGE")

    def start_scan(self):
        self._scanning = True
        self._scan_y = 0
        self._timer.start(16)
        self.update()

    def stop_scan(self):
        self._scanning = False
        self._timer.stop()
        self.update()

    def _tick_scan(self):
        self._scan_y = (self._scan_y + 3) % self._size[1]
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._scanning:
            painter = QPainter(self)
            # Scanline
            pen = QPen(QColor(0, 200, 255, 120))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawLine(0, self._scan_y, self._size[0], self._scan_y)
            # Gradient fade above scanline
            for i in range(20):
                alpha = int(40 * (1 - i / 20))
                painter.setPen(QPen(QColor(0, 200, 255, alpha)))
                y = self._scan_y - i
                if y >= 0:
                    painter.drawLine(0, y, self._size[0], y)
            # Corner brackets
            painter.setPen(QPen(QColor(0, 200, 255, 200), 2))
            m, ln = 8, 16
            for cx, cy in [(m, m), (self._size[0]-m, m),
                           (m, self._size[1]-m), (self._size[0]-m, self._size[1]-m)]:
                # horizontal
                dx = ln if cx < self._size[0] // 2 else -ln
                painter.drawLine(cx, cy, cx + dx, cy)
                # vertical
                dy = ln if cy < self._size[1] // 2 else -ln
                painter.drawLine(cx, cy, cx, cy + dy)
            painter.end()


class StatusBadge(QLabel):
    """Coloured pill-shaped status badge."""

    def __init__(self, status: str = "", parent=None):
        super().__init__(parent)
        self.set_status(status)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedHeight(20)

    def set_status(self, status: str):
        if not status:
            self.setText("")
            self.setStyleSheet("background: transparent; border: none;")
            return
        fg, bg = status_colors(status)
        self.setText(status.upper())
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {bg};
                color: {fg};
                border: 1px solid {fg};
                border-radius: 3px;
                padding: 1px 8px;
                font-family: Consolas;
                font-size: 10px;
                font-weight: bold;
                letter-spacing: 1px;
            }}
        """)


class SectionHeader(QWidget):
    """Dark tactical section header with a coloured accent line."""

    def __init__(self, title: str, accent: str = ACCENT_BLUE, parent=None):
        super().__init__(parent)
        self.setFixedHeight(32)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(8)

        # Accent bar
        bar = QFrame()
        bar.setFixedSize(3, 16)
        bar.setStyleSheet(f"background: {accent}; border: none;")

        lbl = QLabel(title.upper())
        lbl.setStyleSheet(f"""
            color: {accent};
            font-family: Consolas;
            font-size: 10px;
            font-weight: bold;
            letter-spacing: 2px;
            background: transparent;
            border: none;
        """)

        layout.addWidget(bar)
        layout.addWidget(lbl)
        layout.addStretch()

        self.setStyleSheet(f"""
            QWidget {{
                background-color: {BG_PANEL};
                border-bottom: 1px solid {BORDER};
                border-top: none;
                border-left: none;
                border-right: none;
            }}
        """)


class InfoRow(QWidget):
    """Key–value row used in detail panels."""

    def __init__(self, label: str, value: str = "", parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(8)

        lbl = QLabel(label + ":")
        lbl.setFixedWidth(110)
        lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px; background: transparent; border: none;")

        self.val_lbl = QLabel(value)
        self.val_lbl.setStyleSheet(f"color: {TEXT_WHITE}; font-size: 11px; background: transparent; border: none;")
        self.val_lbl.setWordWrap(True)

        layout.addWidget(lbl)
        layout.addWidget(self.val_lbl, 1)
        self.setStyleSheet("background: transparent; border: none;")

    def set_value(self, value: str):
        self.val_lbl.setText(str(value))


class ConfidenceBar(QWidget):
    """Horizontal confidence percentage bar."""

    def __init__(self, confidence: float = 0.0, parent=None):
        super().__init__(parent)
        self.setFixedHeight(22)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(6)

        from PyQt6.QtWidgets import QProgressBar
        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(int(confidence))
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(6)

        pct = QLabel(f"{confidence:.1f}%")
        pct.setFixedWidth(48)
        pct.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        pct.setStyleSheet(f"color: {ACCENT_CYAN}; font-size: 11px; background: transparent; border: none;")

        c = ACCENT_GREEN if confidence >= 80 else ACCENT_BLUE if confidence >= 60 else ACCENT_AMBER
        self._bar.setStyleSheet(f"""
            QProgressBar {{ background: {BG_DARKEST}; border: 1px solid {BORDER}; border-radius: 2px; }}
            QProgressBar::chunk {{ background: {c}; border-radius: 2px; }}
        """)

        layout.addWidget(self._bar, 1)
        layout.addWidget(pct)
        self.setStyleSheet("background: transparent; border: none;")


class MatchCard(QFrame):
    """Compact card widget showing a face-match result."""
    clicked = pyqtSignal(int)   # emits person DB id

    def __init__(self, record: dict, parent=None):
        super().__init__(parent)
        self._id = record.get('id', -1)
        self.setFixedHeight(90)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._build_ui(record)
        self._set_normal_style()

    def _build_ui(self, record):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        # Thumbnail
        self.photo = PhotoLabel("?", (60, 70))
        if record.get('photo_blob'):
            self.photo.set_photo_bytes(record['photo_blob'])

        # Info
        info = QVBoxLayout()
        info.setSpacing(2)

        name_lbl = QLabel(record.get('full_name', 'Unknown'))
        name_lbl.setStyleSheet(f"color: {TEXT_WHITE}; font-size: 12px; font-weight: bold; background: transparent; border: none;")

        id_lbl = QLabel(f"ID: {record.get('id_number', '')}")
        id_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 10px; background: transparent; border: none;")

        self.badge = StatusBadge(record.get('status', ''))

        conf = record.get('confidence', None)
        if conf is not None:
            self.conf_bar = ConfidenceBar(conf)
            conf_lbl = QLabel(f"MATCH  {conf:.1f}%")
            conf_lbl.setStyleSheet(f"color: {ACCENT_CYAN}; font-size: 10px; background: transparent; border: none;")
            info.addWidget(conf_lbl)
        
        info.addWidget(name_lbl)
        info.addWidget(id_lbl)
        info.addWidget(self.badge)
        info.addStretch()

        layout.addWidget(self.photo)
        layout.addLayout(info, 1)

    def _set_normal_style(self):
        self.setStyleSheet(f"""
            MatchCard {{
                background-color: {BG_CARD};
                border: 1px solid {BORDER};
                border-radius: 4px;
            }}
            MatchCard:hover {{
                border-color: {ACCENT_BLUE};
                background-color: {BG_HOVER};
            }}
        """)

    def set_selected(self, selected: bool):
        if selected:
            self.setStyleSheet(f"""
                MatchCard {{
                    background-color: {BG_HOVER};
                    border: 1px solid {ACCENT_BLUE};
                    border-left: 3px solid {ACCENT_CYAN};
                    border-radius: 4px;
                }}
            """)
        else:
            self._set_normal_style()

    def mousePressEvent(self, event):
        self.clicked.emit(self._id)
        super().mousePressEvent(event)


class PulsingDot(QLabel):
    """Animated status indicator dot."""

    def __init__(self, color: str = ACCENT_GREEN, parent=None):
        super().__init__("●", parent)
        self._color = color
        self._alpha = 255
        self._dir = -5
        self._timer = QTimer()
        self._timer.timeout.connect(self._pulse)
        self._timer.start(50)
        self.setStyleSheet(f"color: {color}; font-size: 10px; background: transparent; border: none;")

    def _pulse(self):
        self._alpha += self._dir
        if self._alpha <= 80:
            self._dir = 5
        elif self._alpha >= 255:
            self._dir = -5
        c = QColor(self._color)
        c.setAlpha(self._alpha)
        hex_c = f"rgba({c.red()},{c.green()},{c.blue()},{self._alpha})"
        self.setStyleSheet(f"color: {hex_c}; font-size: 10px; background: transparent; border: none;")
