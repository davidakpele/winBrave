"""
ui/results_panel.py
Centre panel: shows match cards from face search or text search results.
Displays match rating label, confidence %, and diff % on each card.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
    QFrame, QPushButton
)
from PyQt6.QtCore import Qt, pyqtSignal

from .styles import *
from .widgets import MatchCard


# Map color_hint strings from face_engine to actual hex colours
_RATING_COLORS = {
    'green':  '#00e676',
    'yellow': '#ffd740',
    'orange': '#ff9100',
    'red':    '#ff1744',
}


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

        # ── Header bar ────────────────────────────────────────────────────────
        hdr = QWidget()
        hdr.setFixedHeight(32)
        hdr.setStyleSheet(f"background-color: {BG_PANEL}; border-bottom: 1px solid {BORDER};")
        hdr_row = QHBoxLayout(hdr)
        hdr_row.setContentsMargins(10, 0, 10, 0)

        bar = QFrame()
        bar.setFixedSize(3, 16)
        bar.setStyleSheet(f"background: {ACCENT_CYAN}; border: none;")

        title = QLabel("DATABASE RESULTS")
        title.setStyleSheet(
            f"color: {ACCENT_CYAN}; font-size: 10px; font-weight: bold; "
            f"letter-spacing: 2px; background: transparent; border: none;"
        )

        self.count_lbl = QLabel("")
        self.count_lbl.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: 10px; background: transparent; border: none;"
        )

        hdr_row.addWidget(bar)
        hdr_row.addWidget(title)
        hdr_row.addStretch()
        hdr_row.addWidget(self.count_lbl)
        self._root.addWidget(hdr)

        # ── Sub-header ────────────────────────────────────────────────────────
        self.sub_hdr = QLabel("— AWAITING SEARCH —")
        self.sub_hdr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sub_hdr.setFixedHeight(24)
        self._set_subhdr_idle()
        self._root.addWidget(self.sub_hdr)

        # ── Rating banner (hidden until a face match result comes in) ─────────
        self.rating_banner = QWidget()
        self.rating_banner.setFixedHeight(36)
        self.rating_banner.setStyleSheet("background: transparent;")
        rb_lay = QHBoxLayout(self.rating_banner)
        rb_lay.setContentsMargins(10, 0, 10, 0)
        rb_lay.setSpacing(12)

        self.rating_lbl = QLabel("")          # e.g. "CLOSE MATCH"
        self.rating_lbl.setStyleSheet(
            "font-size: 12px; font-weight: bold; letter-spacing: 2px; "
            "background: transparent; border: none;"
        )

        self.match_pct_lbl = QLabel("")       # e.g. "Match  82.4%"
        self.match_pct_lbl.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: 11px; background: transparent; border: none;"
        )

        self.diff_pct_lbl = QLabel("")        # e.g. "Diff  17.6%"
        self.diff_pct_lbl.setStyleSheet(
            f"color: {TEXT_DIM}; font-size: 11px; background: transparent; border: none;"
        )

        rb_lay.addWidget(self.rating_lbl)
        rb_lay.addWidget(self.match_pct_lbl)
        rb_lay.addWidget(self.diff_pct_lbl)
        rb_lay.addStretch()

        self.rating_banner.hide()
        self._root.addWidget(self.rating_banner)

        # ── Scroll area ───────────────────────────────────────────────────────
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self._root.addWidget(self.scroll, 1)

        # ── Show all button ───────────────────────────────────────────────────
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

    # ── Internal helpers ──────────────────────────────────────────────────────

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

    def _update_rating_banner(self, rec: dict):
        """
        Populate and show the rating banner from a face-match result record.
        The record is expected to have: match_label, confidence, diff_percent, color_hint.
        """
        label       = rec.get('match_label', '')
        confidence  = rec.get('confidence', 0.0)
        diff        = rec.get('diff_percent', 0.0)
        color_hint  = rec.get('color_hint', 'green')
        color       = _RATING_COLORS.get(color_hint, '#00e676')

        if not label:
            self.rating_banner.hide()
            return

        self.rating_lbl.setText(label)
        self.rating_lbl.setStyleSheet(
            f"color: {color}; font-size: 12px; font-weight: bold; "
            f"letter-spacing: 2px; background: transparent; border: none;"
        )
        self.match_pct_lbl.setText(f"Match  {confidence:.1f}%")
        self.match_pct_lbl.setStyleSheet(
            f"color: {color}; font-size: 11px; background: transparent; border: none;"
        )
        self.diff_pct_lbl.setText(f"Diff  {diff:.1f}%")

        # Set banner background as a faint tint of the rating colour
        self.rating_banner.setStyleSheet(
            f"background: transparent; border-bottom: 1px solid {BORDER};"
        )
        self.rating_banner.show()

    # ── Public API ────────────────────────────────────────────────────────────

    def show_results(self, records: list, search_type: str = "FACE MATCH"):
        """
        Render result cards. For face-match results the first record should
        carry match_label / confidence / diff_percent / color_hint fields.
        """
        self._reset_container()
        self._selected_id = None
        self._set_subhdr_active(f"— {search_type.upper()} RESULTS —")

        # Hide rating banner by default; show only for face-match results
        self.rating_banner.hide()

        if not records:
            self.count_lbl.setText("NO MATCHES")
            self._show_not_found()
            return

        self.count_lbl.setText(
            f"{len(records)} MATCH{'ES' if len(records) != 1 else ''} FOUND"
        )

        for rec in records:
            card = MatchCard(rec)
            card.clicked.connect(self._card_clicked)
            self._cards.append(card)
            self._layout.insertWidget(self._layout.count() - 1, card)

        # Show rating banner if the top result has face-match metadata
        if records and records[0].get('match_label'):
            self._update_rating_banner(records[0])

        if records:
            self._card_clicked(records[0].get('id', -1))

    def show_empty(self):
        self._reset_container()
        self.count_lbl.setText("")
        self.rating_banner.hide()
        self._set_subhdr_idle()

    def _show_not_found(self):
        w = QWidget()
        w.setStyleSheet("background: transparent; border: none;")
        lay = QVBoxLayout(w)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.setSpacing(12)

        icon = QLabel("⊘")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet(
            f"color: {ACCENT_RED}; font-size: 40px; background: transparent; border: none;"
        )

        msg = QLabel("USER NOT FOUND ON THE SYSTEM")
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        msg.setStyleSheet(
            f"color: {ACCENT_RED}; font-size: 12px; font-weight: bold; "
            f"letter-spacing: 2px; background: transparent; border: none;"
        )

        hint = QLabel(
            "No matching records in the database.\n"
            "Try adjusting the tolerance slider\n"
            "or add this person as a new record."
        )
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet(
            f"color: {TEXT_DIM}; font-size: 11px; background: transparent; border: none;"
        )
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