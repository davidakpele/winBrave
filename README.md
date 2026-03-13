# FaceSearch Pro — Research Edition

A desktop facial recognition search application built with PyQt6, designed for security research and learning.

## Screenshot
Matches the dark tactical UI from the reference mockup — with face scan animation, match cards, confidence bars, status badges, and a full record detail panel.

---

## Features

| Feature | Details |
|---|---|
| **Face Search** | Upload a photo → encode biometrics → search local DB |
| **Text Search** | Search by name, ID, nationality, status, address, notes |
| **Match Cards** | Sorted by confidence, with status colour-coding |
| **Detail Panel** | Full biographic view, case notes, actions |
| **Add / Edit / Delete** | Full CRUD on person records |
| **Auto Encoding** | Face encoding computed on photo upload |
| **Dark Tactical UI** | Scan-line animation, pulsing dots, confidence bars |
| **Local SQLite DB** | All data stays on your machine |

---

## Project Structure

```
facerec/
├── main.py                 # Entry point
├── requirements.txt
├── setup_windows.bat       # One-click Windows installer
├── facerec.db              # Created automatically on first run
├── core/
│   └── face_engine.py      # face_recognition wrapper
├── database/
│   └── db_manager.py       # SQLite CRUD layer
└── ui/
    ├── main_window.py      # Root window + menu
    ├── search_panel.py     # Left: image upload + controls
    ├── results_panel.py    # Centre: match cards
    ├── detail_panel.py     # Right: record detail
    ├── person_dialog.py    # Add/Edit dialog
    ├── widgets.py          # PhotoLabel, MatchCard, StatusBadge, etc.
    └── styles.py           # Colour palette + global stylesheet
```

---

## Windows Setup

### Prerequisites
- Python 3.10 or 3.11 (recommended)
- [Visual Studio Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/) with **C++ workload** — required for dlib

### Quick Setup
```bat
setup_windows.bat
```

### Manual Setup
```bat
pip install cmake
pip install dlib           # see note below if this fails
pip install face_recognition PyQt6 opencv-python numpy Pillow
```

#### If dlib fails to build on Windows:
Download a prebuilt `.whl` for your Python version from:
https://github.com/z-mahmud22/Dlib_Windows_Python3.x

Then install it:
```bat
pip install dlib-19.24.1-cp311-cp311-win_amd64.whl
```

---

## Running the App

```bat
python main.py
```

---

## How to Use

### Face Search
1. Click the photo zone in the left panel (or drag & drop)
2. Select a query image (clear frontal face photo)
3. Adjust the **tolerance slider** (lower = stricter matching)
4. Click **RUN FACE SEARCH**
5. Matching records appear in the centre panel
6. Click any card to view full details on the right

### Text Search
- Type a name, ID number, nationality, or status in the **Text Search** box
- Press Enter or click **Search Database**

### Adding Records
- Click **+ NEW RECORD** in the title bar (or File → New Record)
- Fill in the form and select a photo
- The face encoding is computed automatically when a photo is provided

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

- **`core/face_engine.py`** — All face_recognition calls are isolated here. The engine is lazily imported so the app launches even if libraries aren't installed yet.
- **`database/db_manager.py`** — Pure SQLite; no ORM dependency. Face encodings are stored as pickled numpy arrays in a BLOB column.
- **Thread safety** — Face search runs in a `QThread` worker to keep the UI responsive during heavy biometric computation.
- **Tolerance** — The default 0.55 is a good balance. Lower (0.40) = fewer false positives. Higher (0.65) = more permissive matching.

---

## Disclaimer

This tool is for **security research and educational use only**. It operates entirely locally — no data is transmitted externally. Do not use for surveillance, profiling, or any purpose that violates applicable laws or privacy rights.
