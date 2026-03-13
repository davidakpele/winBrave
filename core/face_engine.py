"""
core/face_engine.py
OpenCV DNN face detection + OpenFace embedding engine.
Returns ONLY the single best match above threshold.
Minimum 60% confidence required for a match.
"""
import os
import pickle
import urllib.request
import numpy as np
import cv2

MODEL_DIR  = os.path.join(os.path.dirname(__file__), '..', 'models')
PROTO_PATH = os.path.join(MODEL_DIR, 'deploy.prototxt')
MODEL_PATH = os.path.join(MODEL_DIR, 'res10_300x300_ssd_iter_140000.caffemodel')
EMB_PATH   = os.path.join(MODEL_DIR, 'openface.nn4.small2.v1.t7')

PROTO_URL = "https://raw.githubusercontent.com/opencv/opencv/master/samples/dnn/face_detector/deploy.prototxt"
MODEL_URL = "https://github.com/opencv/opencv_3rdparty/raw/dnn_samples_face_detector_20170830/res10_300x300_ssd_iter_140000.caffemodel"
EMB_URL   = "https://storage.cmusatyalab.org/openface-models/nn4.small2.v1.t7"

# Minimum confidence % required to count as a match
MINIMUM_CONFIDENCE_PERCENT = 60.0

_detector  = None
_embedder  = None
_available = False


def _download_models():
    os.makedirs(MODEL_DIR, exist_ok=True)
    for path, url, name in [
        (PROTO_PATH, PROTO_URL, "deploy.prototxt"),
        (MODEL_PATH, MODEL_URL, "face detector model"),
        (EMB_PATH,   EMB_URL,   "OpenFace embedding model"),
    ]:
        if not os.path.exists(path):
            print(f"[face_engine] Downloading {name}...")
            try:
                urllib.request.urlretrieve(url, path)
                print(f"[face_engine] Downloaded {name}")
            except Exception as e:
                print(f"[face_engine] Failed to download {name}: {e}")


def _load_models():
    global _detector, _embedder, _available
    if _available:
        return True
    try:
        _download_models()
        if not all(os.path.exists(p) for p in [PROTO_PATH, MODEL_PATH, EMB_PATH]):
            return False
        _detector = cv2.dnn.readNetFromCaffe(PROTO_PATH, MODEL_PATH)
        _embedder = cv2.dnn.readNetFromTorch(EMB_PATH)
        _available = True
        print("[face_engine] Models loaded OK")
        return True
    except Exception as e:
        print(f"[face_engine] Error loading models: {e}")
        return False


def is_available() -> bool:
    return _load_models()


def _detect_and_crop_face(img):
    """
    Runs face detector on the full-resolution image.
    Returns tight face crop (numpy array) or None.
    """
    h, w = img.shape[:2]

    scale = 600.0 / max(h, w)
    new_w, new_h = int(w * scale), int(h * scale)
    resized = cv2.resize(img, (new_w, new_h))

    blob = cv2.dnn.blobFromImage(
        resized, 1.0, (new_w, new_h), (104.0, 177.0, 123.0)
    )
    _detector.setInput(blob)
    detections = _detector.forward()

    best_conf = 0.0
    best_box  = None
    for i in range(detections.shape[2]):
        conf = float(detections[0, 0, i, 2])
        if conf > best_conf:
            best_conf = conf
            box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
            best_box = box.astype(int)

    if best_conf < 0.4 or best_box is None:
        print(f"[face_engine] No face detected (conf={best_conf:.3f})")
        return None

    x1, y1, x2, y2 = best_box
    pad_x = int((x2 - x1) * 0.10)
    pad_y = int((y2 - y1) * 0.10)
    x1 = max(0, x1 - pad_x)
    y1 = max(0, y1 - pad_y)
    x2 = min(w, x2 + pad_x)
    y2 = min(h, y2 + pad_y)

    face_crop = img[y1:y2, x1:x2]
    print(f"[face_engine] Face cropped conf={best_conf:.3f} size={face_crop.shape[1]}x{face_crop.shape[0]}")
    return face_crop if face_crop.size > 0 else None


def _embed(face_crop):
    """Embed a face crop into a 128-d vector."""
    blob = cv2.dnn.blobFromImage(
        cv2.resize(face_crop, (96, 96)),
        1.0 / 255.0, (96, 96),
        (0, 0, 0), swapRB=True, crop=False
    )
    _embedder.setInput(blob)
    return _embedder.forward().flatten()


def encode_face_from_bytes(image_bytes: bytes):
    """Decode image bytes, detect face only, return 128-d embedding or None."""
    if not _load_models():
        return None
    try:
        arr = np.frombuffer(image_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            return None
        face = _detect_and_crop_face(img)
        if face is None:
            return None
        return _embed(face)
    except Exception as e:
        print(f"[face_engine] encode_face_from_bytes error: {e}")
        return None


def encode_face_from_path(path: str):
    """Load image from path, detect face only, return 128-d embedding or None."""
    if not _load_models():
        return None
    try:
        img = cv2.imread(path)
        if img is None:
            return None
        face = _detect_and_crop_face(img)
        if face is None:
            return None
        return _embed(face)
    except Exception as e:
        print(f"[face_engine] encode_face_from_path error: {e}")
        return None


def find_best_match(db_records: list, query_encoding, tolerance: float = 0.55) -> list:
    """
    Returns the single best match only if confidence >= 60%.
    The tolerance slider is still respected but cannot go below 60% confidence.
    """
    best_record   = None
    best_distance = float('inf')

    for rec in db_records:
        raw = rec.get('encoding')
        if raw is None:
            continue

        if isinstance(raw, np.ndarray):
            stored_enc = raw
        elif isinstance(raw, (bytes, bytearray)):
            try:
                stored_enc = pickle.loads(raw)
            except Exception:
                continue
        else:
            continue

        if not isinstance(stored_enc, np.ndarray) or stored_enc.size == 0:
            continue

        # Cosine distance (0 = identical, 1 = completely different)
        a = query_encoding / (np.linalg.norm(query_encoding) + 1e-10)
        b = stored_enc     / (np.linalg.norm(stored_enc)     + 1e-10)
        distance = float(1.0 - np.dot(a, b))
        confidence = (1.0 - distance) * 100

        print(f"[face_engine] {rec.get('full_name','?'):20s}  dist={distance:.4f}  conf={confidence:.1f}%")

        if distance < best_distance:
            best_distance = distance
            best_record   = rec

    if best_record is None:
        print("[face_engine] No records with encodings found")
        return []

    best_confidence = (1.0 - best_distance) * 100

    # Hard rule: must be 60% or above — ignore tolerance slider below this
    if best_confidence < MINIMUM_CONFIDENCE_PERCENT:
        print(f"[face_engine] Best match only {best_confidence:.1f}% — below 60% minimum, returning not found")
        return []

    # Also respect tolerance slider (converted: tolerance=0.55 means max distance 0.55)
    if best_distance > tolerance:
        print(f"[face_engine] Best match {best_confidence:.1f}% — below tolerance threshold, returning not found")
        return []

    result = dict(best_record)
    result['confidence'] = round(best_confidence, 1)
    result['distance']   = round(best_distance, 4)
    print(f"[face_engine] MATCH → {result.get('full_name')}  conf={result['confidence']}%")
    return [result]