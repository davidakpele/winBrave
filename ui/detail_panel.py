"""
ui/detail_panel.py
Right panel: full record detail for the selected person.
Includes photo, biographic data, status, notes, and quick actions.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QTextEdit, QSizePolicy, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from .styles import *
from .widgets import PhotoLabel, StatusBadge, SectionHeader, InfoRow


class DetailPanel(QWidget):
    open_edit = pyqtSignal(int)   # request edit dialog for person_id
    deleted   = pyqtSignal(int)   # person was deleted

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_id = None
        self._build_ui()
        self._show_empty()

    def _build_ui(self):
        self.setMinimumWidth(300)
        self.setStyleSheet(f"background-color: {BG_DARK}; border-left: 1px solid {BORDER};")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        self.hdr = SectionHeader("MATCH DETAILS", ACCENT_AMBER)
        root.addWidget(self.hdr)

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        inner = QWidget()
        inner.setStyleSheet("background: transparent;")
        self.inner_layout = QVBoxLayout(inner)
        self.inner_layout.setContentsMargins(12, 12, 12, 12)
        self.inner_layout.setSpacing(10)

        # --- Photo + name block ---
        photo_row = QHBoxLayout()
        photo_row.setSpacing(12)

        self.photo = PhotoLabel("NO PHOTO", (120, 140))
        photo_row.addWidget(self.photo)

        name_block = QVBoxLayout()
        name_block.setSpacing(4)
        self.name_lbl = QLabel("—")
        self.name_lbl.setStyleSheet(f"color: {TEXT_WHITE}; font-size: 16px; font-weight: bold; background: transparent; border: none;")
        self.name_lbl.setWordWrap(True)

        self.id_lbl = QLabel("ID: —")
        self.id_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px; background: transparent; border: none;")

        self.status_badge = StatusBadge("")
        self.conf_lbl = QLabel("")
        self.conf_lbl.setStyleSheet(f"color: {ACCENT_CYAN}; font-size: 11px; background: transparent; border: none;")

        name_block.addWidget(self.name_lbl)
        name_block.addWidget(self.id_lbl)
        name_block.addWidget(self.status_badge)
        name_block.addWidget(self.conf_lbl)
        name_block.addStretch()
        photo_row.addLayout(name_block, 1)
        self.inner_layout.addLayout(photo_row)

        # Divider
        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet(f"color: {BORDER}; background: {BORDER}; border: none; max-height: 1px;")
        self.inner_layout.addWidget(div)

        # --- Bio fields ---
        bio_lbl = QLabel("BIOGRAPHIC DATA")
        bio_lbl.setStyleSheet(f"color: {TEXT_DIM}; font-size: 10px; letter-spacing: 2px; background: transparent; border: none;")
        self.inner_layout.addWidget(bio_lbl)

        self.row_age         = InfoRow("Age")
        self.row_gender      = InfoRow("Gender")
        self.row_nationality = InfoRow("Nationality")
        self.row_address     = InfoRow("Address")
        self.row_last_seen   = InfoRow("Last Seen")

        for row in [self.row_age, self.row_gender, self.row_nationality,
                    self.row_address, self.row_last_seen]:
            self.inner_layout.addWidget(row)

        # Divider
        div2 = QFrame()
        div2.setFrameShape(QFrame.Shape.HLine)
        div2.setStyleSheet(f"color: {BORDER}; background: {BORDER}; border: none; max-height: 1px;")
        self.inner_layout.addWidget(div2)

        # --- Notes ---
        notes_lbl = QLabel("CASE NOTES")
        notes_lbl.setStyleSheet(f"color: {TEXT_DIM}; font-size: 10px; letter-spacing: 2px; background: transparent; border: none;")
        self.inner_layout.addWidget(notes_lbl)

        self.notes_edit = QTextEdit()
        self.notes_edit.setReadOnly(True)
        self.notes_edit.setFixedHeight(80)
        self.notes_edit.setStyleSheet(f"""
            QTextEdit {{
                background-color: {BG_DARKEST};
                color: {TEXT_PRIMARY};
                border: 1px solid {BORDER};
                font-family: Consolas;
                font-size: 11px;
                padding: 6px;
            }}
        """)
        self.inner_layout.addWidget(self.notes_edit)

        self.inner_layout.addStretch()

        scroll.setWidget(inner)
        root.addWidget(scroll, 1)

        # --- Action bar ---
        action_bar = QFrame()
        action_bar.setFixedHeight(48)
        action_bar.setStyleSheet(f"""
            QFrame {{
                background-color: {BG_PANEL};
                border-top: 1px solid {BORDER};
                border-bottom: none; border-left: none; border-right: none;
                border-radius: 0;
            }}
        """)
        ab_layout = QHBoxLayout(action_bar)
        ab_layout.setContentsMargins(10, 6, 10, 6)
        ab_layout.setSpacing(8)

        self.edit_btn = QPushButton("EDIT RECORD")
        self.edit_btn.clicked.connect(lambda: self.open_edit.emit(self._current_id))
        self.edit_btn.setEnabled(False)

        self.del_btn = QPushButton("DELETE")
        self.del_btn.setObjectName("btn_danger")
        self.del_btn.clicked.connect(self._delete_person)
        self.del_btn.setEnabled(False)

        ab_layout.addWidget(self.edit_btn, 1)
        ab_layout.addWidget(self.del_btn)
        root.addWidget(action_bar)

    # ── Public API ─────────────────────────────────────────────────────────────

    def show_person(self, person_id: int, confidence: float = None):
        from database.db_manager import get_person_by_id
        record = get_person_by_id(person_id)
        if not record:
            return

        self._current_id = person_id
        self.hdr = self._update_header(record.get('full_name', ''))

        self.name_lbl.setText(record.get('full_name', '—'))
        self.id_lbl.setText(f"ID: {record.get('id_number', '—')}")
        self.status_badge.set_status(record.get('status', ''))

        if confidence is not None:
            self.conf_lbl.setText(f"CONFIDENCE:  {confidence:.1f}%")
        else:
            self.conf_lbl.setText("")

        if record.get('photo_blob'):
            self.photo.set_photo_bytes(record['photo_blob'])
        else:
            self.photo.clear_photo()

        self.row_age.set_value(str(record.get('age', '—')))
        self.row_gender.set_value(record.get('gender', '—'))
        self.row_nationality.set_value(record.get('nationality', '—'))
        self.row_address.set_value(record.get('address', '—'))
        self.row_last_seen.set_value(record.get('last_seen', '—'))
        self.notes_edit.setPlainText(record.get('notes', ''))

        self.edit_btn.setEnabled(True)
        self.del_btn.setEnabled(True)

    def _show_empty(self):
        self._current_id = None
        self.name_lbl.setText("SELECT A RECORD")
        self.id_lbl.setText("ID: —")
        self.status_badge.set_status("")
        self.conf_lbl.setText("")
        self.photo.clear_photo()
        self.row_age.set_value("—")
        self.row_gender.set_value("—")
        self.row_nationality.set_value("—")
        self.row_address.set_value("—")
        self.row_last_seen.set_value("—")
        self.notes_edit.setPlainText("")
        self.edit_btn.setEnabled(False)
        self.del_btn.setEnabled(False)

    def _update_header(self, name: str):
        # Update header label text dynamically
        # (SectionHeader doesn't expose a setText, so we find the label)
        pass

    def _delete_person(self):
        if self._current_id is None:
            return
        reply = QMessageBox.question(
            self, "Confirm Delete",
            "Permanently delete this record?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            from database.db_manager import delete_person
            delete_person(self._current_id)
            pid = self._current_id
            self._show_empty()
            self.deleted.emit(pid)
