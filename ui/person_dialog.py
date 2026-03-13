"""
ui/person_dialog.py
Dialog for adding a new person or editing an existing record.
"""
import os
import io
import pickle
import traceback
import faulthandler
import numpy as np
faulthandler.enable()

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QSpinBox, QTextEdit, QFileDialog,
    QGridLayout, QGroupBox, QFrame, QSizePolicy, QMessageBox
)
from PyQt6.QtCore import Qt
from .styles import *
from .widgets import PhotoLabel
from core.face_engine import encode_face_from_bytes
from database.db_manager import get_person_by_id, update_person, add_person, get_connection

print("DEBUG: person_dialog imports OK")


class PersonDialog(QDialog):
    def __init__(self, parent=None, person_id: int = None):
        super().__init__(parent)
        print(f"DEBUG: PersonDialog init, person_id={person_id}")
        self._person_id   = person_id
        self._photo_bytes = None   # raw original bytes — NOT resized
        self._build_ui()
        if person_id:
            self._load_record(person_id)
        self.setWindowTitle("Edit Record" if person_id else "New Record")
        self.setMinimumSize(560, 600)
        self.setStyleSheet(f"background-color: {BG_DARK}; color: {TEXT_PRIMARY};")

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel("▮  PERSON RECORD" if not self._person_id else "▮  EDIT RECORD")
        title.setStyleSheet(f"color: {ACCENT_BLUE}; font-size: 13px; font-weight: bold; letter-spacing: 2px; background: transparent; border: none;")
        root.addWidget(title)

        cols = QHBoxLayout()
        cols.setSpacing(16)

        photo_col = QVBoxLayout()
        photo_col.setSpacing(8)
        self.photo_lbl = PhotoLabel("CLICK\nTO ADD\nPHOTO", (160, 190))
        self.photo_lbl.setCursor(Qt.CursorShape.PointingHandCursor)
        self.photo_lbl.mousePressEvent = lambda e: self._pick_photo()
        photo_col.addWidget(self.photo_lbl)

        pick_btn = QPushButton("SELECT PHOTO")
        pick_btn.clicked.connect(self._pick_photo)
        photo_col.addWidget(pick_btn)
        photo_col.addStretch()
        cols.addLayout(photo_col)

        fields_col = QVBoxLayout()
        fields_col.setSpacing(8)

        def field(label, widget):
            lbl = QLabel(label)
            lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 10px; letter-spacing: 1px; background: transparent; border: none;")
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
        lbl2.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 10px; letter-spacing: 1px; background: transparent; border: none;")
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

        notes_lbl = QLabel("CASE NOTES")
        notes_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 10px; letter-spacing: 1px; background: transparent; border: none;")
        root.addWidget(notes_lbl)
        self.notes_edit = QTextEdit()
        self.notes_edit.setFixedHeight(80)
        root.addWidget(self.notes_edit)

        enc_lbl = QLabel("ℹ  If a photo is provided, face encoding will be computed automatically on save.")
        enc_lbl.setStyleSheet(f"color: {TEXT_DIM}; font-size: 10px; background: transparent; border: none;")
        enc_lbl.setWordWrap(True)
        root.addWidget(enc_lbl)

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
                print("DEBUG: unhandled crash")
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

        # Read original bytes — do NOT resize or recompress
        # The face engine needs the full-resolution image for accurate detection
        with open(path, 'rb') as f:
            self._photo_bytes = f.read()

        print(f"DEBUG: photo loaded {len(self._photo_bytes)} bytes from {os.path.basename(path)}")
        self.photo_lbl.set_photo_bytes(self._photo_bytes)

    def _load_record(self, person_id: int):
        print(f"DEBUG: loading record {person_id}")
        rec = get_person_by_id(person_id)
        if not rec:
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
            self._photo_bytes = rec['photo_blob']
            self.photo_lbl.set_photo_bytes(self._photo_bytes)
        print("DEBUG: record loaded OK")

    def _save(self):
        print("DEBUG: _save started")
        name   = self.name_edit.text().strip()
        id_num = self.id_edit.text().strip()

        if not name or not id_num:
            QMessageBox.warning(self, "Validation", "Full Name and ID Number are required.")
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
            'encoding':    None,
        }

        if self._photo_bytes:
            print("DEBUG: computing face encoding on original full-res image...")
            try:
                enc = encode_face_from_bytes(self._photo_bytes)
                if enc is not None:
                    data['encoding'] = pickle.dumps(enc)
                    print(f"DEBUG: encoding OK, vector size={len(enc)}")
                else:
                    print("DEBUG: no face detected — saving record without encoding")
                    QMessageBox.information(
                        self, "No Face Detected",
                        "No face was detected in this photo.\n"
                        "The record will be saved without a face encoding.\n\n"
                        "For face search to work, use a clear frontal photo."
                    )
            except Exception as e:
                print(f"DEBUG: encoding error (non-fatal): {e}")
                traceback.print_exc()
        else:
            print("DEBUG: no photo, skipping encoding")

        print("DEBUG: saving to database...")
        try:
            if self._person_id:
                print(f"DEBUG: updating record id={self._person_id}")
                update_person(self._person_id, data)
                if self._photo_bytes:
                    conn = get_connection()
                    conn.execute(
                        "UPDATE persons SET photo_blob=?, encoding=? WHERE id=?",
                        (self._photo_bytes, data['encoding'], self._person_id)
                    )
                    conn.commit()
                    conn.close()
                    print("DEBUG: photo/encoding updated in DB")
            else:
                print("DEBUG: inserting new record")
                add_person(data)
                print("DEBUG: inserted OK")
        except Exception as e:
            print(f"DEBUG: DB error: {e}")
            traceback.print_exc()
            QMessageBox.critical(self, "Save Error", str(e))
            return

        print("DEBUG: calling accept()")
        self.accept()