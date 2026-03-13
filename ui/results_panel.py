"""
ui/results_panel.py
Centre panel: shows match cards from face search or text search results.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
    QFrame, QSizePolicy, QPushButton
)
from PyQt6.QtCore import Qt, pyqtSignal

from .styles import *
from .widgets import MatchCard, SectionHeader, StatusBadge


class ResultsPanel(QWidget):
    person_selected = pyqtSignal(int)   # person DB id

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cards = []
        self._selected_id = None
        self._build_ui()

    def _build_ui(self):
        self.setMinimumWidth(360)
        self.setStyleSheet(f"background-color: {BG_DARK}; border: none;")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header row
        hdr_widget = QWidget()
        hdr_widget.setFixedHeight(32)
        hdr_widget.setStyleSheet(f"background-color: {BG_PANEL}; border-bottom: 1px solid {BORDER};")
        hdr_row = QHBoxLayout(hdr_widget)
        hdr_row.setContentsMargins(10, 0, 10, 0)

        bar = QFrame()
        bar.setFixedSize(3, 16)
        bar.setStyleSheet(f"background: {ACCENT_CYAN}; border: none;")

        self.title_lbl = QLabel("DATABASE RESULTS")
        self.title_lbl.setStyleSheet(f"color: {ACCENT_CYAN}; font-size: 10px; font-weight: bold; letter-spacing: 2px; background: transparent; border: none;")

        self.count_lbl = QLabel("")
        self.count_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 10px; background: transparent; border: none;")

        hdr_row.addWidget(bar)
        hdr_row.addWidget(self.title_lbl)
        hdr_row.addStretch()
        hdr_row.addWidget(self.count_lbl)
        root.addWidget(hdr_widget)

        # Sub-header (match type indicator)
        self.sub_hdr = QLabel("— AWAITING SEARCH —")
        self.sub_hdr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sub_hdr.setFixedHeight(24)
        self.sub_hdr.setStyleSheet(f"""
            color: {TEXT_DIM};
            font-size: 10px;
            letter-spacing: 2px;
            background-color: {BG_DARKEST};
            border-bottom: 1px solid {BORDER};
            border-top: none; border-left: none; border-right: none;
        """)
        root.addWidget(self.sub_hdr)

        # Scroll area
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self.cards_container = QWidget()
        self.cards_container.setStyleSheet("background: transparent;")
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(10, 10, 10, 10)
        self.cards_layout.setSpacing(8)
        self.cards_layout.addStretch()

        self.scroll.setWidget(self.cards_container)
        root.addWidget(self.scroll, 1)

        # Bottom: show-all button
        self.show_all_btn = QPushButton("SHOW ALL DATABASE RECORDS")
        self.show_all_btn.setStyleSheet(f"""
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
        self.show_all_btn.clicked.connect(self._load_all)
        root.addWidget(self.show_all_btn)

    # ── Public API ─────────────────────────────────────────────────────────────

    def show_results(self, records: list, search_type: str = "FACE MATCH"):
        self._clear_cards()
        self._selected_id = None

        count = len(records)
        self.count_lbl.setText(f"{count} MATCH{'ES' if count != 1 else ''} FOUND")
        self.sub_hdr.setText(f"— {search_type.upper()} RESULTS —")
        self.sub_hdr.setStyleSheet(f"""
            color: {ACCENT_CYAN};
            font-size: 10px;
            letter-spacing: 2px;
            background-color: {BG_DARKEST};
            border-bottom: 1px solid {BORDER};
            border-top: none; border-left: none; border-right: none;
        """)

        if not records:
            lbl = QLabel("No matches found.")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px; padding: 40px; background: transparent; border: none;")
            self.cards_layout.insertWidget(0, lbl)
            return

        for rec in records:
            card = MatchCard(rec)
            card.clicked.connect(self._card_clicked)
            self._cards.append(card)
            self.cards_layout.insertWidget(len(self._cards) - 1, card)

        # Auto-select first
        if records:
            self._card_clicked(records[0].get('id', -1))

    def show_empty(self):
        self._clear_cards()
        self.count_lbl.setText("")
        self.sub_hdr.setText("— AWAITING SEARCH —")
        self.sub_hdr.setStyleSheet(f"""
            color: {TEXT_DIM}; font-size: 10px; letter-spacing: 2px;
            background-color: {BG_DARKEST};
            border-bottom: 1px solid {BORDER};
            border-top: none; border-left: none; border-right: none;
        """)

    # ── Private ────────────────────────────────────────────────────────────────

    def _clear_cards(self):
        for card in self._cards:
            card.deleteLater()
        self._cards.clear()
        # Remove any non-card widgets (e.g. "no matches" labels)
        while self.cards_layout.count() > 1:
            item = self.cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _card_clicked(self, person_id: int):
        self._selected_id = person_id
        for card in self._cards:
            card.set_selected(card._id == person_id)
        self.person_selected.emit(person_id)

    def _load_all(self):
        from database.db_manager import get_all_persons
        records = get_all_persons()
        self.show_results(records, "ALL RECORDS")
