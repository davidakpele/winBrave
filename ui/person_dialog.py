"""
ui/person_dialog.py
Dialog for adding a new person or editing an existing record.
"""
import os
import faulthandler
faulthandler.enable()

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QSpinBox, QTextEdit, QFileDialog,
    QGridLayout, QGroupBox, QFrame, QSizePolicy, QMessageBox
)
from PyQt6.QtCore import Qt
from .styles import *
from .widgets import PhotoLabel


class PersonDialog(QDialog):
    def __init__(self, parent=None, person_id: int = None):
        super().__init__(parent)
        self._person_id = person_id
        self._photo_bytes = None
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
                print("--- SAVE BUTTON CLICKED ---")
                self._save()
            except Exception as e:
                import traceback
                print("=== UNHANDLED SAVE CRASH ===")
                traceback.print_exc()
                QMessageBox.critical(self, "Crash", str(e))

        save_btn.clicked.connect(safe_save)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        root.addLayout(btn_row)

    def _pick_photo(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Photo", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.webp)"
        )
        if not path:
            return
        print(f"Photo selected: {path}")
        with open(path, 'rb') as f:
            raw = f.read()
        try:
            from PIL import Image
            import io
            img = Image.open(io.BytesIO(raw)).convert("RGB")
            img.thumbnail((300, 300), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=85)
            self._photo_bytes = buf.getvalue()
            print(f"Photo resized OK: {len(self._photo_bytes)} bytes")
        except Exception as e:
            print(f"Photo resize error: {e}")
            self._photo_bytes = raw
        self.photo_lbl.set_photo_bytes(self._photo_bytes)

    def _load_record(self, person_id: int):
        from database.db_manager import get_person_by_id
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

    def _save(self):
        print("STEP 1: reading form fields")
        name = self.name_edit.text().strip()
        id_num = self.id_edit.text().strip()
        print(f"STEP 2: name={name}, id={id_num}")

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
        print("STEP 3: data dict built")

        if self._photo_bytes:
            print("STEP 4: computing face encoding...")
            try:
                import io
                from PIL import Image
                import numpy as np
                print("STEP 4a: PIL/numpy imported")
                img = Image.open(io.BytesIO(self._photo_bytes)).convert("RGB")
                arr = np.array(img)
                print(f"STEP 4b: image array shape={arr.shape}")
                import face_recognition
                print("STEP 4c: face_recognition imported")
                encs = face_recognition.face_encodings(arr)
                print(f"STEP 4d: encoding done, {len(encs)} face(s) found")
                if encs:
                    import pickle
                    data['encoding'] = pickle.dumps(encs[0])
                    print("STEP 4e: encoding pickled")
            except Exception as e:
                import traceback
                print(f"STEP 4 ERROR: {e}")
                traceback.print_exc()
        else:
            print("STEP 4: no photo, skipping encoding")

        print("STEP 5: saving to database...")
        try:
            if self._person_id:
                print(f"STEP 5a: updating person id={self._person_id}")
                from database.db_manager import update_person
                update_person(self._person_id, data)
                if self._photo_bytes:
                    from database.db_manager import get_connection
                    import pickle
                    conn = get_connection()
                    conn.execute(
                        "UPDATE persons SET photo_blob=?, encoding=? WHERE id=?",
                        (self._photo_bytes, data['encoding'], self._person_id)
                    )
                    conn.commit()
                    conn.close()
            else:
                print("STEP 5b: inserting new person")
                from database.db_manager import add_person
                add_person(data)
            print("STEP 6: saved successfully, closing dialog")
        except Exception as e:
            import traceback
            print(f"STEP 5 ERROR: {e}")
            traceback.print_exc()
            QMessageBox.critical(self, "Save Error", str(e))
            return

        self.accept()
        print("STEP 7: dialog accepted")