"""
ui/search_panel.py
Deep scan overlay: dense poly-mesh shaped as a face oval — no bounding box,
mesh points follow the face silhouette exactly like the reference image.
"""
import os
import time
import math
import random
import numpy as np
import cv2

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QSlider, QGroupBox, QFileDialog, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QObject, QTimer, QRect, QRectF, QPointF
from PyQt6.QtGui import (QPixmap, QPainter, QPen, QColor, QFont,
                          QBrush, QPainterPath, QPolygonF, QRadialGradient)

from .styles import *
from .widgets import SectionHeader, PulsingDot


# ---------------------------------------------------------------------------
#  Face-shaped point cloud — points follow the face oval silhouette
#  All coordinates normalised 0..1 within the face bounding box.
#  cx=0.5 is face centre, cy=0 is top of forehead, cy=1 is chin tip.
# ---------------------------------------------------------------------------

def _make_face_pts():
    pts = []

    # ── Outer silhouette — face oval (head shape) ──────────────────────────
    # Top of head is narrower, jaw widens then tapers to chin
    silhouette = [
        (0.50, 0.00),   # top forehead
        (0.38, 0.03), (0.62, 0.03),
        (0.26, 0.10), (0.74, 0.10),
        (0.16, 0.20), (0.84, 0.20),
        (0.10, 0.32), (0.90, 0.32),
        (0.08, 0.46), (0.92, 0.46),
        (0.10, 0.58), (0.90, 0.58),
        (0.14, 0.68), (0.86, 0.68),
        (0.20, 0.76), (0.80, 0.76),
        (0.30, 0.84), (0.70, 0.84),
        (0.40, 0.90), (0.60, 0.90),
        (0.50, 0.95),   # chin tip
    ]
    pts.extend(silhouette)

    # ── Mid layer — inside the face oval ──────────────────────────────────
    mid = [
        (0.50, 0.06),
        (0.32, 0.12), (0.68, 0.12),
        (0.20, 0.22), (0.80, 0.22),
        (0.14, 0.35), (0.86, 0.35),
        (0.14, 0.50), (0.86, 0.50),
        (0.18, 0.63), (0.82, 0.63),
        (0.25, 0.74), (0.75, 0.74),
        (0.36, 0.82), (0.64, 0.82),
        (0.50, 0.87),
    ]
    pts.extend(mid)

    # ── Inner face detail — eyes, nose, mouth zone ────────────────────────
    inner = [
        # forehead zone
        (0.38, 0.16), (0.50, 0.14), (0.62, 0.16),
        # brow level
        (0.28, 0.26), (0.38, 0.24), (0.50, 0.23), (0.62, 0.24), (0.72, 0.26),
        # eye level
        (0.28, 0.34), (0.36, 0.32), (0.44, 0.31), (0.50, 0.32),
        (0.56, 0.31), (0.64, 0.32), (0.72, 0.34),
        # eye centres (glow points)
        (0.36, 0.37), (0.64, 0.37),
        # nose bridge
        (0.50, 0.40), (0.44, 0.43), (0.56, 0.43),
        # nose tip
        (0.50, 0.50), (0.42, 0.52), (0.58, 0.52),
        # cheek level
        (0.22, 0.44), (0.78, 0.44),
        (0.24, 0.54), (0.76, 0.54),
        # mouth zone
        (0.36, 0.60), (0.44, 0.58), (0.50, 0.57),
        (0.56, 0.58), (0.64, 0.60),
        (0.38, 0.65), (0.50, 0.66), (0.62, 0.65),
        # chin zone
        (0.42, 0.72), (0.50, 0.74), (0.58, 0.72),
        (0.50, 0.80),
    ]
    pts.extend(inner)

    return pts

_FACE_PTS_NORM = _make_face_pts()


def _mesh_points(cx, cy, size, jitter=0.0):
    """
    Map normalised face points into widget coords.
    cx, cy = centre of face in widget coords
    size   = diameter (width=height of bounding box)
    """
    half = size / 2.0
    pts = []
    for nx, ny in _FACE_PTS_NORM:
        # nx/ny are 0..1 within the face box
        x = (cx - half) + nx * size + (random.uniform(-jitter, jitter) if jitter else 0)
        y = (cy - half) + ny * size + (random.uniform(-jitter, jitter) if jitter else 0)
        pts.append(QPointF(x, y))
    return pts


def _triangulate(pts_qf):
    """Delaunay triangulation → (edges, triangles)."""
    if len(pts_qf) < 3:
        return [], []
    try:
        from scipy.spatial import Delaunay
        arr = np.array([(p.x(), p.y()) for p in pts_qf])
        tri = Delaunay(arr)
        tris = tri.simplices.tolist()
    except Exception:
        tris = []
    edges = set()
    for a, b, c in tris:
        for e in [(min(a,b),max(a,b)),(min(b,c),max(b,c)),(min(a,c),max(a,c))]:
            edges.add(e)
    return list(edges), tris


# Pre-compute static topology on unit points
_static_unit = [QPointF(nx, ny) for nx, ny in _FACE_PTS_NORM]
_STATIC_EDGES, _STATIC_TRIS = _triangulate(_static_unit)

# Special glow node indices (eye centres)
_EYE_L_IDX = next((i for i,(nx,ny) in enumerate(_FACE_PTS_NORM) if abs(nx-0.36)<0.01 and abs(ny-0.37)<0.01), None)
_EYE_R_IDX = next((i for i,(nx,ny) in enumerate(_FACE_PTS_NORM) if abs(nx-0.64)<0.01 and abs(ny-0.37)<0.01), None)


# ---------------------------------------------------------------------------
#  ScanPhotoLabel
# ---------------------------------------------------------------------------

class ScanPhotoLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(276, 260)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._reset_text()

        self._scanning   = False
        self._no_face    = False
        self._face_cx    = 0
        self._face_cy    = 0
        self._face_size  = 0
        self._deep_phase = False
        self._phase_lbl  = "SCANNING..."
        self._countdown  = 0
        self._mesh_alpha = 0
        self._mesh_pts   = []
        self._scan_y     = 0
        self._scan_dir   = 1
        self._grid_alpha = 40
        self._grid_dir   = 1
        self._frame      = 0
        self._pulse      = 0.0
        self._pulse_dir  = 1

        self._timer = QTimer()
        self._timer.timeout.connect(self._tick)

    def _reset_text(self):
        self.clear()
        self.setText("CLICK TO LOAD\nQUERY IMAGE")
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {BG_DARKEST};
                color: {TEXT_DIM};
                border: 2px dashed {BORDER_LIGHT};
                font-family: Consolas; font-size: 11px; letter-spacing: 2px;
            }}
        """)

    def set_photo_path(self, path):
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
        self._face_size  = 0
        self._deep_phase = False
        self._no_face    = False
        self._mesh_pts   = []
        self._mesh_alpha = 0
        self._reset_text()
        self.stop_scan()

    def set_face_center(self, cx, cy, size):
        """cx, cy = centre in widget coords, size = mesh diameter."""
        self._face_cx   = cx
        self._face_cy   = cy
        self._face_size = size
        self._deep_phase = False
        self._no_face    = False

    def show_no_face(self):
        self._no_face  = True
        self._scanning = False
        self._timer.stop()
        self.setStyleSheet(
            f"QLabel {{ background-color: {BG_DARKEST}; border: 2px solid #ff1744; }}"
        )
        self.update()

    def set_countdown(self, seconds):
        self._countdown = seconds
        self.update()

    def start_scan(self):
        self._scanning   = True
        self._no_face    = False
        self._scan_y     = 0
        self._scan_dir   = 1
        self._grid_alpha = 40
        self._grid_dir   = 1
        self._phase_lbl  = "LOCATING FACE..."
        self._mesh_alpha = 0
        self._frame      = 0
        self.setStyleSheet(
            f"QLabel {{ background-color: {BG_DARKEST}; border: 1px solid {ACCENT_CYAN}; }}"
        )
        self._timer.start(40)

    def enter_deep_scan(self):
        self._deep_phase = True
        self._phase_lbl  = "MAPPING FACIAL GEOMETRY..."
        self._mesh_alpha = 0
        if self._face_size > 0:
            self._mesh_pts = _mesh_points(self._face_cx, self._face_cy, self._face_size)
            # scan starts from top of face oval
            self._scan_y   = int(self._face_cy - self._face_size / 2)
            self._scan_dir = 1

    def stop_scan(self):
        self._scanning   = False
        self._deep_phase = False
        self._countdown  = 0
        self._frame      = 0
        self._timer.stop()
        self.update()

    def _tick(self):
        self._frame += 1
        self._pulse += self._pulse_dir * 0.05
        if self._pulse >= 1.0: self._pulse_dir = -1
        if self._pulse <= 0.0: self._pulse_dir =  1

        if self._deep_phase and self._face_size > 0:
            self._mesh_alpha = min(230, self._mesh_alpha + 8)
            if self._frame % 4 == 0:
                self._mesh_pts = _mesh_points(
                    self._face_cx, self._face_cy, self._face_size, jitter=0.8)
            # scan sweeps through face oval top→bottom→top
            face_top    = self._face_cy - self._face_size / 2
            face_bottom = self._face_cy + self._face_size / 2
            self._scan_y += self._scan_dir * 2
            if self._scan_y >= face_bottom: self._scan_dir = -1
            elif self._scan_y <= face_top:  self._scan_dir =  1
        else:
            self._scan_y += self._scan_dir * 4
            if self._scan_y >= self.height(): self._scan_dir = -1
            elif self._scan_y <= 0:           self._scan_dir =  1
            self._grid_alpha = max(20, min(70, self._grid_alpha + self._grid_dir * 2))
            if self._grid_alpha >= 70: self._grid_dir = -1
            elif self._grid_alpha <= 20: self._grid_dir = 1
        self.update()

    # ── Paint ────────────────────────────────────────────────────────────────

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        if self._no_face:
            self._paint_no_face(p, w, h)
        elif self._scanning:
            if self._deep_phase and self._face_size > 0 and self._mesh_pts:
                self._paint_face_mesh(p, w, h)
            else:
                self._paint_full_scan(p, w, h)
            if self._countdown > 0:
                p.setPen(QPen(QColor(0, 220, 255, 220)))
                p.setFont(QFont("Consolas", 9, QFont.Weight.Bold))
                p.drawText(QRect(w-48, 4, 44, 18),
                           Qt.AlignmentFlag.AlignRight, f"{self._countdown}s")
        p.end()

    def _paint_no_face(self, p, w, h):
        p.setBrush(QBrush(QColor(255, 23, 68, 60)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRect(0, 0, w, h)
        p.setPen(QPen(QColor(255, 23, 68, 230)))
        p.setFont(QFont("Consolas", 28, QFont.Weight.Bold))
        p.drawText(QRect(0, h//2-44, w, 44), Qt.AlignmentFlag.AlignCenter, "⊘")
        p.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
        p.drawText(QRect(0, h//2+4, w, 20), Qt.AlignmentFlag.AlignCenter, "NO FACE DETECTED")
        p.setFont(QFont("Consolas", 7))
        p.setPen(QPen(QColor(255, 100, 100, 180)))
        p.drawText(QRect(0, h//2+26, w, 18), Qt.AlignmentFlag.AlignCenter,
                   "Use a clear, frontal face photo")

    def _paint_full_scan(self, p, w, h):
        p.setPen(QPen(QColor(0, 200, 255, self._grid_alpha), 1))
        for x in range(0, w, 24): p.drawLine(x, 0, x, h)
        for y in range(0, h, 24): p.drawLine(0, y, w, y)
        for i in range(30):
            alpha = int(180 * (1 - i / 30))
            sy = self._scan_y - i * self._scan_dir
            if 0 <= sy <= h:
                p.setPen(QPen(QColor(0, 220, 255, alpha), 1))
                p.drawLine(0, sy, w, sy)
        p.setPen(QPen(QColor(0, 240, 255, 230), 2))
        p.drawLine(0, self._scan_y, w, self._scan_y)
        p.setPen(QPen(QColor(0, 220, 255, 200)))
        p.setFont(QFont("Consolas", 8))
        p.drawText(QRect(0, h-20, w, 20), Qt.AlignmentFlag.AlignCenter, self._phase_lbl)

    def _paint_face_mesh(self, p, w, h):
        cx      = self._face_cx
        cy      = self._face_cy
        size    = self._face_size
        alpha   = self._mesh_alpha
        pts     = self._mesh_pts
        pulse   = self._pulse

        # scan progress 0..1 within the face oval (top=0, bottom=1)
        face_top = cy - size / 2
        scan_pct = (self._scan_y - face_top) / max(size, 1)

        # ── Filled triangles ───────────────────────────────────────────────
        for a, b, c in _STATIC_TRIS:
            if a >= len(pts) or b >= len(pts) or c >= len(pts): continue
            ny_mid = (_FACE_PTS_NORM[a][1] + _FACE_PTS_NORM[b][1] + _FACE_PTS_NORM[c][1]) / 3
            dist   = abs(ny_mid - scan_pct)
            glow   = max(0, int((1 - dist / 0.20) * 40)) if dist < 0.20 else 0
            f_a    = min(255, int(alpha * 0.09) + glow)
            p.setBrush(QBrush(QColor(0, 140, 255, f_a)))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawPolygon(QPolygonF([pts[a], pts[b], pts[c]]))

        # ── Edges ──────────────────────────────────────────────────────────
        for a, b in _STATIC_EDGES:
            if a >= len(pts) or b >= len(pts): continue
            ny_mid = (_FACE_PTS_NORM[a][1] + _FACE_PTS_NORM[b][1]) / 2
            dist   = abs(ny_mid - scan_pct)
            if dist < 0.12:
                bright = int(220 * (1 - dist / 0.12))
                p.setPen(QPen(QColor(120, 255, 255, min(255, int(alpha*0.85) + bright)), 1))
            else:
                p.setPen(QPen(QColor(30, 160, 255, min(190, int(alpha * 0.75))), 1))
            p.drawLine(pts[a], pts[b])

        # ── Nodes ──────────────────────────────────────────────────────────
        for i, pt in enumerate(pts):
            ny   = _FACE_PTS_NORM[i][1]
            dist = abs(ny - scan_pct)

            # Eye centres get special intense glow
            is_eye = (i == _EYE_L_IDX or i == _EYE_R_IDX)

            if is_eye:
                eye_a = int(180 + pulse * 60)
                # Outer glow rings
                for r, a2 in [(12, 30), (8, 60), (5, 100)]:
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    p.setPen(QPen(QColor(80, 200, 255, a2), 1))
                    p.drawEllipse(pt, float(r), float(r))
                # Bright centre
                grad = QRadialGradient(pt, 4)
                grad.setColorAt(0, QColor(200, 255, 255, eye_a))
                grad.setColorAt(1, QColor(0, 180, 255, 0))
                p.setBrush(QBrush(grad))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(pt, 4.0, 4.0)

            elif dist < 0.10:
                glow = int(255 * (1 - dist / 0.10))
                p.setBrush(QBrush(QColor(200, 255, 255, glow)))
                p.setPen(QPen(QColor(255, 255, 255, glow), 1))
                p.drawEllipse(pt, 3.0, 3.0)
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.setPen(QPen(QColor(100, 220, 255, glow // 3), 1))
                p.drawEllipse(pt, 5.5, 5.5)
            else:
                na = min(220, int(alpha * 0.8))
                p.setBrush(QBrush(QColor(60, 200, 255, na)))
                p.setPen(QPen(QColor(100, 230, 255, na), 1))
                p.drawEllipse(pt, 1.8, 1.8)

        # ── Scan line (across full width of face at current y) ────────────
        sa = int(60 + pulse * 80)
        p.setPen(QPen(QColor(150, 255, 255, sa), 1))
        p.drawLine(0, int(self._scan_y), w, int(self._scan_y))

        # ── Corner brackets only (NO box outline) ─────────────────────────
        bx = int(cx - size / 2)
        by = int(cy - size / 2)
        bw = bh = int(size)
        ba = int(160 + pulse * 80)
        p.setPen(QPen(QColor(0, 200, 255, ba), 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        ln = 18
        for qx, qy in [(bx,by),(bx+bw,by),(bx,by+bh),(bx+bw,by+bh)]:
            dx = ln if qx == bx else -ln
            dy = ln if qy == by else -ln
            p.drawLine(qx, qy, qx+dx, qy)
            p.drawLine(qx, qy, qx, qy+dy)

        # ── Status label ──────────────────────────────────────────────────
        p.setPen(QPen(QColor(0, 220, 255, 220)))
        p.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
        p.drawText(QRect(0, h-20, w, 20), Qt.AlignmentFlag.AlignCenter, self._phase_lbl)


# ---------------------------------------------------------------------------
#  Worker
# ---------------------------------------------------------------------------

class SearchWorker(QObject):
    finished     = pyqtSignal(list)
    error        = pyqtSignal(str)
    no_face      = pyqtSignal()
    face_located = pyqtSignal(int, int, int, int)
    countdown    = pyqtSignal(int)

    def __init__(self, image_bytes, tolerance):
        super().__init__()
        self._bytes = image_bytes
        self._tol   = tolerance

    def run(self):
        try:
            from core.face_engine import encode_face_from_bytes, find_best_match, is_available
            from database.db_manager import get_all_encodings

            if not is_available():
                self.error.emit("Face engine unavailable.")
                return

            enc, box = encode_face_from_bytes(self._bytes)
            if enc is None or box is None:
                self.no_face.emit()
                return

            x1, y1, x2, y2 = box
            self.face_located.emit(x1, y1, x2-x1, y2-y1)

            for s in range(5, 0, -1):
                self.countdown.emit(s)
                time.sleep(1)
            self.countdown.emit(0)

            db_records = get_all_encodings()
            if not db_records:
                self.error.emit("No face encodings in database.\nAdd persons with photos first.")
                return

            results = find_best_match(db_records, enc, tolerance=self._tol)
            self.finished.emit(results)

        except Exception as e:
            import traceback; traceback.print_exc()
            self.error.emit(str(e))


# ---------------------------------------------------------------------------
#  SearchPanel
# ---------------------------------------------------------------------------

class SearchPanel(QWidget):
    search_requested = pyqtSignal(bytes, float)
    text_search      = pyqtSignal(str)
    results_ready    = pyqtSignal(list)
    search_error     = pyqtSignal(str)
    status_message   = pyqtSignal(str)

    _PHOTO_W = 276
    _PHOTO_H = 260

    def __init__(self, parent=None):
        super().__init__(parent)
        self._image_bytes = None
        self._image_size  = None
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

        # Mesh size slider
        size_row = QHBoxLayout()
        size_lbl = QLabel("MESH SIZE")
        size_lbl.setStyleSheet(
            f"color: {TEXT_DIM}; font-size: 9px; letter-spacing: 1px; background: transparent; border: none;")
        self.size_slider = QSlider(Qt.Orientation.Horizontal)
        self.size_slider.setRange(0, 80)
        self.size_slider.setValue(35)
        self.size_val_lbl = QLabel("35%")
        self.size_val_lbl.setFixedWidth(32)
        self.size_val_lbl.setStyleSheet(
            f"color: {ACCENT_CYAN}; font-size: 9px; background: transparent; border: none;")
        self.size_slider.valueChanged.connect(lambda v: self.size_val_lbl.setText(f"{v}%"))
        size_row.addWidget(size_lbl)
        size_row.addWidget(self.size_slider, 1)
        size_row.addWidget(self.size_val_lbl)
        cl.addLayout(size_row)

        self.img_status = QLabel("No image loaded")
        self.img_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.img_status.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: 10px; background: transparent; border: none;")
        cl.addWidget(self.img_status)

        filt_group = QGroupBox("SEARCH FILTERS")
        fg = QVBoxLayout(filt_group)
        fg.setSpacing(8)
        tol_lbl = QLabel("MATCH TOLERANCE")
        tol_lbl.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: 10px; letter-spacing: 1px; background: transparent; border: none;")
        fg.addWidget(tol_lbl)
        tol_row = QHBoxLayout()
        self.tol_slider = QSlider(Qt.Orientation.Horizontal)
        self.tol_slider.setRange(30, 75)
        self.tol_slider.setValue(55)
        self.tol_val_lbl = QLabel("0.55")
        self.tol_val_lbl.setFixedWidth(32)
        self.tol_val_lbl.setStyleSheet(
            f"color: {ACCENT_CYAN}; font-size: 11px; background: transparent; border: none;")
        self.tol_slider.valueChanged.connect(lambda v: self.tol_val_lbl.setText(f"{v/100:.2f}"))
        tol_row.addWidget(self.tol_slider, 1)
        tol_row.addWidget(self.tol_val_lbl)
        fg.addLayout(tol_row)
        stat_lbl = QLabel("STATUS FILTER")
        stat_lbl.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: 10px; letter-spacing: 1px; background: transparent; border: none;")
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
                color: {ACCENT_CYAN}; border: 2px solid {ACCENT_BLUE};
                border-radius: 4px; font-family: Consolas;
                font-size: 13px; font-weight: bold; letter-spacing: 3px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {ACCENT_BLUE}, stop:1 #1a7abf);
                color: white; border-color: {ACCENT_CYAN};
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
        self._proc_lbl.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: 10px; background: transparent; border: none;")
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
                border-bottom: none; border-left: none; border-right: none; border-radius: 0;
            }}
        """)
        sb = QHBoxLayout(status_bar)
        sb.setContentsMargins(10, 0, 10, 0)
        dot = PulsingDot(ACCENT_GREEN)
        sys_lbl = QLabel("SYSTEM: ONLINE")
        sys_lbl.setStyleSheet(
            f"color: {ACCENT_GREEN}; font-size: 10px; background: transparent; border: none;")
        sb.addWidget(dot); sb.addWidget(sys_lbl); sb.addStretch()
        root.addWidget(status_bar)

    def _pick_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Query Image", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.webp)")
        if not path: return
        with open(path, 'rb') as f:
            self._image_bytes = f.read()
        arr = np.frombuffer(self._image_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is not None:
            self._image_size = (img.shape[1], img.shape[0])
        self.photo_lbl.set_photo_path(path)
        self.img_status.setText(f"✓ {os.path.basename(path)}")
        self.img_status.setStyleSheet(
            f"color: {ACCENT_GREEN}; font-size: 10px; background: transparent; border: none;")
        self.search_btn.setEnabled(True)

    def _do_face_search(self):
        if not self._image_bytes: return
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
        self._worker.no_face.connect(self._on_no_face)
        self._worker.face_located.connect(self._on_face_located)
        self._worker.countdown.connect(self._on_countdown)
        self._worker.finished.connect(self._on_results)
        self._worker.error.connect(self._on_error)
        self._worker.finished.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)
        self._worker.no_face.connect(self._thread.quit)
        self._thread.start()

    def _on_no_face(self):
        self.photo_lbl.stop_scan()
        self.photo_lbl.show_no_face()
        self._dot.hide(); self._proc_lbl.setText("")
        self.search_btn.setEnabled(True); self.clear_btn.setEnabled(True)
        self.img_status.setText("⚠ No face detected")
        self.img_status.setStyleSheet(
            f"color: #ff1744; font-size: 10px; background: transparent; border: none;")
        self.status_message.emit("No face detected in image")

    def _on_face_located(self, ix, iy, iw, ih):
        if self._image_size is None: return
        orig_w, orig_h = self._image_size
        scale  = min(self._PHOTO_W / orig_w, self._PHOTO_H / orig_h)
        disp_w = int(orig_w * scale)
        disp_h = int(orig_h * scale)
        off_x  = (self._PHOTO_W - disp_w) // 2
        off_y  = (self._PHOTO_H - disp_h) // 2

        # Face box in widget space
        wx = int(ix * scale) + off_x
        wy = int(iy * scale) + off_y
        ww = max(10, int(iw * scale))
        wh = max(10, int(ih * scale))

        # Apply padding from slider
        pad_pct = self.size_slider.value() / 100.0
        pad     = int(max(ww, wh) * pad_pct)
        wx -= pad; wy -= pad
        ww += pad * 2; wh += pad * 2

        # Square bounding region, centred
        size = max(ww, wh)
        wx  -= (size - ww) // 2
        wy  -= (size - wh) // 2

        # Centre point for mesh
        cx = wx + size // 2
        cy = wy + size // 2

        self.photo_lbl.set_face_center(cx, cy, size)
        self.photo_lbl.enter_deep_scan()
        self._proc_lbl.setText("Mapping facial geometry...")
        self.status_message.emit("Face located — mapping geometry...")

    def _on_countdown(self, secs):
        self.photo_lbl.set_countdown(secs)
        self._proc_lbl.setText(
            f"Matching biometrics... {secs}s" if secs > 0 else "Finalising...")

    def _on_results(self, results):
        self.photo_lbl.stop_scan()
        self._dot.hide(); self._proc_lbl.setText("")
        self.search_btn.setEnabled(True); self.clear_btn.setEnabled(True)
        status = self.status_filter.currentText()
        if status != "All Records":
            results = [r for r in results if r.get('status') == status]
        self.results_ready.emit(results)
        self.status_message.emit("1 match found" if results else "No match found")

    def _on_error(self, msg):
        self.photo_lbl.stop_scan()
        self._dot.hide(); self._proc_lbl.setText("")
        self.search_btn.setEnabled(True); self.clear_btn.setEnabled(True)
        self.search_error.emit(msg)
        self.status_message.emit("Search error")

    def _do_text_search(self):
        q = self.text_input.text().strip()
        if q: self.text_search.emit(q)

    def _clear(self):
        self._image_bytes = None; self._image_size = None
        self.photo_lbl.clear_photo()
        self.img_status.setText("No image loaded")
        self.img_status.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: 10px; background: transparent; border: none;")
        self.search_btn.setEnabled(False)
        self._proc_lbl.setText(""); self._dot.hide()
        self.text_input.clear()
        self.status_message.emit("Cleared")