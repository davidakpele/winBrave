"""
ui/persons_table.py
Full persons list with pagination, search, edit and delete actions.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QFrame, QAbstractItemView, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor

from .styles import *

PAGE_SIZE = 50


class PersonsTablePanel(QWidget):
    open_detail = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._all_records  = []
        self._filtered     = []
        self._page         = 0
        self._page_records = []
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        self.setStyleSheet(f"background: {BG_DARK}; border: none;")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Top bar
        top = QFrame()
        top.setFixedHeight(50)
        top.setStyleSheet(f"""
            QFrame {{
                background: {BG_PANEL};
                border-bottom: 1px solid {BORDER};
                border-top: none; border-left: none; border-right: none;
            }}
        """)
        tl = QHBoxLayout(top)
        tl.setContentsMargins(14, 0, 14, 0)
        tl.setSpacing(10)

        bar = QFrame()
        bar.setFixedSize(3, 18)
        bar.setStyleSheet(f"background: {ACCENT_BLUE}; border: none;")

        title = QLabel("DATABASE RECORDS")
        title.setStyleSheet(f"color: {ACCENT_BLUE}; font-size: 11px; font-weight: bold; letter-spacing: 2px; background: transparent; border: none;")

        self.count_lbl = QLabel("")
        self.count_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 10px; background: transparent; border: none;")

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search name, ID, status, nationality...")
        self.search_box.setFixedWidth(300)
        self.search_box.textChanged.connect(self._apply_filter)

        refresh_btn = QPushButton("⟳  REFRESH")
        refresh_btn.setFixedHeight(28)
        refresh_btn.clicked.connect(self.refresh)

        add_btn = QPushButton("+ NEW RECORD")
        add_btn.setObjectName("btn_primary")
        add_btn.setFixedHeight(28)
        add_btn.clicked.connect(self._add_record)

        tl.addWidget(bar)
        tl.addWidget(title)
        tl.addWidget(self.count_lbl)
        tl.addStretch()
        tl.addWidget(self.search_box)
        tl.addWidget(refresh_btn)
        tl.addWidget(add_btn)
        root.addWidget(top)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "NAME", "ID NUMBER", "AGE", "GENDER", "NATIONALITY", "STATUS", "LAST SEEN", "ACTIONS"
        ])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(1, 130)
        self.table.setColumnWidth(2, 50)
        self.table.setColumnWidth(3, 80)
        self.table.setColumnWidth(5, 170)
        self.table.setColumnWidth(6, 100)
        self.table.setColumnWidth(7, 150)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background: {BG_DARKEST};
                alternate-background-color: {BG_PANEL};
                border: none;
                gridline-color: transparent;
                color: {TEXT_PRIMARY};
                font-size: 12px;
                selection-background-color: {ACCENT_BLUE}33;
                outline: none;
            }}
            QTableWidget::item {{
                padding: 4px 8px;
                border-bottom: 1px solid {BORDER};
            }}
            QTableWidget::item:selected {{
                background: {ACCENT_BLUE}33;
                color: {TEXT_WHITE};
            }}
            QHeaderView::section {{
                background: {BG_PANEL};
                color: {ACCENT_BLUE};
                border: none;
                border-bottom: 2px solid {ACCENT_BLUE};
                padding: 6px 8px;
                font-size: 10px;
                letter-spacing: 1px;
                font-weight: bold;
            }}
        """)
        self.table.doubleClicked.connect(self._on_double_click)
        root.addWidget(self.table, 1)

        # Pagination bar
        pag = QFrame()
        pag.setFixedHeight(40)
        pag.setStyleSheet(f"""
            QFrame {{
                background: {BG_PANEL};
                border-top: 1px solid {BORDER};
                border-bottom: none; border-left: none; border-right: none;
            }}
        """)
        pl = QHBoxLayout(pag)
        pl.setContentsMargins(14, 0, 14, 0)
        pl.setSpacing(8)

        self.prev_btn = QPushButton("◀  PREV")
        self.prev_btn.setFixedHeight(26)
        self.prev_btn.clicked.connect(self._prev_page)

        self.page_lbl = QLabel("Page 1 of 1")
        self.page_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 10px; background: transparent; border: none;")

        self.next_btn = QPushButton("NEXT  ▶")
        self.next_btn.setFixedHeight(26)
        self.next_btn.clicked.connect(self._next_page)

        self.page_info = QLabel("")
        self.page_info.setStyleSheet(f"color: {TEXT_DIM}; font-size: 10px; background: transparent; border: none;")

        pl.addWidget(self.prev_btn)
        pl.addWidget(self.page_lbl)
        pl.addWidget(self.next_btn)
        pl.addStretch()
        pl.addWidget(self.page_info)
        root.addWidget(pag)

    # ── Data ──────────────────────────────────────────────────────────────────

    def refresh(self):
        from database.db_manager import get_all_persons
        self._all_records = get_all_persons()
        self._apply_filter()

    def _apply_filter(self):
        q = self.search_box.text().strip().lower()
        if q:
            self._filtered = [
                r for r in self._all_records
                if q in (r.get('full_name') or '').lower()
                or q in (r.get('id_number') or '').lower()
                or q in (r.get('nationality') or '').lower()
                or q in (r.get('status') or '').lower()
                or q in (r.get('address') or '').lower()
                or q in (r.get('notes') or '').lower()
            ]
        else:
            self._filtered = list(self._all_records)
        self._page = 0
        self._render_page()

    def _render_page(self):
        total   = len(self._filtered)
        start   = self._page * PAGE_SIZE
        end     = min(start + PAGE_SIZE, total)
        records = self._filtered[start:end]
        self._page_records = records

        self.table.setRowCount(0)
        self.table.setRowCount(len(records))

        for row, rec in enumerate(records):
            self.table.setRowHeight(row, 38)

            def cell(text, align=Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft):
                item = QTableWidgetItem(str(text) if text else "—")
                item.setTextAlignment(align)
                return item

            self.table.setItem(row, 0, cell(rec.get('full_name', '')))
            self.table.setItem(row, 1, cell(rec.get('id_number', '')))
            self.table.setItem(row, 2, cell(rec.get('age', ''), Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter))
            self.table.setItem(row, 3, cell(rec.get('gender', '')))
            self.table.setItem(row, 4, cell(rec.get('nationality', '')))

            status = rec.get('status', 'No Record')
            status_item = QTableWidgetItem(status)
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
            fg, bg = STATUS_COLORS.get(status, (TEXT_SECONDARY, BG_CARD))
            status_item.setForeground(QColor(fg))
            status_item.setBackground(QColor(bg))
            self.table.setItem(row, 5, status_item)

            self.table.setItem(row, 6, cell(rec.get('last_seen', ''), Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter))

            pid = rec['id']
            btn_widget = QWidget()
            btn_widget.setStyleSheet("background: transparent;")
            bl = QHBoxLayout(btn_widget)
            bl.setContentsMargins(6, 3, 6, 3)
            bl.setSpacing(6)

            edit_btn = QPushButton("EDIT")
            edit_btn.setFixedHeight(24)
            edit_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    border: 1px solid {ACCENT_BLUE};
                    color: {ACCENT_BLUE};
                    font-size: 10px;
                    font-family: Consolas;
                    padding: 0 10px;
                    border-radius: 2px;
                    letter-spacing: 1px;
                }}
                QPushButton:hover {{ background: {ACCENT_BLUE}; color: {BG_DARKEST}; }}
            """)
            edit_btn.clicked.connect(lambda _, p=pid: self._edit_record(p))

            del_btn = QPushButton("DEL")
            del_btn.setFixedHeight(24)
            del_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    border: 1px solid {ACCENT_RED};
                    color: {ACCENT_RED};
                    font-size: 10px;
                    font-family: Consolas;
                    padding: 0 10px;
                    border-radius: 2px;
                    letter-spacing: 1px;
                }}
                QPushButton:hover {{ background: {ACCENT_RED}; color: white; }}
            """)
            del_btn.clicked.connect(lambda _, p=pid: self._delete_record(p))

            bl.addWidget(edit_btn)
            bl.addWidget(del_btn)
            self.table.setCellWidget(row, 7, btn_widget)

        total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        self.page_lbl.setText(f"Page {self._page + 1} of {total_pages}")
        self.page_info.setText(f"Showing {start + 1}–{end} of {total} records")
        self.count_lbl.setText(f"  {total} RECORDS")
        self.prev_btn.setEnabled(self._page > 0)
        self.next_btn.setEnabled(end < total)

    # ── Pagination ────────────────────────────────────────────────────────────

    def _prev_page(self):
        if self._page > 0:
            self._page -= 1
            self._render_page()

    def _next_page(self):
        if (self._page + 1) * PAGE_SIZE < len(self._filtered):
            self._page += 1
            self._render_page()

    # ── Actions ───────────────────────────────────────────────────────────────

    def _on_double_click(self, index):
        row = index.row()
        if row < len(self._page_records):
            self.open_detail.emit(self._page_records[row]['id'])

    def _add_record(self):
        from .person_dialog import PersonDialog
        dlg = PersonDialog(self)
        if dlg.exec():
            self.refresh()

    def _edit_record(self, person_id: int):
        from .person_dialog import PersonDialog
        dlg = PersonDialog(self, person_id)
        dlg.exec()
        self.refresh()  # always refresh whether saved or cancelled

    def _delete_record(self, person_id: int):
        reply = QMessageBox.question(
            self, "Confirm Delete", "Permanently delete this record?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            from database.db_manager import delete_person
            delete_person(person_id)
            self.refresh()