"""
ui/person_dialog.py
Dialog for adding a new person or editing an existing record.
Updated for new face_engine API: encode_face_from_bytes returns (vec, box).
"""
import os
import pickle
import traceback
import faulthandler
faulthandler.enable()

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QSpinBox, QTextEdit, QFileDialog,
    QGroupBox, QFrame, QSizePolicy, QMessageBox
)
from PyQt6.QtCore import Qt, QObject, QEvent
from .styles import *
from .widgets import PhotoLabel
from core.face_engine import encode_face_from_bytes
from database.db_manager import get_person_by_id, update_person, add_person

print("DEBUG: person_dialog imports OK")


class _ClickFilter(QObject):
    """
    Safe PyQt6 click detection via installEventFilter.
    Avoids the hard segfault caused by monkey-patching mousePressEvent
    on C++ Qt widgets in PyQt6.
    """
    def __init__(self, callback):
        super().__init__()
        self._cb = callback

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.MouseButtonRelease:
            self._cb()
            return True
        return False


class PersonDialog(QDialog):
    def __init__(self, parent=None, person_id: int = None):
        super().__init__(parent)
        print(f"DEBUG: PersonDialog init, person_id={person_id}")
        self._person_id      = person_id
        self._photo_bytes    = None
        self._photo_changed  = False   # True only when user picks a NEW photo
        self._existing_enc   = None    # encoding blob already in DB (edit mode)
        self._build_ui()
        if person_id:
            self._load_record(person_id)
        self.setWindowTitle("Edit Record" if person_id else "New Record")
        self.setMinimumSize(560, 600)
        self.setStyleSheet(f"background-color: {BG_DARK}; color: {TEXT_PRIMARY};")
        print("DEBUG: PersonDialog init complete")

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel("▮  PERSON RECORD" if not self._person_id else "▮  EDIT RECORD")
        title.setStyleSheet(
            f"color: {ACCENT_BLUE}; font-size: 13px; font-weight: bold; "
            f"letter-spacing: 2px; background: transparent; border: none;"
        )
        root.addWidget(title)

        cols = QHBoxLayout()
        cols.setSpacing(16)

        # ── Photo column ──────────────────────────────────────────────────────
        photo_col = QVBoxLayout()
        photo_col.setSpacing(8)

        self.photo_lbl = PhotoLabel("CLICK\nTO ADD\nPHOTO", (160, 190))
        self.photo_lbl.setCursor(Qt.CursorShape.PointingHandCursor)
        self._photo_filter = _ClickFilter(self._pick_photo)   # keep ref!
        self.photo_lbl.installEventFilter(self._photo_filter)
        photo_col.addWidget(self.photo_lbl)

        pick_btn = QPushButton("SELECT PHOTO")
        pick_btn.clicked.connect(self._pick_photo)
        photo_col.addWidget(pick_btn)
        photo_col.addStretch()
        cols.addLayout(photo_col)

        # ── Fields column ─────────────────────────────────────────────────────
        fields_col = QVBoxLayout()
        fields_col.setSpacing(8)

        def field(label, widget):
            lbl = QLabel(label)
            lbl.setStyleSheet(
                f"color: {TEXT_SECONDARY}; font-size: 10px; "
                f"letter-spacing: 1px; background: transparent; border: none;"
            )
            fields_col.addWidget(lbl)
            fields_col.addWidget(widget)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Full Name")
        field("FULL NAME *", self.name_edit)

        self.id_edit = QLineEdit()
        self.id_edit.setPlaceholderText("e.g. 456-78-9123")
        field("ID NUMBER *", self.id_edit)

        age_gender = QHBoxLayout()
        self.age_spin = QSpinBox()
        self.age_spin.setRange(0, 120)
        self.age_spin.setValue(30)
        self.gender_combo = QComboBox()
        self.gender_combo.addItems(["Male", "Female", "Non-binary", "Unknown"])
        age_gender.addWidget(self.age_spin, 1)
        age_gender.addWidget(self.gender_combo, 1)
        lbl2 = QLabel("AGE / GENDER")
        lbl2.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: 10px; "
            f"letter-spacing: 1px; background: transparent; border: none;"
        )
        fields_col.addWidget(lbl2)
        fields_col.addLayout(age_gender)

        self.nat_edit = QLineEdit()
        self.nat_edit.setPlaceholderText("e.g. United States")
        field("NATIONALITY", self.nat_edit)

        self.addr_edit = QLineEdit()
        self.addr_edit.setPlaceholderText("Street address")
        field("ADDRESS", self.addr_edit)

        self.last_seen_edit = QLineEdit()
        self.last_seen_edit.setPlaceholderText("MM/DD/YYYY")
        field("LAST SEEN", self.last_seen_edit)

        self.status_combo = QComboBox()
        self.status_combo.addItems([
            "No Record", "Felony Warrant", "Arrest Record",
            "Under Investigation", "Interpol Notice",
            "Person of Interest", "Witness"
        ])
        field("STATUS", self.status_combo)

        cols.addLayout(fields_col, 1)
        root.addLayout(cols)

        # ── Notes ─────────────────────────────────────────────────────────────
        notes_lbl = QLabel("CASE NOTES")
        notes_lbl.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: 10px; "
            f"letter-spacing: 1px; background: transparent; border: none;"
        )
        root.addWidget(notes_lbl)
        self.notes_edit = QTextEdit()
        self.notes_edit.setFixedHeight(80)
        root.addWidget(self.notes_edit)

        enc_lbl = QLabel(
            "ℹ  Face encoding is computed automatically on save. "
            "For best results use a clear, well-lit frontal photo."
        )
        enc_lbl.setStyleSheet(
            f"color: {TEXT_DIM}; font-size: 10px; "
            f"background: transparent; border: none;"
        )
        enc_lbl.setWordWrap(True)
        root.addWidget(enc_lbl)

        # ── Buttons ───────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("CANCEL")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("SAVE RECORD")
        save_btn.setObjectName("btn_primary")

        def safe_save():
            try:
                print("DEBUG: save button clicked")
                self._save()
            except Exception as e:
                print(f"DEBUG: unhandled crash in _save: {e}")
                traceback.print_exc()
                QMessageBox.critical(self, "Crash", str(e))

        save_btn.clicked.connect(safe_save)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        root.addLayout(btn_row)

    def _pick_photo(self):
        print("DEBUG: _pick_photo called")
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Photo", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.webp)"
        )
        if not path:
            return
        with open(path, 'rb') as f:
            self._photo_bytes   = f.read()
            self._photo_changed = True   # user explicitly picked a new photo
        print(f"DEBUG: photo loaded {len(self._photo_bytes)} bytes  "
              f"file={os.path.basename(path)}")
        self.photo_lbl.set_photo_bytes(self._photo_bytes)

    def _load_record(self, person_id: int):
        print(f"DEBUG: loading record id={person_id}")
        rec = get_person_by_id(person_id)
        if not rec:
            print("DEBUG: record not found")
            return
        self.name_edit.setText(rec.get('full_name', ''))
        self.id_edit.setText(rec.get('id_number', ''))
        self.age_spin.setValue(int(rec.get('age') or 0))
        idx = self.gender_combo.findText(rec.get('gender', 'Male'))
        if idx >= 0:
            self.gender_combo.setCurrentIndex(idx)
        self.nat_edit.setText(rec.get('nationality', ''))
        self.addr_edit.setText(rec.get('address', ''))
        self.last_seen_edit.setText(rec.get('last_seen', ''))
        idx2 = self.status_combo.findText(rec.get('status', 'No Record'))
        if idx2 >= 0:
            self.status_combo.setCurrentIndex(idx2)
        self.notes_edit.setPlainText(rec.get('notes', ''))
        if rec.get('photo_blob'):
            # SQLite can return memoryview or sqlite3.Binary — always normalise to plain bytes
            raw = rec['photo_blob']
            self._photo_bytes   = bytes(raw) if not isinstance(raw, bytes) else raw
            self._photo_changed = False   # loaded from DB — not a new pick
            self.photo_lbl.set_photo_bytes(self._photo_bytes)
        if rec.get('encoding'):
            raw_enc = rec['encoding']
            self._existing_enc = bytes(raw_enc) if not isinstance(raw_enc, bytes) else raw_enc
        print("DEBUG: record loaded OK")

    def _save(self):
        print("DEBUG: _save started")
        name   = self.name_edit.text().strip()
        id_num = self.id_edit.text().strip()

        if not name or not id_num:
            QMessageBox.warning(self, "Validation",
                                "Full Name and ID Number are required.")
            return

        data = {
            'full_name':   name,
            'id_number':   id_num,
            'age':         self.age_spin.value(),
            'gender':      self.gender_combo.currentText(),
            'nationality': self.nat_edit.text().strip(),
            'address':     self.addr_edit.text().strip(),
            'last_seen':   self.last_seen_edit.text().strip(),
            'status':      self.status_combo.currentText(),
            'notes':       self.notes_edit.toPlainText().strip(),
            'photo_blob':  self._photo_bytes,
            'encoding':    self._existing_enc,   # default: keep existing encoding
        }

        if self._photo_bytes and self._photo_changed:
            # User picked a NEW photo — re-encode from scratch
            print("DEBUG: new photo selected, computing face encoding...")
            try:
                enc, box = encode_face_from_bytes(self._photo_bytes)
                if enc is not None:
                    data['encoding'] = pickle.dumps(enc)
                    print(f"DEBUG: encoding OK  dim={len(enc)}  box={box}")
                else:
                    print("DEBUG: no face detected — saving photo without encoding")
                    QMessageBox.information(
                        self, "No Face Detected",
                        "No face was detected in this photo.\n"
                        "The record will be saved without a face encoding.\n\n"
                        "For face search to work, please use a clear,\n"
                        "well-lit photo where the face is visible."
                    )
                    data['encoding'] = None   # wipe old encoding — photo changed but no face
            except Exception as e:
                print(f"DEBUG: encoding error (non-fatal): {e}")
                traceback.print_exc()
        elif not self._photo_bytes:
            print("DEBUG: no photo at all, skipping encoding")
            data['encoding'] = None
        else:
            print("DEBUG: photo unchanged — keeping existing encoding")

        print("DEBUG: saving to database...")
        try:
            if self._person_id:
                print(f"DEBUG: updating record id={self._person_id}")
                update_person(self._person_id, data)

                # ── Guaranteed photo + encoding save ──────────────────────────
                # update_person may or may not include photo_blob in its SQL.
                # We do a direct targeted UPDATE here to make absolutely sure
                # the photo and encoding are persisted on every edit save.
                if self._photo_bytes is not None:
                    from database.db_manager import get_connection as get_db_connection
                    try:
                        conn = get_db_connection()
                        conn.execute(
                            "UPDATE persons SET photo_blob=?, encoding=? WHERE id=?",
                            (
                                self._photo_bytes,
                                data.get('encoding'),
                                self._person_id,
                            )
                        )
                        conn.commit()
                        print("DEBUG: photo_blob + encoding force-saved OK")
                    except Exception as db_e:
                        print(f"DEBUG: force-save photo failed: {db_e}")
                        traceback.print_exc()

                print("DEBUG: record updated OK")
            else:
                print("DEBUG: inserting new record")
                add_person(data)
                print("DEBUG: new record inserted OK")
        except Exception as e:
            print(f"DEBUG: database error: {e}")
            traceback.print_exc()
            QMessageBox.critical(self, "Save Error", str(e))
            return

        print("DEBUG: calling self.accept()")
        self.accept()