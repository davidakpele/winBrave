"""
core/face_engine.py
Face detection and recognition engine using OpenCV DNN.
No dlib or face_recognition package required.
"""
import io
import os
import pickle
import urllib.request
import numpy as np
import cv2
from PIL import Image
from typing import Optional, List, Tuple, Dict


# ── Model paths ────────────────────────────────────────────────────────────────
_MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")
_DETECTOR_PROTO  = os.path.join(_MODEL_DIR, "deploy.prototxt")
_DETECTOR_MODEL  = os.path.join(_MODEL_DIR, "res10_300x300_ssd_iter_140000.caffemodel")
_RECOGNIZER_MODEL = os.path.join(_MODEL_DIR, "openface.nn4.small2.v1.t7")

_DETECTOR   = None
_RECOGNIZER = None


# ── Model download URLs ────────────────────────────────────────────────────────
_URLS = {
    _DETECTOR_PROTO: "https://raw.githubusercontent.com/opencv/opencv/master/samples/dnn/face_detector/deploy.prototxt",
    _DETECTOR_MODEL: "https://github.com/opencv/opencv_3rdparty/raw/dnn_samples_face_detector_20170830/res10_300x300_ssd_iter_140000.caffemodel",
    _RECOGNIZER_MODEL: "https://storage.cmusatyalab.org/openface-models/nn4.small2.v1.t7",
}


def _ensure_models():
    """Download models if not present."""
    os.makedirs(_MODEL_DIR, exist_ok=True)
    for path, url in _URLS.items():
        if not os.path.exists(path):
            print(f"Downloading model: {os.path.basename(path)} ...")
            urllib.request.urlretrieve(url, path)
            print(f"Downloaded: {os.path.basename(path)}")


def _load_models():
    global _DETECTOR, _RECOGNIZER
    if _DETECTOR is None:
        _ensure_models()
        _DETECTOR = cv2.dnn.readNetFromCaffe(_DETECTOR_PROTO, _DETECTOR_MODEL)
    if _RECOGNIZER is None:
        _RECOGNIZER = cv2.dnn.readNetFromTorch(_RECOGNIZER_MODEL)


# ── Core functions ─────────────────────────────────────────────────────────────

def detect_face_locations(rgb_array: np.ndarray, confidence_thresh: float = 0.5) -> List[Tuple[int, int, int, int]]:
    """Detect faces. Returns list of (top, right, bottom, left) tuples."""
    _load_models()
    h, w = rgb_array.shape[:2]
    blob = cv2.dnn.blobFromImage(rgb_array, 1.0, (300, 300), (104.0, 177.0, 123.0))
    _DETECTOR.setInput(blob)
    detections = _DETECTOR.forward()
    locations = []
    for i in range(detections.shape[2]):
        conf = detections[0, 0, i, 2]
        if conf > confidence_thresh:
            box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
            x1, y1, x2, y2 = box.astype(int)
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)
            locations.append((y1, x2, y2, x1))  # top, right, bottom, left
    return locations


def encode_face(rgb_array: np.ndarray) -> Optional[np.ndarray]:
    """Return 128-d face embedding for the first detected face, or None."""
    _load_models()
    locations = detect_face_locations(rgb_array)
    if not locations:
        return None
    top, right, bottom, left = locations[0]
    face_roi = rgb_array[top:bottom, left:right]
    if face_roi.size == 0:
        return None
    blob = cv2.dnn.blobFromImage(face_roi, 1.0 / 255, (96, 96), (0, 0, 0), swapRB=True, crop=False)
    _RECOGNIZER.setInput(blob)
    embedding = _RECOGNIZER.forward()
    vec = embedding[0]
    norm = np.linalg.norm(vec)
    return vec / norm if norm > 0 else vec


def encode_face_from_bytes(image_bytes: bytes) -> Optional[np.ndarray]:
    """Encode face from raw image bytes."""
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    return encode_face(np.array(img))


def encode_face_from_path(image_path: str) -> Optional[np.ndarray]:
    """Encode face from file path."""
    img = Image.open(image_path).convert("RGB")
    return encode_face(np.array(img))


def compare_encodings(enc1: np.ndarray, enc2: np.ndarray) -> float:
    """Return cosine distance between two embeddings (lower = more similar)."""
    return float(1.0 - np.dot(enc1, enc2))


def find_best_match(
    database_records: List[Dict],
    unknown_encoding: np.ndarray,
    tolerance: float = 0.55,
    top_n: int = 5
) -> List[Dict]:
    """Search database for best matching faces. Returns top_n sorted by confidence."""
    if not database_records:
        return []
    results = []
    for record in database_records:
        enc = record.get('encoding')
        if enc is None:
            continue
        dist = compare_encodings(enc, unknown_encoding)
        if dist <= tolerance:
            confidence = max(0.0, (1.0 - dist) * 100)
            results.append({**record, 'confidence': round(confidence, 1), 'distance': dist})
    results.sort(key=lambda x: x['distance'])
    return results[:top_n]


def resize_image_bytes(image_bytes: bytes, max_size: Tuple[int, int] = (300, 300)) -> bytes:
    """Resize image bytes preserving aspect ratio."""
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img.thumbnail(max_size, Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def array_to_qpixmap(rgb_array: np.ndarray):
    """Convert numpy RGB array to QPixmap."""
    from PyQt6.QtGui import QImage, QPixmap
    h, w, ch = rgb_array.shape
    qimg = QImage(rgb_array.data, w, h, ch * w, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(qimg)


def is_available() -> bool:
    """Always True — only needs opencv which is always installed."""
    try:
        _load_models()
        return True
    except Exception as e:
        print(f"Face engine not available: {e}")
        return False