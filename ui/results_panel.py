"""
ui/results_panel.py
Centre panel: shows match cards from face search or text search results.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
    QFrame, QPushButton
)
from PyQt6.QtCore import Qt, pyqtSignal

from .styles import *
from .widgets import MatchCard


class ResultsPanel(QWidget):
    person_selected = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cards = []
        self._selected_id = None
        self._build_ui()

    def _build_ui(self):
        self.setMinimumWidth(360)
        self.setStyleSheet(f"background-color: {BG_DARK}; border: none;")

        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(0, 0, 0, 0)
        self._root.setSpacing(0)

        # Header
        hdr = QWidget()
        hdr.setFixedHeight(32)
        hdr.setStyleSheet(f"background-color: {BG_PANEL}; border-bottom: 1px solid {BORDER};")
        hdr_row = QHBoxLayout(hdr)
        hdr_row.setContentsMargins(10, 0, 10, 0)

        bar = QFrame()
        bar.setFixedSize(3, 16)
        bar.setStyleSheet(f"background: {ACCENT_CYAN}; border: none;")

        title = QLabel("DATABASE RESULTS")
        title.setStyleSheet(f"color: {ACCENT_CYAN}; font-size: 10px; font-weight: bold; letter-spacing: 2px; background: transparent; border: none;")

        self.count_lbl = QLabel("")
        self.count_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 10px; background: transparent; border: none;")

        hdr_row.addWidget(bar)
        hdr_row.addWidget(title)
        hdr_row.addStretch()
        hdr_row.addWidget(self.count_lbl)
        self._root.addWidget(hdr)

        # Sub-header
        self.sub_hdr = QLabel("— AWAITING SEARCH —")
        self.sub_hdr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sub_hdr.setFixedHeight(24)
        self._set_subhdr_idle()
        self._root.addWidget(self.sub_hdr)

        # Scroll area
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self._root.addWidget(self.scroll, 1)

        # Show all button
        show_all = QPushButton("SHOW ALL DATABASE RECORDS")
        show_all.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                border-top: 1px solid {BORDER};
                color: {TEXT_SECONDARY};
                font-size: 10px;
                letter-spacing: 1px;
                padding: 8px;
            }}
            QPushButton:hover {{ color: {ACCENT_BLUE}; }}
        """)
        show_all.clicked.connect(self._load_all)
        self._root.addWidget(show_all)

        self._reset_container()

    def _reset_container(self):
        """Destroy old scroll content and create a fresh empty container."""
        self._cards = []
        old = self.scroll.takeWidget()
        if old:
            old.deleteLater()

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        self._layout = QVBoxLayout(container)
        self._layout.setContentsMargins(10, 10, 10, 10)
        self._layout.setSpacing(8)
        self._layout.addStretch()
        self.scroll.setWidget(container)

    def _set_subhdr_idle(self):
        self.sub_hdr.setText("— AWAITING SEARCH —")
        self.sub_hdr.setStyleSheet(f"""
            color: {TEXT_DIM}; font-size: 10px; letter-spacing: 2px;
            background-color: {BG_DARKEST};
            border-bottom: 1px solid {BORDER};
            border-top: none; border-left: none; border-right: none;
        """)

    def _set_subhdr_active(self, text: str):
        self.sub_hdr.setText(text)
        self.sub_hdr.setStyleSheet(f"""
            color: {ACCENT_CYAN}; font-size: 10px; letter-spacing: 2px;
            background-color: {BG_DARKEST};
            border-bottom: 1px solid {BORDER};
            border-top: none; border-left: none; border-right: none;
        """)

    def show_results(self, records: list, search_type: str = "FACE MATCH"):
        # Wipe everything and start completely fresh
        self._reset_container()
        self._selected_id = None
        self._set_subhdr_active(f"— {search_type.upper()} RESULTS —")

        if not records:
            self.count_lbl.setText("NO MATCHES")
            self._show_not_found()
            return

        self.count_lbl.setText(f"{len(records)} MATCH{'ES' if len(records) != 1 else ''} FOUND")

        for rec in records:
            card = MatchCard(rec)
            card.clicked.connect(self._card_clicked)
            self._cards.append(card)
            self._layout.insertWidget(self._layout.count() - 1, card)

        if records:
            self._card_clicked(records[0].get('id', -1))

    def show_empty(self):
        self._reset_container()
        self.count_lbl.setText("")
        self._set_subhdr_idle()

    def _show_not_found(self):
        w = QWidget()
        w.setStyleSheet("background: transparent; border: none;")
        lay = QVBoxLayout(w)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.setSpacing(12)

        icon = QLabel("⊘")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet(f"color: {ACCENT_RED}; font-size: 40px; background: transparent; border: none;")

        msg = QLabel("USER NOT FOUND ON THE SYSTEM")
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        msg.setStyleSheet(f"color: {ACCENT_RED}; font-size: 12px; font-weight: bold; letter-spacing: 2px; background: transparent; border: none;")

        hint = QLabel("No matching records in the database.\nTry adjusting the tolerance slider\nor add this person as a new record.")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet(f"color: {TEXT_DIM}; font-size: 11px; background: transparent; border: none;")
        hint.setWordWrap(True)

        lay.addStretch()
        lay.addWidget(icon)
        lay.addWidget(msg)
        lay.addWidget(hint)
        lay.addStretch()

        self._layout.insertWidget(0, w)

    def _card_clicked(self, person_id: int):
        self._selected_id = person_id
        for card in self._cards:
            card.set_selected(card._id == person_id)
        self.person_selected.emit(person_id)

    def _load_all(self):
        from database.db_manager import get_all_persons
        records = get_all_persons()
        self.show_results(records, "ALL RECORDS")