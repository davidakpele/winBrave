"""
ui/search_panel.py
Left panel: query image upload / webcam capture, search controls, filter options.
"""
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QSlider, QGroupBox, QFileDialog,
    QFrame, QSizePolicy, QSpacerItem
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QObject
from PyQt6.QtGui import QPixmap

from .styles import *
from .widgets import PhotoLabel, SectionHeader, PulsingDot


class SearchWorker(QObject):
    """Runs face search in a background thread."""
    finished = pyqtSignal(list)
    error    = pyqtSignal(str)

    def __init__(self, image_bytes: bytes, tolerance: float):
        super().__init__()
        self._bytes = image_bytes
        self._tol = tolerance

    def run(self):
        try:
            from core.face_engine import encode_face_from_bytes, find_best_match, is_available
            from database.db_manager import get_all_encodings

            if not is_available():
                self.error.emit(
                    "face_recognition library not found.\n\n"
                    "Install it with:\n  pip install face_recognition\n\n"
                    "(Requires cmake + Visual Studio Build Tools on Windows)"
                )
                return

            enc = encode_face_from_bytes(self._bytes)
            if enc is None:
                self.error.emit("No face detected in the uploaded image.\nPlease use a clear frontal photo.")
                return

            db_records = get_all_encodings()
            if not db_records:
                self.error.emit("No face encodings in database.\nAdd persons with photos first.")
                return

            results = find_best_match(db_records, enc, tolerance=self._tol)
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))


class SearchPanel(QWidget):
    search_requested  = pyqtSignal(bytes, float)   # image bytes, tolerance
    text_search       = pyqtSignal(str)
    results_ready     = pyqtSignal(list)
    search_error      = pyqtSignal(str)
    status_message    = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._image_bytes: bytes = None
        self._thread = None
        self._worker = None
        self._build_ui()

    # ── Build ──────────────────────────────────────────────────────────────────
    def _build_ui(self):
        self.setFixedWidth(300)
        self.setStyleSheet(f"background-color: {BG_PANEL}; border-right: 1px solid {BORDER};")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        hdr = SectionHeader("  FACIAL RECOGNITION SEARCH", ACCENT_BLUE)
        root.addWidget(hdr)

        # Content area
        content = QWidget()
        content.setStyleSheet(f"background: transparent; border: none;")
        cl = QVBoxLayout(content)
        cl.setContentsMargins(12, 12, 12, 12)
        cl.setSpacing(10)

        # --- Photo drop zone ---
        self.photo_lbl = PhotoLabel("CLICK TO LOAD\nQUERY IMAGE", (276, 260))
        self.photo_lbl.setCursor(Qt.CursorShape.PointingHandCursor)
        self.photo_lbl.mousePressEvent = lambda e: self._pick_image()
        cl.addWidget(self.photo_lbl)

        # Status label under photo
        self.img_status = QLabel("No image loaded")
        self.img_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.img_status.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 10px; background: transparent; border: none;")
        cl.addWidget(self.img_status)

        # --- Filters group ---
        filt_group = QGroupBox("SEARCH FILTERS")
        fg_layout = QVBoxLayout(filt_group)
        fg_layout.setSpacing(8)

        # Tolerance slider
        tol_lbl = QLabel("MATCH TOLERANCE")
        tol_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 10px; letter-spacing: 1px; background: transparent; border: none;")
        fg_layout.addWidget(tol_lbl)

        tol_row = QHBoxLayout()
        self.tol_slider = QSlider(Qt.Orientation.Horizontal)
        self.tol_slider.setRange(30, 75)
        self.tol_slider.setValue(55)
        self.tol_val_lbl = QLabel("0.55")
        self.tol_val_lbl.setFixedWidth(32)
        self.tol_val_lbl.setStyleSheet(f"color: {ACCENT_CYAN}; font-size: 11px; background: transparent; border: none;")
        self.tol_slider.valueChanged.connect(
            lambda v: self.tol_val_lbl.setText(f"{v/100:.2f}")
        )
        tol_row.addWidget(self.tol_slider, 1)
        tol_row.addWidget(self.tol_val_lbl)
        fg_layout.addLayout(tol_row)

        # Status filter
        stat_lbl = QLabel("STATUS FILTER")
        stat_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 10px; letter-spacing: 1px; background: transparent; border: none;")
        fg_layout.addWidget(stat_lbl)

        self.status_filter = QComboBox()
        self.status_filter.addItems([
            "All Records", "Felony Warrant", "Arrest Record",
            "Under Investigation", "Interpol Notice",
            "Person of Interest", "Witness", "No Record"
        ])
        fg_layout.addWidget(self.status_filter)

        cl.addWidget(filt_group)

        # --- Text search ---
        text_group = QGroupBox("TEXT SEARCH")
        tg_layout = QVBoxLayout(text_group)
        tg_layout.setSpacing(6)

        self.text_input = QLineEdit()
        self.text_input.setPlaceholderText("Name, ID, nationality...")
        self.text_input.returnPressed.connect(self._do_text_search)
        tg_layout.addWidget(self.text_input)

        txt_btn = QPushButton("SEARCH DATABASE")
        txt_btn.clicked.connect(self._do_text_search)
        tg_layout.addWidget(txt_btn)

        cl.addWidget(text_group)

        cl.addStretch()

        # --- Action buttons ---
        self.search_btn = QPushButton("▶  RUN FACE SEARCH")
        self.search_btn.setObjectName("btn_primary")
        self.search_btn.setFixedHeight(36)
        self.search_btn.clicked.connect(self._do_face_search)
        self.search_btn.setEnabled(False)
        cl.addWidget(self.search_btn)

        self.clear_btn = QPushButton("CLEAR")
        self.clear_btn.clicked.connect(self._clear)
        cl.addWidget(self.clear_btn)

        # Progress indicator
        prog_row = QHBoxLayout()
        self._dot = PulsingDot(ACCENT_AMBER)
        self._dot.hide()
        self._proc_lbl = QLabel("")
        self._proc_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 10px; background: transparent; border: none;")
        prog_row.addWidget(self._dot)
        prog_row.addWidget(self._proc_lbl, 1)
        cl.addLayout(prog_row)

        root.addWidget(content, 1)

        # --- Bottom status bar ---
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
        sb_layout = QHBoxLayout(status_bar)
        sb_layout.setContentsMargins(10, 0, 10, 0)

        dot = PulsingDot(ACCENT_GREEN)
        sys_lbl = QLabel("SYSTEM: ONLINE")
        sys_lbl.setStyleSheet(f"color: {ACCENT_GREEN}; font-size: 10px; background: transparent; border: none;")
        sb_layout.addWidget(dot)
        sb_layout.addWidget(sys_lbl)
        sb_layout.addStretch()
        root.addWidget(status_bar)

    # ── Slots ──────────────────────────────────────────────────────────────────
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
        self._dot.show()
        self._proc_lbl.setText("Analyzing biometrics...")
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
        self._dot.hide()
        self._proc_lbl.setText("")
        self.search_btn.setEnabled(True)

        status = self.status_filter.currentText()
        if status != "All Records":
            results = [r for r in results if r.get('status') == status]

        self.results_ready.emit(results)
        self.status_message.emit(f"{len(results)} match(es) found")

    def _on_error(self, msg: str):
        self._dot.hide()
        self._proc_lbl.setText("")
        self.search_btn.setEnabled(True)
        self.search_error.emit(msg)
        self.status_message.emit("Search error")

    def _do_text_search(self):
        q = self.text_input.text().strip()
        if q:
            self.text_search.emit(q)
            self.status_message.emit(f"Text search: '{q}'")

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
