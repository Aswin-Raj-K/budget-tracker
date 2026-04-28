from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QMainWindow, QVBoxLayout, QWidget

from budget_tracker.config import APP_DISPLAY_NAME, ORG_NAME


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_DISPLAY_NAME)
    app.setOrganizationName(ORG_NAME)

    window = QMainWindow()
    window.setWindowTitle(APP_DISPLAY_NAME)
    window.resize(1200, 760)

    central = QWidget()
    layout = QVBoxLayout(central)
    layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
    placeholder = QLabel("Budget Tracker — scaffold ready")
    placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(placeholder)
    window.setCentralWidget(central)

    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
