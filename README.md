# FaceSearch Pro — Research Edition

A desktop facial recognition search application built with PyQt6, designed for security research and learning.

---

## Features

| Feature | Details |
|---|---|
| **Face Search** | Upload a photo → detect face → embed face crop → search local DB |
| **Deep Face Scan** | Scan animation locks onto the detected face region only — dims everything outside it |
| **5-Second Countdown** | Biometric matching delay with live countdown badge on the scan overlay |
| **Text Search** | Search by name, ID, nationality, status, address, notes |
| **Match Rating** | Results rated as EXACT / STRONG / CLOSE / POSSIBLE MATCH with colour coding |
| **Confidence & Diff** | Each result shows Match % and Diff % (e.g. Match 82.4% · Diff 17.6%) |
| **Match Cards** | Sorted by confidence, with status colour-coding |
| **Detail Panel** | Full biographic view, case notes, actions |
| **Add / Edit / Delete** | Full CRUD on person records |
| **Auto Encoding** | Face encoding computed on photo upload — face crop only, not full image |
| **65% Minimum Match** | Hard floor — results below 65% confidence are never returned |
| **Dark Tactical UI** | Scan-line animation, pulsing dots, confidence bars, rating banners |
| **Local SQLite DB** | All data stays on your machine |

---

## Project Structure

```
facerec/
├── main.py                 # Entry point
├── requirements.txt
├── setup_windows.bat       # One-click Windows installer
├── facerec.db              # Created automatically on first run
├── models/                 # Downloaded automatically on first run
│   ├── deploy.prototxt
│   ├── res10_300x300_ssd_iter_140000.caffemodel
│   └── openface.nn4.small2.v1.t7
├── core/
│   └── face_engine.py      # OpenCV DNN face detection + OpenFace embedding
├── database/
│   └── db_manager.py       # SQLite CRUD layer
└── ui/
    ├── main_window.py      # Root window + menu
    ├── search_panel.py     # Left: image upload, deep scan animation, controls
    ├── results_panel.py    # Centre: match cards + rating banner
    ├── detail_panel.py     # Right: record detail
    ├── person_dialog.py    # Add/Edit dialog
    ├── widgets.py          # PhotoLabel, MatchCard, StatusBadge, etc.
    └── styles.py           # Colour palette + global stylesheet
```

---

## Windows Setup

### Prerequisites
- Python 3.10 or 3.11 (recommended)
- OpenCV and NumPy (no dlib or face_recognition required)

### Quick Setup
```bat
pip install PyQt6 opencv-python numpy Pillow
```

### Model Download
Face detection and embedding models are downloaded automatically on first launch into the `models/` folder. No manual steps required. If a download fails, run the app again and it will retry.

---

## Running the App

```bat
python main.py
```

---

## How to Use

### Face Search
1. Click the photo zone in the left panel (or use **SELECT PHOTO**)
2. Select a query image — use a clear, well-lit frontal face photo
3. Adjust the **tolerance slider** (lower = stricter matching)
4. Click **▶ RUN FACE SEARCH**
5. The scan runs in two phases:
   - **Phase 1 — Full scan:** cyan grid sweeps the whole image while the face is located
   - **Phase 2 — Deep scan:** the overlay locks onto the face region, dims the surroundings, and runs a focused green scan inside the face box only
6. A 5-second countdown runs while biometrics are matched against the database
7. Results appear in the centre panel with a rating banner

### Reading Match Results

The rating banner above the result cards shows:

| Rating | Confidence | Colour |
|---|---|---|
| EXACT MATCH | 92%+ | Green |
| STRONG MATCH | 82–91% | Green |
| CLOSE MATCH | 75–81% | Yellow |
| POSSIBLE MATCH | 65–74% | Orange |

Below the label, the banner shows e.g. `Match  82.4%  ·  Diff  17.6%`.

Results below **65% confidence** are never shown regardless of the tolerance slider setting.

### Text Search
- Type a name, ID number, nationality, or status in the **Text Search** box
- Press Enter or click **SEARCH DATABASE**

### Adding Records
- Click **+ NEW RECORD** in the title bar
- Fill in the form and select a photo
- The face encoding is computed automatically from the face crop of the uploaded photo
- If no face is detected in the photo, the record is saved without an encoding (it will not appear in face search results)

### Status Codes

| Status | Colour |
|---|---|
| Felony Warrant | Red |
| Arrest Record | Amber |
| Under Investigation | Amber |
| Interpol Notice | Red |
| Person of Interest | Yellow |
| Witness | Blue |
| No Record | Teal |

---

## Architecture Notes

### Face Engine (`core/face_engine.py`)
The engine uses **OpenCV DNN** for two tasks:

1. **Detection** — ResNet SSD (`res10_300x300_ssd_iter_140000.caffemodel`) locates the face bounding box in the image. The image is scaled to 600px on its longest side before detection for accuracy. A minimum detector confidence of 50% is required.

2. **Embedding** — The detected face crop (with 10% padding) is passed to the **OpenFace** network (`openface.nn4.small2.v1.t7`) which produces a 128-dimensional vector representing the face. The full image is never passed to the embedder — only the cropped face region.

Matching uses **cosine distance** between stored and query embeddings. The hard minimum of 65% confidence cannot be bypassed by the tolerance slider.

### Encoding Storage
Face encodings are stored as pickled NumPy arrays in a BLOB column in SQLite. Both pickled bytes and raw NumPy arrays are handled during matching for backward compatibility.

### Thread Safety
Face search runs in a `QThread` worker to keep the UI responsive. The worker emits Qt signals to update the scan overlay and countdown badge from the main thread safely.

### PyQt6 Compatibility
`mousePressEvent` is **not** monkey-patched on any widget. PyQt6 is stricter than PyQt5 — overriding C++ virtual methods via instance assignment causes a hard segfault. All click detection uses `installEventFilter` with a `QObject` subclass (`_ClickFilter`) stored as an instance attribute to prevent garbage collection.

### Tolerance Slider
The slider range is 0.30–0.75 (cosine distance). Lower values require faces to be more similar before a match is returned. The 65% confidence hard floor applies regardless of slider position.

---

## Disclaimer

This tool is for **security research and educational use only**. It operates entirely locally — no data is transmitted externally. Do not use for surveillance, profiling, or any purpose that violates applicable laws or privacy rights.