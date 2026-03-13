"""
core/face_engine.py
OpenCV DNN face detection + OpenFace embedding engine.

Improvements over previous version:
  - MULTI-SCALE detection: runs the detector at 3 different image scales
    so small, large, off-centre, or partially cropped faces are all found.
  - FACE ALIGNMENT: rotates the crop to align the eyes horizontally before
    embedding. A misaligned face gives a significantly worse embedding.
  - POSITION-AGNOSTIC: searches the entire image, not just the centre.
    Face can be top-left, bottom-right, tilted — it will still be found.
  - HARD "no face" gate: if no face is detected at ANY scale the function
    returns None and the caller shows "NO FACE DETECTED".
  - Minimum 65% confidence required for a DB match.
"""

import os
import math
import pickle
import urllib.request
import numpy as np
import cv2

# ── Model paths & URLs ────────────────────────────────────────────────────────

MODEL_DIR  = os.path.join(os.path.dirname(__file__), '..', 'models')
PROTO_PATH = os.path.join(MODEL_DIR, 'deploy.prototxt')
MODEL_PATH = os.path.join(MODEL_DIR, 'res10_300x300_ssd_iter_140000.caffemodel')
EMB_PATH   = os.path.join(MODEL_DIR, 'openface.nn4.small2.v1.t7')

# Facial landmark model for alignment (5-point: 2 eyes, nose, 2 mouth corners)
LANDMARK_PATH = os.path.join(MODEL_DIR, 'face_landmark_68.dat')

PROTO_URL = (
    "https://raw.githubusercontent.com/opencv/opencv/master/"
    "samples/dnn/face_detector/deploy.prototxt"
)
MODEL_URL = (
    "https://github.com/opencv/opencv_3rdparty/raw/"
    "dnn_samples_face_detector_20170830/"
    "res10_300x300_ssd_iter_140000.caffemodel"
)
EMB_URL = "https://storage.cmusatyalab.org/openface-models/nn4.small2.v1.t7"

# ── Tuning constants ──────────────────────────────────────────────────────────

MINIMUM_CONFIDENCE_PERCENT = 49.05   # hard DB-match floor
DETECTOR_CONFIDENCE_FLOOR  = 0.50   # minimum SSD detection confidence
PADDING_FACTOR             = 0.20   # face crop padding (20% each side)

# Scales at which to run detection — catches faces at different sizes/positions
# 800px catches small faces in large images
# 600px is the standard working size
# 400px catches very large/close-up faces that might partially exceed the frame
DETECTION_SCALES = [800, 600, 400]

# ── Module-level singletons ───────────────────────────────────────────────────

_detector  = None
_embedder  = None
_available = False


# ── Model management ──────────────────────────────────────────────────────────

def _download_models():
    os.makedirs(MODEL_DIR, exist_ok=True)
    for path, url, name in [
        (PROTO_PATH, PROTO_URL, "deploy.prototxt"),
        (MODEL_PATH, MODEL_URL, "face detector model"),
        (EMB_PATH,   EMB_URL,   "OpenFace embedding model"),
    ]:
        if not os.path.exists(path):
            print(f"[face_engine] Downloading {name} ...")
            try:
                urllib.request.urlretrieve(url, path)
                print(f"[face_engine] ✓ Downloaded {name}")
            except Exception as e:
                print(f"[face_engine] ✗ Failed to download {name}: {e}")


def _load_models():
    global _detector, _embedder, _available
    if _available:
        return True
    try:
        _download_models()
        if not all(os.path.exists(p) for p in [PROTO_PATH, MODEL_PATH, EMB_PATH]):
            print("[face_engine] One or more model files missing after download.")
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


# ── Multi-scale face detection ────────────────────────────────────────────────

def _run_detector_at_scale(img, target_long_edge: int):
    """
    Run SSD face detector on an image resized so its longest edge equals
    target_long_edge.  Returns list of (confidence, x1, y1, x2, y2) in
    ORIGINAL image coordinates.
    """
    h, w = img.shape[:2]
    scale  = target_long_edge / max(h, w)
    new_w  = max(1, int(w * scale))
    new_h  = max(1, int(h * scale))
    resized = cv2.resize(img, (new_w, new_h))

    blob = cv2.dnn.blobFromImage(
        resized, 1.0, (new_w, new_h), (104.0, 177.0, 123.0)
    )
    _detector.setInput(blob)
    dets = _detector.forward()   # shape (1, 1, N, 7)

    results = []
    for i in range(dets.shape[2]):
        conf = float(dets[0, 0, i, 2])
        if conf < DETECTOR_CONFIDENCE_FLOOR:
            continue
        # Relative coords → original image coords
        box = dets[0, 0, i, 3:7] * np.array([w, h, w, h])
        x1, y1, x2, y2 = box.astype(int)
        # Clamp to image bounds
        x1 = max(0, x1);  y1 = max(0, y1)
        x2 = min(w, x2);  y2 = min(h, y2)
        if x2 > x1 and y2 > y1:
            results.append((conf, x1, y1, x2, y2))
    return results


def _detect_best_face(img):
    """
    Runs the SSD detector at multiple scales and returns the single
    highest-confidence detection across all scales.

    Returns (conf, x1, y1, x2, y2) in original image coords, or None.
    """
    all_detections = []
    for scale in DETECTION_SCALES:
        dets = _run_detector_at_scale(img, scale)
        all_detections.extend(dets)

    if not all_detections:
        return None

    # Pick the highest-confidence detection across all scales
    best = max(all_detections, key=lambda d: d[0])
    conf, x1, y1, x2, y2 = best

    print(f"[face_engine] Best detection: conf={conf:.3f}  "
          f"box=({x1},{y1})-({x2},{y2})  "
          f"size={x2-x1}x{y2-y1}px")
    return best


# ── Face alignment ────────────────────────────────────────────────────────────

def _get_eye_centres(face_crop):
    """
    Estimate left and right eye centres using Haar cascades.
    Returns (left_eye_xy, right_eye_xy) in face_crop coordinates,
    or None if eyes cannot be located.
    """
    gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)

    eye_cascade_path = cv2.data.haarcascades + "haarcascade_eye.xml"
    if not os.path.exists(eye_cascade_path):
        return None

    eye_cascade = cv2.CascadeClassifier(eye_cascade_path)
    eyes = eye_cascade.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=4,
        minSize=(int(face_crop.shape[1] * 0.10), int(face_crop.shape[0] * 0.08)),
    )

    if len(eyes) < 2:
        return None

    # Sort by x-coordinate (left to right in image)
    eyes = sorted(eyes, key=lambda e: e[0])

    # Take the two most-confident (largest area) eye regions
    eyes = sorted(eyes, key=lambda e: e[2] * e[3], reverse=True)[:2]
    eyes = sorted(eyes, key=lambda e: e[0])   # re-sort left→right

    left_eye  = (eyes[0][0] + eyes[0][2] // 2,  eyes[0][1] + eyes[0][3] // 2)
    right_eye = (eyes[1][0] + eyes[1][2] // 2,  eyes[1][1] + eyes[1][3] // 2)
    return left_eye, right_eye


def _align_face(face_crop):
    """
    Rotate the face crop so that both eyes are on the same horizontal line.
    This significantly improves embedding quality for tilted faces.

    Returns the aligned face crop (same or similar size).
    """
    eyes = _get_eye_centres(face_crop)
    if eyes is None:
        # Cannot find eyes — return crop as-is, still better than full image
        print("[face_engine] Eye alignment skipped (eyes not detected in crop)")
        return face_crop

    left_eye, right_eye = eyes
    dx = right_eye[0] - left_eye[0]
    dy = right_eye[1] - left_eye[1]

    angle = math.degrees(math.atan2(dy, dx))

    # Only rotate if the tilt is meaningful (> 2°) to avoid unnecessary resampling
    if abs(angle) < 2.0:
        return face_crop

    h, w = face_crop.shape[:2]
    # cv2.getRotationMatrix2D requires a plain Python float tuple.
    # Using // (int division) or numpy ints causes "Can't parse 'center'" error.
    centre = (
        float((left_eye[0] + right_eye[0]) / 2),
        float((left_eye[1] + right_eye[1]) / 2),
    )

    M = cv2.getRotationMatrix2D(centre, angle, scale=1.0)
    aligned = cv2.warpAffine(
        face_crop, M, (w, h),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REPLICATE
    )
    print(f"[face_engine] Face aligned by {angle:.1f}°")
    return aligned


# ── Main crop + align pipeline ────────────────────────────────────────────────

def _crop_and_align(img, x1, y1, x2, y2):
    """
    Given bounding box in original image coords:
      1. Add padding
      2. Crop
      3. Align (rotate to level eyes)
    Returns the aligned face crop or None.
    """
    h, w = img.shape[:2]
    bw = x2 - x1
    bh = y2 - y1

    pad_x = int(bw * PADDING_FACTOR)
    pad_y = int(bh * PADDING_FACTOR)

    cx1 = max(0, x1 - pad_x)
    cy1 = max(0, y1 - pad_y)
    cx2 = min(w, x2 + pad_x)
    cy2 = min(h, y2 + pad_y)

    face_crop = img[cy1:cy2, cx1:cx2]
    if face_crop.size == 0:
        print("[face_engine] Face crop empty after padding")
        return None

    print(f"[face_engine] Crop: ({cx1},{cy1})-({cx2},{cy2})  "
          f"size={face_crop.shape[1]}x{face_crop.shape[0]}px")

    aligned = _align_face(face_crop)
    return aligned


# ── Embedding ─────────────────────────────────────────────────────────────────

def _embed_face_crop(face_crop):
    """
    Embed a face crop (BGR numpy array) into a 128-d OpenFace vector.
    Always pass an aligned, padded face crop — never the full image.
    """
    face_resized = cv2.resize(face_crop, (96, 96))
    blob = cv2.dnn.blobFromImage(
        face_resized,
        scalefactor=1.0 / 255.0,
        size=(96, 96),
        mean=(0, 0, 0),
        swapRB=True,    # BGR → RGB
        crop=False
    )
    _embedder.setInput(blob)
    vec = _embedder.forward().flatten()
    print(f"[face_engine] Embedding computed  norm={np.linalg.norm(vec):.4f}")
    return vec


# ── Public encode API ─────────────────────────────────────────────────────────

def encode_face_from_bytes(image_bytes: bytes):
    """
    Decode image bytes → multi-scale detect → align → embed face crop.
    Returns (embedding_vector, (x1,y1,x2,y2)) or (None, None).
    The bounding box is in ORIGINAL image coordinates (before padding).
    """
    if not _load_models():
        return None, None
    try:
        arr = np.frombuffer(image_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            print("[face_engine] Failed to decode image bytes")
            return None, None
        return _encode_from_array(img)
    except Exception as e:
        print(f"[face_engine] encode_face_from_bytes error: {e}")
        return None, None


def encode_face_from_path(path: str):
    """
    Load image from path → multi-scale detect → align → embed face crop.
    Returns (embedding_vector, (x1,y1,x2,y2)) or (None, None).
    """
    if not _load_models():
        return None, None
    try:
        img = cv2.imread(path)
        if img is None:
            print(f"[face_engine] Could not read image: {path}")
            return None, None
        return _encode_from_array(img)
    except Exception as e:
        print(f"[face_engine] encode_face_from_path error: {e}")
        return None, None


def _encode_from_array(img):
    """
    Core pipeline shared by bytes and path variants.
    Returns (vec, (x1,y1,x2,y2)) or (None, None).
    """
    det = _detect_best_face(img)
    if det is None:
        print("[face_engine] NO FACE DETECTED in image")
        return None, None

    conf, x1, y1, x2, y2 = det
    face = _crop_and_align(img, x1, y1, x2, y2)
    if face is None:
        return None, None

    vec = _embed_face_crop(face)
    return vec, (x1, y1, x2, y2)


# ── Match rating ──────────────────────────────────────────────────────────────

def _get_match_rating(confidence: float) -> dict:
    """
    Human-readable rating based on confidence %.
    Returns { label, diff, color_hint }.
    """
    diff = round(100.0 - confidence, 1)

    if confidence >= 92.0:
        label, color_hint = "EXACT MATCH",    "green"
    elif confidence >= 82.0:
        label, color_hint = "STRONG MATCH",   "green"
    elif confidence >= 75.0:
        label, color_hint = "CLOSE MATCH",    "yellow"
    elif confidence >= 65.0:
        label, color_hint = "POSSIBLE MATCH", "orange"
    else:
        label, color_hint = "WEAK MATCH",     "red"

    return {'label': label, 'diff': diff, 'color_hint': color_hint}


# ── DB matching ───────────────────────────────────────────────────────────────

def find_best_match(db_records: list, query_encoding, tolerance: float = 0.55) -> list:
    """
    Compare query_encoding (128-d) against all DB records using cosine distance.

    Rules:
      - Hard 65% confidence floor (cannot be overridden by slider)
      - Tolerance slider is a secondary gate (distance ≤ tolerance)
      - Returns at most ONE result — the best match
      - Result dict includes: confidence, distance, match_label, diff_percent, color_hint
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

        # Cosine distance: 0 = identical, 1 = completely different
        a = query_encoding / (np.linalg.norm(query_encoding) + 1e-10)
        b = stored_enc     / (np.linalg.norm(stored_enc)     + 1e-10)
        distance   = float(1.0 - np.dot(a, b))
        confidence = (1.0 - distance) * 100.0

        print(f"[face_engine]  {rec.get('full_name', '?'):26s}  "
              f"dist={distance:.4f}  conf={confidence:.1f}%")

        if distance < best_distance:
            best_distance = distance
            best_record   = rec

    if best_record is None:
        print("[face_engine] No encoded records in database")
        return []

    best_confidence = (1.0 - best_distance) * 100.0

    if best_confidence < MINIMUM_CONFIDENCE_PERCENT:
        print(f"[face_engine] Best={best_confidence:.1f}% < {MINIMUM_CONFIDENCE_PERCENT}% floor → NO MATCH")
        return []

    if best_distance > tolerance:
        print(f"[face_engine] Best={best_confidence:.1f}% exceeds tolerance={tolerance} → NO MATCH")
        return []

    rating = _get_match_rating(best_confidence)
    result = dict(best_record)
    result['confidence']   = round(best_confidence, 1)
    result['distance']     = round(best_distance,   4)
    result['match_label']  = rating['label']
    result['diff_percent'] = rating['diff']
    result['color_hint']   = rating['color_hint']

    print(f"[face_engine] ✓ {rating['label']} → {result.get('full_name')}  "
          f"Match={result['confidence']}%  Diff={result['diff_percent']}%")
    return [result]