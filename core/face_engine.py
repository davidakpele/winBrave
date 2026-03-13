"""
core/face_engine.py
OpenCV DNN face detection + OpenFace embedding engine.
- Detects and crops face FIRST, embeds only the face region
- Minimum 65% confidence required for a match
- Returns confidence, distance, and rating label
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
MINIMUM_CONFIDENCE_PERCENT = 65.0

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
    Runs SSD face detector.
    Scales image up to 600px on longest side for best detection accuracy.
    Returns tight face crop (numpy array BGR) or None.
    """
    h, w = img.shape[:2]
    scale   = 600.0 / max(h, w)
    new_w   = int(w * scale)
    new_h   = int(h * scale)
    resized = cv2.resize(img, (new_w, new_h))

    # Use the resized dimensions for the blob so the network sees the full image
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
            # Boxes are relative → scale back to ORIGINAL image coordinates
            box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
            best_box = box.astype(int)

    # Require at least 50% detection confidence
    if best_conf < 0.50 or best_box is None:
        print(f"[face_engine] No face detected (best_conf={best_conf:.3f})")
        return None

    x1, y1, x2, y2 = best_box

    # Add 10% padding around the detected face box
    pad_x = int((x2 - x1) * 0.10)
    pad_y = int((y2 - y1) * 0.10)
    x1 = max(0, x1 - pad_x)
    y1 = max(0, y1 - pad_y)
    x2 = min(w, x2 + pad_x)
    y2 = min(h, y2 + pad_y)

    face_crop = img[y1:y2, x1:x2]
    if face_crop.size == 0:
        print("[face_engine] Face crop was empty after padding")
        return None

    print(f"[face_engine] Face detected conf={best_conf:.3f}  "
          f"crop={face_crop.shape[1]}x{face_crop.shape[0]}px")
    return face_crop


def _embed_face_crop(face_crop):
    """
    Embed a FACE CROP (not the full image) into a 128-d OpenFace vector.
    The crop must be a BGR numpy array of the face region only.
    """
    # Resize to the exact input the OpenFace network expects
    face_resized = cv2.resize(face_crop, (96, 96))
    blob = cv2.dnn.blobFromImage(
        face_resized,
        scalefactor=1.0 / 255.0,
        size=(96, 96),
        mean=(0, 0, 0),
        swapRB=True,   # BGR → RGB
        crop=False
    )
    _embedder.setInput(blob)
    vec = _embedder.forward().flatten()
    print(f"[face_engine] Embedding computed, norm={np.linalg.norm(vec):.4f}")
    return vec


def encode_face_from_bytes(image_bytes: bytes):
    """
    Decode image bytes → detect face → embed FACE CROP ONLY.
    Returns 128-d numpy vector or None if no face found.
    """
    if not _load_models():
        return None
    try:
        arr = np.frombuffer(image_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            print("[face_engine] Failed to decode image bytes")
            return None
        face = _detect_and_crop_face(img)
        if face is None:
            return None
        return _embed_face_crop(face)
    except Exception as e:
        print(f"[face_engine] encode_face_from_bytes error: {e}")
        return None


def encode_face_from_path(path: str):
    """
    Load image from path → detect face → embed FACE CROP ONLY.
    Returns 128-d numpy vector or None.
    """
    if not _load_models():
        return None
    try:
        img = cv2.imread(path)
        if img is None:
            print(f"[face_engine] Could not read image: {path}")
            return None
        face = _detect_and_crop_face(img)
        if face is None:
            return None
        return _embed_face_crop(face)
    except Exception as e:
        print(f"[face_engine] encode_face_from_path error: {e}")
        return None


def _get_match_rating(confidence: float) -> dict:
    """
    Returns a human-readable match rating dict based on confidence %.
    
    Returns:
        {
          'label':      str   — e.g. "STRONG MATCH"
          'diff':       float — difference from 100%, e.g. 12.4
          'color_hint': str   — 'green' / 'yellow' / 'orange' / 'red'
        }
    """
    diff = round(100.0 - confidence, 1)

    if confidence >= 92.0:
        label      = "EXACT MATCH"
        color_hint = "green"
    elif confidence >= 82.0:
        label      = "STRONG MATCH"
        color_hint = "green"
    elif confidence >= 75.0:
        label      = "CLOSE MATCH"
        color_hint = "yellow"
    elif confidence >= 65.0:
        label      = "POSSIBLE MATCH"
        color_hint = "orange"
    else:
        # Should never reach here since we filter below 65% before calling this
        label      = "WEAK MATCH"
        color_hint = "red"

    return {
        'label':      label,
        'diff':       diff,
        'color_hint': color_hint,
    }


def find_best_match(db_records: list, query_encoding, tolerance: float = 0.55) -> list:
    """
    Compare query_encoding (128-d face vector) against all DB records.
    Uses COSINE distance on FACE-ONLY embeddings.

    Rules:
      - Hard minimum: 65% confidence (overrides tolerance slider)
      - Tolerance slider still applies as a secondary gate
      - Returns at most ONE result (the best match)
      - Result includes: confidence, distance, rating label, diff %
    """
    best_record   = None
    best_distance = float('inf')

    for rec in db_records:
        raw = rec.get('encoding')
        if raw is None:
            continue

        # Support both raw numpy arrays and pickled bytes
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

        # Cosine distance: 0 = identical face, 1 = completely different
        a = query_encoding / (np.linalg.norm(query_encoding) + 1e-10)
        b = stored_enc     / (np.linalg.norm(stored_enc)     + 1e-10)
        distance   = float(1.0 - np.dot(a, b))
        confidence = (1.0 - distance) * 100.0

        print(f"[face_engine]  {rec.get('full_name', '?'):24s}  "
              f"dist={distance:.4f}  conf={confidence:.1f}%")

        if distance < best_distance:
            best_distance = distance
            best_record   = rec

    if best_record is None:
        print("[face_engine] No encoded records found in database")
        return []

    best_confidence = (1.0 - best_distance) * 100.0

    # Gate 1 — hard 65% floor (cannot be overridden by slider)
    if best_confidence < MINIMUM_CONFIDENCE_PERCENT:
        print(f"[face_engine] Best={best_confidence:.1f}% < 65% minimum → NO MATCH")
        return []

    # Gate 2 — tolerance slider (distance must be ≤ slider value)
    if best_distance > tolerance:
        print(f"[face_engine] Best={best_confidence:.1f}% fails tolerance={tolerance} → NO MATCH")
        return []

    # Build the result with rating metadata
    rating = _get_match_rating(best_confidence)

    result = dict(best_record)
    result['confidence']   = round(best_confidence, 1)
    result['distance']     = round(best_distance, 4)
    result['match_label']  = rating['label']          # e.g. "CLOSE MATCH"
    result['diff_percent'] = rating['diff']            # e.g. 18.5
    result['color_hint']   = rating['color_hint']     # e.g. "yellow"

    print(f"[face_engine] ✓ {rating['label']} → {result.get('full_name')}  "
          f"Match={result['confidence']}%  Diff={result['diff_percent']}%")
    return [result]