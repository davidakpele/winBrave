"""
core/face_engine.py
Face detection, encoding, and matching engine.
Uses face_recognition (dlib) for biometric analysis.
"""
import numpy as np
import pickle
from typing import Optional, List, Tuple, Dict
from pathlib import Path

# Lazy imports — allows the app to start even if libraries aren't installed yet
_face_recognition = None
_cv2 = None
_PIL_Image = None


def _import_deps():
    global _face_recognition, _cv2, _PIL_Image
    if _face_recognition is None:
        try:
            import face_recognition as fr
            _face_recognition = fr
        except ImportError:
            raise ImportError(
                "face_recognition is not installed.\n"
                "Run:  pip install face_recognition\n"
                "Also requires cmake + Visual Studio Build Tools on Windows."
            )
    if _cv2 is None:
        try:
            import cv2
            _cv2 = cv2
        except ImportError:
            raise ImportError("opencv-python is not installed.\nRun: pip install opencv-python")
    if _PIL_Image is None:
        try:
            from PIL import Image
            _PIL_Image = Image
        except ImportError:
            raise ImportError("Pillow is not installed.\nRun: pip install Pillow")


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────

def encode_face_from_path(image_path: str) -> Optional[np.ndarray]:
    """Load an image file and return the first face encoding found, or None."""
    _import_deps()
    image = _face_recognition.load_image_file(image_path)
    encodings = _face_recognition.face_encodings(image)
    return encodings[0] if encodings else None


def encode_face_from_bytes(image_bytes: bytes) -> Optional[np.ndarray]:
    """Encode a face from raw image bytes (e.g., from a file dialog)."""
    _import_deps()
    import io
    img = _PIL_Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img_array = np.array(img)
    encodings = _face_recognition.face_encodings(img_array)
    return encodings[0] if encodings else None


def encode_face_from_array(rgb_array: np.ndarray) -> Optional[np.ndarray]:
    """Encode from a numpy RGB array (e.g., from webcam frame)."""
    _import_deps()
    encodings = _face_recognition.face_encodings(rgb_array)
    return encodings[0] if encodings else None


def detect_faces(rgb_array: np.ndarray) -> List[Tuple[int, int, int, int]]:
    """Return list of face bounding boxes (top, right, bottom, left)."""
    _import_deps()
    return _face_recognition.face_locations(rgb_array)


def compare_faces(
    known_encodings: List[np.ndarray],
    unknown_encoding: np.ndarray,
    tolerance: float = 0.55
) -> Tuple[List[bool], List[float]]:
    """
    Compare an unknown encoding against a list of known encodings.
    Returns (matches_list, distance_list).
    Lower distance = better match. Typical threshold ≤ 0.55.
    """
    _import_deps()
    matches = _face_recognition.compare_faces(known_encodings, unknown_encoding, tolerance=tolerance)
    distances = _face_recognition.face_distance(known_encodings, unknown_encoding)
    return matches, distances.tolist()


def find_best_match(
    database_records: List[Dict],
    unknown_encoding: np.ndarray,
    tolerance: float = 0.55,
    top_n: int = 5
) -> List[Dict]:
    """
    Search the database for the best matching faces.
    Returns up to top_n results sorted by confidence (best first).
    Each result dict contains the DB record plus 'confidence' and 'distance'.
    """
    if not database_records:
        return []

    known_encodings = [r['encoding'] for r in database_records]
    matches, distances = compare_faces(known_encodings, unknown_encoding, tolerance)

    results = []
    for i, (record, matched, dist) in enumerate(zip(database_records, matches, distances)):
        if matched:
            confidence = max(0.0, (1.0 - dist) * 100)
            results.append({**record, 'confidence': round(confidence, 1), 'distance': dist})

    # Sort by distance ascending (closest = best)
    results.sort(key=lambda x: x['distance'])
    return results[:top_n]


def draw_faces_on_frame(frame_bgr: np.ndarray, face_locations: List, labels: List[str] = None) -> np.ndarray:
    """Draw bounding boxes and optional labels on a BGR frame (for webcam preview)."""
    _import_deps()
    import cv2
    frame = frame_bgr.copy()
    for i, (top, right, bottom, left) in enumerate(face_locations):
        cv2.rectangle(frame, (left, top), (right, bottom), (0, 180, 220), 2)
        label = labels[i] if labels and i < len(labels) else ""
        if label:
            cv2.rectangle(frame, (left, bottom - 22), (right, bottom), (0, 120, 180), cv2.FILLED)
            cv2.putText(frame, label, (left + 4, bottom - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    return frame


def resize_image_bytes(image_bytes: bytes, max_size: Tuple[int, int] = (300, 300)) -> bytes:
    """Resize image bytes to fit within max_size, preserving aspect ratio."""
    _import_deps()
    import io
    img = _PIL_Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img.thumbnail(max_size, _PIL_Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def array_to_qpixmap(rgb_array: np.ndarray):
    """Convert numpy RGB array to QPixmap for display in PyQt6."""
    from PyQt6.QtGui import QImage, QPixmap
    h, w, ch = rgb_array.shape
    bytes_per_line = ch * w
    qimg = QImage(rgb_array.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(qimg)


def is_available() -> bool:
    """Return True if all face recognition dependencies are importable."""
    try:
        _import_deps()
        return True
    except ImportError:
        return False
