"""
ui/search_panel.py
Left panel: query image upload, search controls, scan animation.
"""
import os
import time
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QSlider, QGroupBox, QFileDialog,
    QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QObject, QTimer, QRect
from PyQt6.QtGui import QPixmap, QPainter, QPen, QColor, QFont

from .styles import *
from .widgets import SectionHeader, PulsingDot


class ScanPhotoLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(276, 260)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setText("CLICK TO LOAD\nQUERY IMAGE")
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {BG_DARKEST};
                color: {TEXT_DIM};
                border: 2px dashed {BORDER_LIGHT};
                font-family: Consolas;
                font-size: 11px;
                letter-spacing: 2px;
            }}
        """)
        self._scanning   = False
        self._scan_y     = 0
        self._scan_dir   = 1
        self._grid_alpha = 40
        self._grid_dir   = 1
        self._timer      = QTimer()
        self._timer.timeout.connect(self._tick)

    def set_photo_path(self, path: str):
        pix = QPixmap(path)
        if not pix.isNull():
            pix = pix.scaled(276, 260,
                             Qt.AspectRatioMode.KeepAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)
            self.setPixmap(pix)
            self.setText("")
            self.setStyleSheet(f"QLabel {{ background-color: {BG_DARKEST}; border: 1px solid {ACCENT_BLUE}; }}")

    def clear_photo(self):
        self.clear()
        self.setText("CLICK TO LOAD\nQUERY IMAGE")
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {BG_DARKEST};
                color: {TEXT_DIM};
                border: 2px dashed {BORDER_LIGHT};
                font-family: Consolas;
                font-size: 11px;
                letter-spacing: 2px;
            }}
        """)
        self.stop_scan()

    def start_scan(self):
        self._scanning   = True
        self._scan_y     = 0
        self._scan_dir   = 1
        self._grid_alpha = 40
        self._grid_dir   = 1
        self.setStyleSheet(f"QLabel {{ background-color: {BG_DARKEST}; border: 1px solid {ACCENT_CYAN}; }}")
        self._timer.start(18)

    def stop_scan(self):
        self._scanning = False
        self._timer.stop()
        self.update()

    def _tick(self):
        self._scan_y += self._scan_dir * 4
        if self._scan_y >= self.height():
            self._scan_dir = -1
        elif self._scan_y <= 0:
            self._scan_dir = 1
        self._grid_alpha = max(20, min(80, self._grid_alpha + self._grid_dir * 2))
        if self._grid_alpha >= 80:
            self._grid_dir = -1
        elif self._grid_alpha <= 20:
            self._grid_dir = 1
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self._scanning:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        painter.setPen(QPen(QColor(0, 200, 255, self._grid_alpha), 1))
        for x in range(0, w, 24):
            painter.drawLine(x, 0, x, h)
        for y in range(0, h, 24):
            painter.drawLine(0, y, w, y)
        for i in range(30):
            alpha = int(180 * (1 - i / 30))
            y = self._scan_y - i * self._scan_dir
            if 0 <= y <= h:
                painter.setPen(QPen(QColor(0, 220, 255, alpha), 1))
                painter.drawLine(0, y, w, y)
        painter.setPen(QPen(QColor(0, 240, 255, 230), 2))
        painter.drawLine(0, self._scan_y, w, self._scan_y)
        painter.setPen(QPen(QColor(0, 220, 255, 230), 2))
        m, ln = 10, 20
        for cx, cy in [(m, m), (w-m, m), (m, h-m), (w-m, h-m)]:
            dx = ln if cx < w // 2 else -ln
            dy = ln if cy < h // 2 else -ln
            painter.drawLine(cx, cy, cx + dx, cy)
            painter.drawLine(cx, cy, cx, cy + dy)
        cx = w // 2
        painter.setPen(QPen(QColor(0, 255, 200, 160), 1))
        painter.drawLine(cx - 14, self._scan_y, cx + 14, self._scan_y)
        painter.drawLine(cx, self._scan_y - 8, cx, self._scan_y + 8)
        painter.setPen(QPen(QColor(0, 220, 255, 200)))
        painter.setFont(QFont("Consolas", 8))
        painter.drawText(QRect(0, h - 20, w, 20),
                         Qt.AlignmentFlag.AlignCenter,
                         "ANALYZING BIOMETRICS...")
        painter.end()


class SearchWorker(QObject):
    finished = pyqtSignal(list)
    error    = pyqtSignal(str)

    def __init__(self, image_bytes: bytes, tolerance: float):
        super().__init__()
        self._bytes = image_bytes
        self._tol   = tolerance

    def run(self):
        try:
            from core.face_engine import encode_face_from_bytes, find_best_match, is_available
            from database.db_manager import get_all_encodings

            if not is_available():
                self.error.emit("Face engine unavailable. Check model files.")
                return

            enc = encode_face_from_bytes(self._bytes)
            if enc is None:
                self.error.emit("No face detected in the uploaded image.\nPlease use a clear frontal photo.")
                return

            db_records = get_all_encodings()
            if not db_records:
                self.error.emit("No face encodings in database.\nAdd persons with photos first.")
                return

            # 5 second scan delay
            time.sleep(5)

            results = find_best_match(db_records, enc, tolerance=self._tol)
            self.finished.emit(results)
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.error.emit(str(e))


class SearchPanel(QWidget):
    search_requested = pyqtSignal(bytes, float)
    text_search      = pyqtSignal(str)
    results_ready    = pyqtSignal(list)
    search_error     = pyqtSignal(str)
    status_message   = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._image_bytes = None
        self._thread      = None
        self._worker      = None
        self._build_ui()

    def _build_ui(self):
        self.setFixedWidth(300)
        self.setStyleSheet(f"background-color: {BG_PANEL}; border-right: 1px solid {BORDER};")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(SectionHeader("  FACIAL RECOGNITION SEARCH", ACCENT_BLUE))

        content = QWidget()
        content.setStyleSheet("background: transparent; border: none;")
        cl = QVBoxLayout(content)
        cl.setContentsMargins(12, 12, 12, 12)
        cl.setSpacing(10)

        self.photo_lbl = ScanPhotoLabel()
        self.photo_lbl.setCursor(Qt.CursorShape.PointingHandCursor)
        self.photo_lbl.mousePressEvent = lambda e: self._pick_image()
        cl.addWidget(self.photo_lbl)

        self.img_status = QLabel("No image loaded")
        self.img_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.img_status.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 10px; background: transparent; border: none;")
        cl.addWidget(self.img_status)

        filt_group = QGroupBox("SEARCH FILTERS")
        fg = QVBoxLayout(filt_group)
        fg.setSpacing(8)
        tol_lbl = QLabel("MATCH TOLERANCE")
        tol_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 10px; letter-spacing: 1px; background: transparent; border: none;")
        fg.addWidget(tol_lbl)
        tol_row = QHBoxLayout()
        self.tol_slider = QSlider(Qt.Orientation.Horizontal)
        self.tol_slider.setRange(30, 75)
        self.tol_slider.setValue(55)
        self.tol_val_lbl = QLabel("0.55")
        self.tol_val_lbl.setFixedWidth(32)
        self.tol_val_lbl.setStyleSheet(f"color: {ACCENT_CYAN}; font-size: 11px; background: transparent; border: none;")
        self.tol_slider.valueChanged.connect(lambda v: self.tol_val_lbl.setText(f"{v/100:.2f}"))
        tol_row.addWidget(self.tol_slider, 1)
        tol_row.addWidget(self.tol_val_lbl)
        fg.addLayout(tol_row)
        stat_lbl = QLabel("STATUS FILTER")
        stat_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 10px; letter-spacing: 1px; background: transparent; border: none;")
        fg.addWidget(stat_lbl)
        self.status_filter = QComboBox()
        self.status_filter.addItems([
            "All Records", "Felony Warrant", "Arrest Record",
            "Under Investigation", "Interpol Notice",
            "Person of Interest", "Witness", "No Record"
        ])
        fg.addWidget(self.status_filter)
        cl.addWidget(filt_group)

        text_group = QGroupBox("TEXT SEARCH")
        tg = QVBoxLayout(text_group)
        tg.setSpacing(6)
        self.text_input = QLineEdit()
        self.text_input.setPlaceholderText("Name, ID, nationality...")
        self.text_input.returnPressed.connect(self._do_text_search)
        tg.addWidget(self.text_input)
        txt_btn = QPushButton("SEARCH DATABASE")
        txt_btn.clicked.connect(self._do_text_search)
        tg.addWidget(txt_btn)
        cl.addWidget(text_group)

        cl.addStretch()

        self.search_btn = QPushButton("▶  RUN FACE SEARCH")
        self.search_btn.setFixedHeight(44)
        self.search_btn.setEnabled(False)
        self.search_btn.clicked.connect(self._do_face_search)
        self.search_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #0d2a42, stop:1 #1a4a6e);
                color: {ACCENT_CYAN};
                border: 2px solid {ACCENT_BLUE};
                border-radius: 4px;
                font-family: Consolas;
                font-size: 13px;
                font-weight: bold;
                letter-spacing: 3px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {ACCENT_BLUE}, stop:1 #1a7abf);
                color: white;
                border-color: {ACCENT_CYAN};
            }}
            QPushButton:pressed {{ background: {ACCENT_CYAN}; color: {BG_DARKEST}; }}
            QPushButton:disabled {{ background: {BG_DARKEST}; color: {TEXT_DIM}; border: 2px solid {BORDER}; }}
        """)
        cl.addWidget(self.search_btn)

        self.clear_btn = QPushButton("CLEAR")
        self.clear_btn.clicked.connect(self._clear)
        cl.addWidget(self.clear_btn)

        prog_row = QHBoxLayout()
        self._dot = PulsingDot(ACCENT_AMBER)
        self._dot.hide()
        self._proc_lbl = QLabel("")
        self._proc_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 10px; background: transparent; border: none;")
        prog_row.addWidget(self._dot)
        prog_row.addWidget(self._proc_lbl, 1)
        cl.addLayout(prog_row)

        root.addWidget(content, 1)

        status_bar = QFrame()
        status_bar.setFixedHeight(28)
        status_bar.setStyleSheet(f"""
            QFrame {{
                background-color: {BG_DARKEST};
                border-top: 1px solid {BORDER};
                border-bottom: none; border-left: none; border-right: none;
                border-radius: 0;
            }}
        """)
        sb = QHBoxLayout(status_bar)
        sb.setContentsMargins(10, 0, 10, 0)
        dot = PulsingDot(ACCENT_GREEN)
        sys_lbl = QLabel("SYSTEM: ONLINE")
        sys_lbl.setStyleSheet(f"color: {ACCENT_GREEN}; font-size: 10px; background: transparent; border: none;")
        sb.addWidget(dot)
        sb.addWidget(sys_lbl)
        sb.addStretch()
        root.addWidget(status_bar)

    def _pick_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Query Image", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.webp)"
        )
        if not path:
            return
        with open(path, 'rb') as f:
            self._image_bytes = f.read()
        self.photo_lbl.set_photo_path(path)
        self.img_status.setText(f"✓ {os.path.basename(path)}")
        self.img_status.setStyleSheet(f"color: {ACCENT_GREEN}; font-size: 10px; background: transparent; border: none;")
        self.search_btn.setEnabled(True)

    def _do_face_search(self):
        if not self._image_bytes:
            return
        tol = self.tol_slider.value() / 100.0
        self.search_btn.setEnabled(False)
        self.clear_btn.setEnabled(False)
        self._dot.show()
        self._proc_lbl.setText("Scanning biometrics...")
        self.photo_lbl.start_scan()
        self.status_message.emit("Running facial recognition scan...")

        self._thread = QThread()
        self._worker = SearchWorker(self._image_bytes, tol)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_results)
        self._worker.error.connect(self._on_error)
        self._worker.finished.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)
        self._thread.start()

    def _on_results(self, results: list):
        self.photo_lbl.stop_scan()
        self._dot.hide()
        self._proc_lbl.setText("")
        self.search_btn.setEnabled(True)
        self.clear_btn.setEnabled(True)
        status = self.status_filter.currentText()
        if status != "All Records":
            results = [r for r in results if r.get('status') == status]
        self.results_ready.emit(results)
        self.status_message.emit("1 match found" if results else "No match found")

    def _on_error(self, msg: str):
        self.photo_lbl.stop_scan()
        self._dot.hide()
        self._proc_lbl.setText("")
        self.search_btn.setEnabled(True)
        self.clear_btn.setEnabled(True)
        self.search_error.emit(msg)
        self.status_message.emit("Search error")

    def _do_text_search(self):
        q = self.text_input.text().strip()
        if q:
            self.text_search.emit(q)

    def _clear(self):
        self._image_bytes = None
        self.photo_lbl.clear_photo()
        self.img_status.setText("No image loaded")
        self.img_status.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 10px; background: transparent; border: none;")
        self.search_btn.setEnabled(False)
        self._proc_lbl.setText("")
        self._dot.hide()
        self.text_input.clear()
        self.status_message.emit("Cleared")