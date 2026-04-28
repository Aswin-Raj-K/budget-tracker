from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QMainWindow, QVBoxLayout, QWidget

from budget_tracker.config import APP_DISPLAY_NAME, ORG_NAME, db_path
from budget_tracker.core.db import init_db


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_DISPLAY_NAME)
    app.setOrganizationName(ORG_NAME)

    init_db()

    window = QMainWindow()
    window.setWindowTitle(APP_DISPLAY_NAME)
    window.resize(1200, 760)

    central = QWidget()
    layout = QVBoxLayout(central)
    layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
    title = QLabel("Budget Tracker — scaffold ready")
    title.setAlignment(Qt.AlignmentFlag.AlignCenter)
    info = QLabel(f"Database: {db_path()}")
    info.setAlignment(Qt.AlignmentFlag.AlignCenter)
    info.setStyleSheet("color: #64748B;")
    layout.addWidget(title)
    layout.addWidget(info)
    window.setCentralWidget(central)

    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
