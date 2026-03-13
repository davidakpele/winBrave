"""
FaceSearch Pro - Facial Recognition Research Tool
Entry point
"""
import sys
import os
import traceback

def exception_hook(exctype, value, tb):
    print("CRASH:", exctype, value)
    traceback.print_tb(tb)
    sys.__excepthook__(exctype, value, tb)

sys.excepthook = exception_hook

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("FaceSearch Pro")
    app.setApplicationVersion("1.0.0")

    app.setStyleSheet("""
        QToolTip {
            background-color: #1a1f2e;
            color: #c8d6e5;
            border: 1px solid #2a9fd6;
            padding: 4px 8px;
            font-family: 'Consolas';
            font-size: 11px;
        }
        QScrollBar:vertical {
            background: #0d1117;
            width: 8px;
            border: none;
        }
        QScrollBar::handle:vertical {
            background: #2a9fd6;
            border-radius: 4px;
            min-height: 20px;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0px;
        }
        QScrollBar:horizontal {
            background: #0d1117;
            height: 8px;
            border: none;
        }
        QScrollBar::handle:horizontal {
            background: #2a9fd6;
            border-radius: 4px;
        }
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
            width: 0px;
        }
    """)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()