"""
ui/styles.py
Centralised colour palette and stylesheet strings for the dark tactical theme.
"""

# ── Palette ────────────────────────────────────────────────────────────────────
BG_DARKEST   = "#080c12"
BG_DARK      = "#0d1117"
BG_PANEL     = "#111825"
BG_CARD      = "#161e2d"
BG_HOVER     = "#1a2438"
BORDER       = "#1e2d42"
BORDER_LIGHT = "#263448"

ACCENT_BLUE  = "#2a9fd6"
ACCENT_CYAN  = "#00d4ff"
ACCENT_RED   = "#e63946"
ACCENT_AMBER = "#f4a261"
ACCENT_GREEN = "#2ec4b6"

TEXT_PRIMARY   = "#c8d6e5"
TEXT_SECONDARY = "#6b7f96"
TEXT_DIM       = "#3d5068"
TEXT_WHITE     = "#eaf0f8"

# ── Status colours ─────────────────────────────────────────────────────────────
STATUS_COLORS = {
    "Felony Warrant":       ("#e63946", "#330a0d"),
    "Arrest Record":        ("#f4a261", "#2e1a08"),
    "Under Investigation":  ("#f4a261", "#2e1a08"),
    "Interpol Notice":      ("#e63946", "#330a0d"),
    "Person of Interest":   ("#e6b800", "#2e2600"),
    "Witness":              ("#2a9fd6", "#0a1e2e"),
    "No Record":            ("#2ec4b6", "#0a2020"),
}

DEFAULT_STATUS_COLOR = (TEXT_SECONDARY, BG_CARD)


def status_colors(status: str):
    return STATUS_COLORS.get(status, DEFAULT_STATUS_COLOR)


# ── Main stylesheet ────────────────────────────────────────────────────────────
MAIN_STYLE = f"""
/* === Base === */
QMainWindow, QWidget {{
    background-color: {BG_DARK};
    color: {TEXT_PRIMARY};
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 12px;
}}

/* === Labels === */
QLabel {{
    color: {TEXT_PRIMARY};
    background: transparent;
}}

/* === Frames / Panels === */
QFrame {{
    background-color: {BG_PANEL};
    border: 1px solid {BORDER};
    border-radius: 4px;
}}
QFrame[flat=true] {{
    background: transparent;
    border: none;
}}

/* === Buttons === */
QPushButton {{
    background-color: {BG_CARD};
    color: {ACCENT_BLUE};
    border: 1px solid {ACCENT_BLUE};
    border-radius: 3px;
    padding: 6px 16px;
    font-family: 'Consolas';
    font-size: 11px;
    letter-spacing: 1px;
    text-transform: uppercase;
}}
QPushButton:hover {{
    background-color: {ACCENT_BLUE};
    color: {BG_DARKEST};
}}
QPushButton:pressed {{
    background-color: {ACCENT_CYAN};
    color: {BG_DARKEST};
}}
QPushButton:disabled {{
    color: {TEXT_DIM};
    border-color: {TEXT_DIM};
}}
QPushButton#btn_danger {{
    color: {ACCENT_RED};
    border-color: {ACCENT_RED};
}}
QPushButton#btn_danger:hover {{
    background-color: {ACCENT_RED};
    color: white;
}}
QPushButton#btn_primary {{
    background-color: {ACCENT_BLUE};
    color: {BG_DARKEST};
    font-weight: bold;
}}
QPushButton#btn_primary:hover {{
    background-color: {ACCENT_CYAN};
}}

/* === Line Edits === */
QLineEdit {{
    background-color: {BG_DARKEST};
    color: {TEXT_WHITE};
    border: 1px solid {BORDER_LIGHT};
    border-radius: 3px;
    padding: 5px 10px;
    selection-background-color: {ACCENT_BLUE};
    font-family: 'Consolas';
    font-size: 12px;
}}
QLineEdit:focus {{
    border-color: {ACCENT_BLUE};
}}

/* === ComboBox === */
QComboBox {{
    background-color: {BG_DARKEST};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_LIGHT};
    border-radius: 3px;
    padding: 4px 8px;
    font-family: 'Consolas';
    font-size: 11px;
    min-width: 120px;
}}
QComboBox::drop-down {{
    border: none;
    width: 20px;
}}
QComboBox QAbstractItemView {{
    background-color: {BG_CARD};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_LIGHT};
    selection-background-color: {ACCENT_BLUE};
    selection-color: {BG_DARKEST};
}}

/* === Spin Box === */
QSpinBox {{
    background-color: {BG_DARKEST};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_LIGHT};
    border-radius: 3px;
    padding: 4px 8px;
    font-family: 'Consolas';
}}
QSpinBox:focus {{ border-color: {ACCENT_BLUE}; }}

/* === Text Edit === */
QTextEdit, QPlainTextEdit {{
    background-color: {BG_DARKEST};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_LIGHT};
    border-radius: 3px;
    padding: 6px;
    font-family: 'Consolas';
    font-size: 11px;
    selection-background-color: {ACCENT_BLUE};
}}

/* === Tab Widget === */
QTabWidget::pane {{
    background-color: {BG_PANEL};
    border: 1px solid {BORDER};
    border-top: none;
}}
QTabBar::tab {{
    background-color: {BG_DARKEST};
    color: {TEXT_SECONDARY};
    border: 1px solid {BORDER};
    border-bottom: none;
    padding: 6px 20px;
    font-family: 'Consolas';
    font-size: 11px;
    letter-spacing: 1px;
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    background-color: {BG_PANEL};
    color: {ACCENT_BLUE};
    border-bottom: 2px solid {ACCENT_BLUE};
}}
QTabBar::tab:hover:!selected {{
    background-color: {BG_CARD};
    color: {TEXT_PRIMARY};
}}

/* === List Widget === */
QListWidget {{
    background-color: {BG_DARKEST};
    border: 1px solid {BORDER};
    color: {TEXT_PRIMARY};
    outline: none;
}}
QListWidget::item {{
    padding: 4px 8px;
    border-bottom: 1px solid {BORDER};
}}
QListWidget::item:selected {{
    background-color: {ACCENT_BLUE};
    color: {BG_DARKEST};
}}
QListWidget::item:hover:!selected {{
    background-color: {BG_HOVER};
}}

/* === Table Widget === */
QTableWidget {{
    background-color: {BG_DARKEST};
    border: 1px solid {BORDER};
    gridline-color: {BORDER};
    color: {TEXT_PRIMARY};
    selection-background-color: {ACCENT_BLUE};
    selection-color: {BG_DARKEST};
    outline: none;
}}
QHeaderView::section {{
    background-color: {BG_PANEL};
    color: {ACCENT_BLUE};
    border: none;
    border-bottom: 1px solid {BORDER_LIGHT};
    border-right: 1px solid {BORDER};
    padding: 5px 8px;
    font-family: 'Consolas';
    font-size: 11px;
    letter-spacing: 1px;
    text-transform: uppercase;
}}
QTableWidget::item {{ padding: 4px 6px; border-bottom: 1px solid {BORDER}; }}

/* === Progress Bar === */
QProgressBar {{
    background-color: {BG_DARKEST};
    border: 1px solid {BORDER};
    border-radius: 2px;
    height: 6px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background-color: {ACCENT_BLUE};
    border-radius: 2px;
}}

/* === Splitter === */
QSplitter::handle {{
    background-color: {BORDER};
    width: 2px;
    height: 2px;
}}
QSplitter::handle:hover {{
    background-color: {ACCENT_BLUE};
}}

/* === Group Box === */
QGroupBox {{
    background-color: transparent;
    border: 1px solid {BORDER_LIGHT};
    border-radius: 4px;
    margin-top: 12px;
    padding-top: 8px;
    color: {TEXT_SECONDARY};
    font-size: 10px;
    letter-spacing: 2px;
    text-transform: uppercase;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
    left: 10px;
    color: {TEXT_SECONDARY};
}}

/* === Dialog === */
QDialog {{
    background-color: {BG_DARK};
    border: 1px solid {BORDER_LIGHT};
}}

/* === Message Box === */
QMessageBox {{
    background-color: {BG_PANEL};
    color: {TEXT_PRIMARY};
}}

/* === Slider === */
QSlider::groove:horizontal {{
    background: {BORDER};
    height: 4px;
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {ACCENT_BLUE};
    width: 14px;
    height: 14px;
    border-radius: 7px;
    margin: -5px 0;
}}
QSlider::sub-page:horizontal {{
    background: {ACCENT_BLUE};
    border-radius: 2px;
}}
"""
