"""
ui/search_panel.py
Left panel: query image upload, search controls, scan animation.
- 5-second result delay with countdown
- Deep scan mode: detects face bounding box and focuses scan overlay on it
"""
import os
import time
import numpy as np
import cv2

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QSlider, QGroupBox, QFileDialog,
    QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QObject, QTimer, QRect
from PyQt6.QtGui import QPixmap, QPainter, QPen, QColor, QFont, QBrush

from .styles import *
from .widgets import SectionHeader, PulsingDot


# ─────────────────────────────────────────────────────────────────────────────
#  Scan photo label — animated scan overlay, face-box aware
# ─────────────────────────────────────────────────────────────────────────────

class ScanPhotoLabel(QLabel):
    """
    Photo display with animated scan overlay during search.
    When a face bounding box is provided via set_face_box(), the scan
    animation collapses to focus exclusively on the face region.
    """

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
        self._scanning    = False
        self._scan_y      = 0
        self._scan_dir    = 1
        self._grid_alpha  = 40
        self._grid_dir    = 1
        self._face_box    = None   # (x, y, w, h) in widget coords
        self._deep_phase  = False  # True = scanning inside face box only
        self._phase_lbl   = "ANALYZING BIOMETRICS..."
        self._countdown   = 0      # seconds remaining displayed top-right
        self._timer       = QTimer()
        self._timer.timeout.connect(self._tick)

    # ── Photo helpers ─────────────────────────────────────────────────────────

    def set_photo_bytes(self, data: bytes):
        pix = QPixmap()
        pix.loadFromData(data)
        if not pix.isNull():
            pix = pix.scaled(276, 260,
                             Qt.AspectRatioMode.KeepAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)
            self.setPixmap(pix)
            self.setText("")
            self.setStyleSheet(
                f"QLabel {{ background-color: {BG_DARKEST}; border: 1px solid {BORDER_LIGHT}; }}"
            )

    def set_photo_path(self, path: str):
        pix = QPixmap(path)
        if not pix.isNull():
            pix = pix.scaled(276, 260,
                             Qt.AspectRatioMode.KeepAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)
            self.setPixmap(pix)
            self.setText("")
            self.setStyleSheet(
                f"QLabel {{ background-color: {BG_DARKEST}; border: 1px solid {ACCENT_BLUE}; }}"
            )

    def clear_photo(self):
        self.clear()
        self._face_box   = None
        self._deep_phase = False
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

    # ── Face box ──────────────────────────────────────────────────────────────

    def set_face_box(self, box):
        """
        box: (x, y, w, h) in widget pixel coordinates, or None.
        Call before start_scan() or mid-scan to switch to deep mode.
        """
        self._face_box   = box
        self._deep_phase = box is not None

    def set_countdown(self, seconds: int):
        self._countdown = seconds
        self.update()

    # ── Scan control ──────────────────────────────────────────────────────────

    def start_scan(self):
        self._scanning   = True
        self._scan_y     = 0
        self._scan_dir   = 1
        self._grid_alpha = 40
        self._grid_dir   = 1
        self._phase_lbl  = "SCANNING IMAGE..."
        self.setStyleSheet(
            f"QLabel {{ background-color: {BG_DARKEST}; border: 1px solid {ACCENT_CYAN}; }}"
        )
        self._timer.start(18)

    def enter_deep_scan(self):
        """Switch overlay to face-only deep-scan mode."""
        self._deep_phase = True
        self._phase_lbl  = "DEEP FACE SCAN..."
        if self._face_box:
            self._scan_y   = self._face_box[1]
            self._scan_dir = 1

    def stop_scan(self):
        self._scanning   = False
        self._deep_phase = False
        self._countdown  = 0
        self._timer.stop()
        self.update()

    # ── Animation tick ────────────────────────────────────────────────────────

    def _tick(self):
        if self._deep_phase and self._face_box:
            fx, fy, fw, fh = self._face_box
            self._scan_y += self._scan_dir * 3
            if self._scan_y >= fy + fh:
                self._scan_dir = -1
            elif self._scan_y <= fy:
                self._scan_dir = 1
        else:
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

    # ── Custom paint ──────────────────────────────────────────────────────────

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self._scanning:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        if self._deep_phase and self._face_box:
            self._paint_deep_scan(painter, w, h)
        else:
            self._paint_full_scan(painter, w, h)

        # Countdown badge — top-right corner
        if self._countdown > 0:
            painter.setPen(QPen(QColor(0, 220, 255, 220)))
            painter.setFont(QFont("Consolas", 9, QFont.Weight.Bold))
            painter.drawText(
                QRect(w - 48, 4, 44, 18),
                Qt.AlignmentFlag.AlignRight,
                f"{self._countdown}s"
            )

        painter.end()

    def _paint_full_scan(self, painter, w, h):
        """Original full-image scan animation."""
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

        cxm = w // 2
        painter.setPen(QPen(QColor(0, 255, 200, 160), 1))
        painter.drawLine(cxm - 14, self._scan_y, cxm + 14, self._scan_y)
        painter.drawLine(cxm, self._scan_y - 8, cxm, self._scan_y + 8)

        painter.setPen(QPen(QColor(0, 220, 255, 200)))
        painter.setFont(QFont("Consolas", 8))
        painter.drawText(
            QRect(0, h - 20, w, 20),
            Qt.AlignmentFlag.AlignCenter,
            self._phase_lbl
        )

    def _paint_deep_scan(self, painter, w, h):
        """
        Deep scan: dims everything outside the face box, draws an intense
        focused scan animation inside the face region only.
        """
        fx, fy, fw, fh = self._face_box

        # Dark overlay outside face box
        painter.setBrush(QBrush(QColor(0, 0, 0, 150)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(0,        0,        w,          fy)           # above
        painter.drawRect(0,        fy + fh,  w,          h - fy - fh) # below
        painter.drawRect(0,        fy,       fx,         fh)           # left
        painter.drawRect(fx + fw,  fy,       w - fx - fw, fh)          # right

        # Fine grid inside face box
        painter.setPen(QPen(QColor(0, 255, 180, self._grid_alpha + 20), 1))
        for x in range(fx, fx + fw, 12):
            painter.drawLine(x, fy, x, fy + fh)
        for y in range(fy, fy + fh, 12):
            painter.drawLine(fx, y, fx + fw, y)

        # Scan trail inside face box
        for i in range(20):
            alpha = int(200 * (1 - i / 20))
            y = self._scan_y - i * self._scan_dir
            if fy <= y <= fy + fh:
                painter.setPen(QPen(QColor(0, 255, 180, alpha), 1))
                painter.drawLine(fx, y, fx + fw, y)

        # Main scan line (bright inside face)
        painter.setPen(QPen(QColor(0, 255, 160, 240), 2))
        painter.drawLine(fx, self._scan_y, fx + fw, self._scan_y)

        # Glowing face bounding box border
        glow = 180 + int(60 * abs((self._scan_y - fy) / max(fh, 1) - 0.5) * 2)
        painter.setPen(QPen(QColor(0, 255, 140, min(glow, 255)), 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(fx, fy, fw, fh)

        # Corner brackets on face box
        painter.setPen(QPen(QColor(0, 255, 200, 240), 3))
        ln = 14
        for cx, cy in [(fx, fy), (fx+fw, fy), (fx, fy+fh), (fx+fw, fy+fh)]:
            dx = ln if cx == fx else -ln
            dy = ln if cy == fy else -ln
            painter.drawLine(cx, cy, cx + dx, cy)
            painter.drawLine(cx, cy, cx, cy + dy)

        # Crosshair at face center
        face_cx = fx + fw // 2
        face_cy = fy + fh // 2
        painter.setPen(QPen(QColor(0, 255, 180, 100), 1))
        painter.drawLine(fx, face_cy, fx + fw, face_cy)
        painter.drawLine(face_cx, fy, face_cx, fy + fh)

        # Scan crosshair on moving line
        painter.setPen(QPen(QColor(0, 255, 160, 220), 2))
        painter.drawLine(face_cx - 10, self._scan_y, face_cx + 10, self._scan_y)
        painter.drawLine(face_cx, self._scan_y - 6, face_cx, self._scan_y + 6)

        # Status text
        painter.setPen(QPen(QColor(0, 255, 160, 220)))
        painter.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
        painter.drawText(
            QRect(0, h - 20, w, 20),
            Qt.AlignmentFlag.AlignCenter,
            self._phase_lbl
        )


# ─────────────────────────────────────────────────────────────────────────────
#  Search worker — runs in a background QThread
# ─────────────────────────────────────────────────────────────────────────────

class SearchWorker(QObject):
    finished     = pyqtSignal(list)
    error        = pyqtSignal(str)
    face_located = pyqtSignal(int, int, int, int)  # x, y, w, h in image space
    countdown    = pyqtSignal(int)                  # seconds remaining

    def __init__(self, image_bytes: bytes, tolerance: float):
        super().__init__()
        self._bytes = image_bytes
        self._tol   = tolerance

    def run(self):
        try:
            from core.face_engine import (
                find_best_match, is_available, _load_models,
                _detect_and_crop_face, _embed_face_crop
            )
            from database.db_manager import get_all_encodings
            import core.face_engine as _fe

            if not is_available():
                self.error.emit("Face engine unavailable. Check model files.")
                return

            # ── Step 1: Decode image ──────────────────────────────────────────
            arr = np.frombuffer(self._bytes, dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if img is None:
                self.error.emit("Could not decode image.")
                return

            ih, iw = img.shape[:2]

            # ── Step 2: Detect face + emit box for UI overlay ─────────────────
            scale   = 600.0 / max(ih, iw)
            new_w   = int(iw * scale)
            new_h   = int(ih * scale)
            resized = cv2.resize(img, (new_w, new_h))
            blob    = cv2.dnn.blobFromImage(
                resized, 1.0, (new_w, new_h), (104.0, 177.0, 123.0)
            )
            _fe._detector.setInput(blob)
            detections = _fe._detector.forward()

            best_conf = 0.0
            best_box  = None
            for i in range(detections.shape[2]):
                conf = float(detections[0, 0, i, 2])
                if conf > best_conf:
                    best_conf = conf
                    box = detections[0, 0, i, 3:7] * np.array([iw, ih, iw, ih])
                    best_box = box.astype(int)

            if best_conf < 0.50 or best_box is None:
                self.error.emit(
                    "No face detected in the uploaded image.\n"
                    "Please use a clear frontal photo."
                )
                return

            x1, y1, x2, y2 = best_box
            pad_x = int((x2 - x1) * 0.10)
            pad_y = int((y2 - y1) * 0.10)
            x1 = max(0, x1 - pad_x)
            y1 = max(0, y1 - pad_y)
            x2 = min(iw, x2 + pad_x)
            y2 = min(ih, y2 + pad_y)

            # Signal the UI to switch to face-focused deep scan
            self.face_located.emit(x1, y1, x2 - x1, y2 - y1)

            # ── Step 3: Embed face crop only ──────────────────────────────────
            face_crop = img[y1:y2, x1:x2]
            if face_crop.size == 0:
                self.error.emit("Face crop was empty. Try a different photo.")
                return
            enc = _fe._embed_face_crop(face_crop)

            # ── Step 4: 5-second countdown ────────────────────────────────────
            for secs_left in range(5, 0, -1):
                self.countdown.emit(secs_left)
                time.sleep(1)
            self.countdown.emit(0)

            # ── Step 5: Match against DB ──────────────────────────────────────
            db_records = get_all_encodings()
            if not db_records:
                self.error.emit(
                    "No face encodings in database.\nAdd persons with photos first."
                )
                return

            results = find_best_match(db_records, enc, tolerance=self._tol)
            self.finished.emit(results)

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.error.emit(str(e))


# ─────────────────────────────────────────────────────────────────────────────
#  Search panel widget
# ─────────────────────────────────────────────────────────────────────────────

class SearchPanel(QWidget):
    search_requested = pyqtSignal(bytes, float)
    text_search      = pyqtSignal(str)
    results_ready    = pyqtSignal(list)
    search_error     = pyqtSignal(str)
    status_message   = pyqtSignal(str)

    _PHOTO_W = 276   # ScanPhotoLabel display width
    _PHOTO_H = 260   # ScanPhotoLabel display height

    def __init__(self, parent=None):
        super().__init__(parent)
        self._image_bytes = None
        self._image_size  = None   # (orig_w, orig_h)
        self._thread      = None
        self._worker      = None
        self._build_ui()

    def _build_ui(self):
        self.setFixedWidth(300)
        self.setStyleSheet(
            f"background-color: {BG_PANEL}; border-right: 1px solid {BORDER};"
        )

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
        self.img_status.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: 10px; background: transparent; border: none;"
        )
        cl.addWidget(self.img_status)

        # Filters
        filt_group = QGroupBox("SEARCH FILTERS")
        fg = QVBoxLayout(filt_group)
        fg.setSpacing(8)

        tol_lbl = QLabel("MATCH TOLERANCE")
        tol_lbl.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: 10px; letter-spacing: 1px; "
            f"background: transparent; border: none;"
        )
        fg.addWidget(tol_lbl)

        tol_row = QHBoxLayout()
        self.tol_slider = QSlider(Qt.Orientation.Horizontal)
        self.tol_slider.setRange(30, 75)
        self.tol_slider.setValue(55)
        self.tol_val_lbl = QLabel("0.55")
        self.tol_val_lbl.setFixedWidth(32)
        self.tol_val_lbl.setStyleSheet(
            f"color: {ACCENT_CYAN}; font-size: 11px; background: transparent; border: none;"
        )
        self.tol_slider.valueChanged.connect(
            lambda v: self.tol_val_lbl.setText(f"{v/100:.2f}")
        )
        tol_row.addWidget(self.tol_slider, 1)
        tol_row.addWidget(self.tol_val_lbl)
        fg.addLayout(tol_row)

        stat_lbl = QLabel("STATUS FILTER")
        stat_lbl.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: 10px; letter-spacing: 1px; "
            f"background: transparent; border: none;"
        )
        fg.addWidget(stat_lbl)
        self.status_filter = QComboBox()
        self.status_filter.addItems([
            "All Records", "Felony Warrant", "Arrest Record",
            "Under Investigation", "Interpol Notice",
            "Person of Interest", "Witness", "No Record"
        ])
        fg.addWidget(self.status_filter)
        cl.addWidget(filt_group)

        # Text search
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
            QPushButton:disabled {{
                background: {BG_DARKEST}; color: {TEXT_DIM};
                border: 2px solid {BORDER};
            }}
        """)
        cl.addWidget(self.search_btn)

        self.clear_btn = QPushButton("CLEAR")
        self.clear_btn.clicked.connect(self._clear)
        cl.addWidget(self.clear_btn)

        prog_row = QHBoxLayout()
        self._dot = PulsingDot(ACCENT_AMBER)
        self._dot.hide()
        self._proc_lbl = QLabel("")
        self._proc_lbl.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: 10px; background: transparent; border: none;"
        )
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
        sys_lbl.setStyleSheet(
            f"color: {ACCENT_GREEN}; font-size: 10px; background: transparent; border: none;"
        )
        sb.addWidget(dot)
        sb.addWidget(sys_lbl)
        sb.addStretch()
        root.addWidget(status_bar)

    # ── Image selection ───────────────────────────────────────────────────────

    def _pick_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Query Image", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.webp)"
        )
        if not path:
            return
        with open(path, 'rb') as f:
            self._image_bytes = f.read()

        arr = np.frombuffer(self._image_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is not None:
            self._image_size = (img.shape[1], img.shape[0])

        self.photo_lbl.set_photo_path(path)
        self.img_status.setText(f"✓ {os.path.basename(path)}")
        self.img_status.setStyleSheet(
            f"color: {ACCENT_GREEN}; font-size: 10px; background: transparent; border: none;"
        )
        self.search_btn.setEnabled(True)

    # ── Face search ───────────────────────────────────────────────────────────

    def _do_face_search(self):
        if not self._image_bytes:
            return
        tol = self.tol_slider.value() / 100.0

        self.search_btn.setEnabled(False)
        self.clear_btn.setEnabled(False)
        self._dot.show()
        self._proc_lbl.setText("Locating face...")
        self.photo_lbl.start_scan()
        self.status_message.emit("Running facial recognition scan...")

        self._thread = QThread()
        self._worker = SearchWorker(self._image_bytes, tol)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.face_located.connect(self._on_face_located)
        self._worker.countdown.connect(self._on_countdown)
        self._worker.finished.connect(self._on_results)
        self._worker.error.connect(self._on_error)
        self._worker.finished.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)

        self._thread.start()

    def _on_face_located(self, ix, iy, iw, ih):
        """
        Scale image-space face box → widget-space, then switch to deep scan.
        """
        if self._image_size is None:
            return
        orig_w, orig_h = self._image_size
        scale  = min(self._PHOTO_W / orig_w, self._PHOTO_H / orig_h)
        disp_w = int(orig_w * scale)
        disp_h = int(orig_h * scale)
        off_x  = (self._PHOTO_W - disp_w) // 2
        off_y  = (self._PHOTO_H - disp_h) // 2

        wx = int(ix * scale) + off_x
        wy = int(iy * scale) + off_y
        ww = int(iw * scale)
        wh = int(ih * scale)

        self.photo_lbl.set_face_box((wx, wy, ww, wh))
        self.photo_lbl.enter_deep_scan()
        self._proc_lbl.setText("Deep scanning face...")
        self.status_message.emit("Face located — running deep scan...")

    def _on_countdown(self, secs: int):
        self.photo_lbl.set_countdown(secs)
        if secs > 0:
            self._proc_lbl.setText(f"Matching biometrics... {secs}s")
        else:
            self._proc_lbl.setText("Finalising results...")

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
        self.status_message.emit(
            f"{len(results)} match(es) found" if results else "No match found"
        )

    def _on_error(self, msg: str):
        self.photo_lbl.stop_scan()
        self._dot.hide()
        self._proc_lbl.setText("")
        self.search_btn.setEnabled(True)
        self.clear_btn.setEnabled(True)
        self.search_error.emit(msg)
        self.status_message.emit("Search error")

    # ── Text search ───────────────────────────────────────────────────────────

    def _do_text_search(self):
        q = self.text_input.text().strip()
        if q:
            self.text_search.emit(q)

    # ── Clear ─────────────────────────────────────────────────────────────────

    def _clear(self):
        self._image_bytes = None
        self._image_size  = None
        self.photo_lbl.clear_photo()
        self.img_status.setText("No image loaded")
        self.img_status.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: 10px; background: transparent; border: none;"
        )
        self.search_btn.setEnabled(False)
        self._proc_lbl.setText("")
        self._dot.hide()
        self.text_input.clear()
        self.status_message.emit("Cleared")