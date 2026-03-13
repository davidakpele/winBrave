"""
ui/main_window.py
Main application window. Assembles all panels and wires up signals/slots.
"""
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QPushButton, QFrame, QSplitter, QStackedWidget, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction

from .styles import *
from .widgets import PulsingDot
from .search_panel import SearchPanel
from .results_panel import ResultsPanel
from .detail_panel import DetailPanel
from .persons_table import PersonsTablePanel


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FaceSearch Pro  ·  Research Edition")
        self.setMinimumSize(1200, 750)
        self.resize(1440, 860)

        from database.db_manager import initialize_db
        initialize_db()

        self.setStyleSheet(MAIN_STYLE)
        self._build_ui()
        self._build_menu()
        self._connect_signals()
        self._start_clock()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_title_bar())

        self.stack = QStackedWidget()
        self.stack.setStyleSheet("background: transparent;")

        # Page 0 — face search
        search_page = QWidget()
        sp_layout = QVBoxLayout(search_page)
        sp_layout.setContentsMargins(0, 0, 0, 0)
        sp_layout.setSpacing(0)

        body = QSplitter(Qt.Orientation.Horizontal)
        body.setHandleWidth(2)
        body.setStyleSheet(f"QSplitter::handle {{ background: {BORDER}; }}")

        self.search_panel  = SearchPanel()
        self.results_panel = ResultsPanel()
        self.detail_panel  = DetailPanel()

        body.addWidget(self.search_panel)
        body.addWidget(self.results_panel)
        body.addWidget(self.detail_panel)
        body.setSizes([300, 440, 360])
        body.setCollapsible(0, False)
        body.setCollapsible(1, False)
        body.setCollapsible(2, False)

        sp_layout.addWidget(body)
        self.stack.addWidget(search_page)

        # Page 1 — records table
        self.persons_table = PersonsTablePanel()
        self.stack.addWidget(self.persons_table)

        root.addWidget(self.stack, 1)
        root.addWidget(self._build_status_bar())

    def _build_title_bar(self) -> QWidget:
        bar = QFrame()
        bar.setFixedHeight(44)
        bar.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {BG_DARKEST}, stop:0.5 #0e1520, stop:1 {BG_DARKEST});
                border-bottom: 2px solid {ACCENT_BLUE};
                border-top: none; border-left: none; border-right: none;
                border-radius: 0;
            }}
        """)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(0)

        logo = QLabel("⬡  FACESEARCH PRO")
        logo.setStyleSheet(f"color: {ACCENT_BLUE}; font-size: 14px; font-weight: bold; letter-spacing: 4px; background: transparent; border: none;")
        subtitle = QLabel("  RESEARCH EDITION  ·  LOCAL DATABASE")
        subtitle.setStyleSheet(f"color: {TEXT_DIM}; font-size: 10px; letter-spacing: 2px; background: transparent; border: none;")

        layout.addWidget(logo)
        layout.addWidget(subtitle)
        layout.addSpacing(32)

        self._nav_active = f"""
            QPushButton {{
                background: transparent;
                border: none;
                border-bottom: 2px solid {ACCENT_BLUE};
                color: {ACCENT_BLUE};
                font-size: 11px;
                letter-spacing: 1px;
                padding: 0 18px;
                font-weight: bold;
                font-family: Consolas;
            }}
        """
        self._nav_inactive = f"""
            QPushButton {{
                background: transparent;
                border: none;
                border-bottom: 2px solid transparent;
                color: {TEXT_SECONDARY};
                font-size: 11px;
                letter-spacing: 1px;
                padding: 0 18px;
                font-family: Consolas;
            }}
            QPushButton:hover {{
                color: {TEXT_PRIMARY};
                border-bottom: 2px solid {BORDER_LIGHT};
            }}
        """

        self.nav_search  = QPushButton("◼  FACE SEARCH")
        self.nav_records = QPushButton("☰  RECORDS TABLE")
        self.nav_search.setFixedHeight(44)
        self.nav_records.setFixedHeight(44)
        self.nav_search.setStyleSheet(self._nav_active)
        self.nav_records.setStyleSheet(self._nav_inactive)
        self.nav_search.clicked.connect(lambda: self._switch_page(0))
        self.nav_records.clicked.connect(lambda: self._switch_page(1))

        layout.addWidget(self.nav_search)
        layout.addWidget(self.nav_records)
        layout.addStretch()

        for text, color in [("SYSTEM: SECURE", ACCENT_GREEN),
                             ("NETWORK: LOCAL", ACCENT_AMBER),
                             ("DB: ONLINE",     ACCENT_GREEN)]:
            dot = PulsingDot(color)
            lbl = QLabel(text)
            lbl.setStyleSheet(f"color: {color}; font-size: 10px; letter-spacing: 1px; background: transparent; border: none;")
            layout.addWidget(dot)
            layout.addWidget(lbl)
            layout.addSpacing(14)

        add_btn = QPushButton("+ NEW RECORD")
        add_btn.setObjectName("btn_primary")
        add_btn.setFixedHeight(28)
        add_btn.clicked.connect(self._new_record)
        layout.addWidget(add_btn)

        return bar

    def _build_status_bar(self) -> QWidget:
        bar = QFrame()
        bar.setFixedHeight(26)
        bar.setStyleSheet(f"""
            QFrame {{
                background-color: {BG_DARKEST};
                border-top: 1px solid {BORDER};
                border-bottom: none; border-left: none; border-right: none;
                border-radius: 0;
            }}
        """)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(16)

        for tab_name in ["◼ RECORDS SEARCH", "+ ADD RECORD", "▪ ACTIVITY LOG"]:
            btn = QPushButton(tab_name)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    border: none;
                    border-right: 1px solid {BORDER};
                    color: {TEXT_SECONDARY};
                    font-size: 10px;
                    letter-spacing: 1px;
                    padding: 0 12px;
                }}
                QPushButton:hover {{ color: {ACCENT_BLUE}; }}
            """)
            if tab_name == "+ ADD RECORD":
                btn.clicked.connect(self._new_record)
            layout.addWidget(btn)

        layout.addStretch()

        self.status_lbl = QLabel("Ready")
        self.status_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 10px; background: transparent; border: none;")
        layout.addWidget(self.status_lbl)
        layout.addSpacing(16)

        self.clock_lbl = QLabel("")
        self.clock_lbl.setStyleSheet(f"color: {TEXT_DIM}; font-size: 10px; font-family: Consolas; background: transparent; border: none;")
        layout.addWidget(self.clock_lbl)

        return bar

    def _build_menu(self):
        mb = self.menuBar()
        mb.setStyleSheet(f"""
            QMenuBar {{
                background-color: {BG_DARKEST};
                color: {TEXT_SECONDARY};
                border-bottom: 1px solid {BORDER};
                font-size: 11px;
            }}
            QMenuBar::item:selected {{ background: {ACCENT_BLUE}; color: {BG_DARKEST}; }}
            QMenu {{
                background-color: {BG_CARD};
                color: {TEXT_PRIMARY};
                border: 1px solid {BORDER_LIGHT};
            }}
            QMenu::item:selected {{ background: {ACCENT_BLUE}; color: {BG_DARKEST}; }}
        """)

        file_menu = mb.addMenu("File")

        act_new = QAction("New Record", self)
        act_new.setShortcut("Ctrl+N")
        act_new.triggered.connect(self._new_record)

        act_records = QAction("View Records Table", self)
        act_records.setShortcut("Ctrl+R")
        act_records.triggered.connect(lambda: self._switch_page(1))

        act_reload = QAction("Reload Database", self)
        act_reload.triggered.connect(self._reload_db)

        act_exit = QAction("Exit", self)
        act_exit.setShortcut("Ctrl+Q")
        act_exit.triggered.connect(self.close)

        file_menu.addAction(act_new)
        file_menu.addAction(act_records)
        file_menu.addAction(act_reload)
        file_menu.addSeparator()
        file_menu.addAction(act_exit)

        help_menu = mb.addMenu("Help")
        act_about = QAction("About", self)
        act_about.triggered.connect(self._show_about)
        help_menu.addAction(act_about)

    def _connect_signals(self):
        self.search_panel.results_ready.connect(self._on_face_results)
        self.search_panel.text_search.connect(self._on_text_search)
        self.search_panel.search_error.connect(self._on_search_error)
        self.search_panel.status_message.connect(self._set_status)

        self.results_panel.person_selected.connect(self._on_person_selected)

        self.detail_panel.open_edit.connect(self._edit_record)
        self.detail_panel.deleted.connect(self._on_deleted)

        self.persons_table.open_edit.connect(self._edit_record)
        self.persons_table.open_detail.connect(self._on_person_selected)

    def _start_clock(self):
        from datetime import datetime
        def tick():
            self.clock_lbl.setText(datetime.now().strftime("%Y-%m-%d  %H:%M:%S"))
        tick()
        self._clock_timer = QTimer()
        self._clock_timer.timeout.connect(tick)
        self._clock_timer.start(1000)

    def _switch_page(self, index: int):
        self.stack.setCurrentIndex(index)
        if index == 0:
            self.nav_search.setStyleSheet(self._nav_active)
            self.nav_records.setStyleSheet(self._nav_inactive)
        else:
            self.nav_search.setStyleSheet(self._nav_inactive)
            self.nav_records.setStyleSheet(self._nav_active)
            self.persons_table.refresh()

    def _on_face_results(self, results: list):
        self.results_panel.show_results(results, "FACE MATCH")
        self._set_status(f"Face search complete — {len(results)} match(es)")

    def _on_text_search(self, query: str):
        from database.db_manager import search_persons
        results = search_persons(query)
        self.results_panel.show_results(results, "TEXT SEARCH")
        self._set_status(f"Text search '{query}' — {len(results)} result(s)")

    def _on_search_error(self, msg: str):
        QMessageBox.warning(self, "Search Error", msg)
        self._set_status("Search error")

    def _on_person_selected(self, person_id: int):
        self._switch_page(0)
        self.detail_panel.show_person(person_id)

    def _new_record(self):
        from .person_dialog import PersonDialog
        dlg = PersonDialog(self)
        if dlg.exec():
            self._set_status("New record saved.")
            self._reload_db()

    def _edit_record(self, person_id: int):
        if person_id is None:
            return
        from .person_dialog import PersonDialog
        dlg = PersonDialog(self, person_id)
        if dlg.exec():
            self._set_status("Record updated.")
            self.detail_panel.show_person(person_id)
            if self.stack.currentIndex() == 1:
                self.persons_table.refresh()

    def _on_deleted(self, person_id: int):
        self.results_panel.show_empty()
        self._set_status("Record deleted.")

    def _reload_db(self):
        from database.db_manager import get_all_persons
        records = get_all_persons()
        self.results_panel.show_results(records, "ALL RECORDS")
        self._set_status(f"Database loaded — {len(records)} records")

    def _set_status(self, msg: str):
        self.status_lbl.setText(msg)

    def _show_about(self):
        QMessageBox.about(self, "FaceSearch Pro",
            "<b>FaceSearch Pro — Research Edition</b><br><br>"
            "A desktop facial recognition search tool for security research and learning.<br><br>"
            "<b>Tech stack:</b><br>"
            "• PyQt6 — GUI framework<br>"
            "• OpenCV DNN — face detection & recognition<br>"
            "• SQLite — local database<br><br>"
            "<i>For research and educational use only.</i>"
        )