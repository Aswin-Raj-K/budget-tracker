from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from budget_tracker.config import APP_DISPLAY_NAME, ORG_NAME, db_path
from budget_tracker.core.db import init_db
from budget_tracker.services.settings_service import SettingsService
from budget_tracker.ui.theme import apply_theme


def _theme_preview(parent: QWidget) -> QWidget:
    """Temporary preview of common widgets to verify theming.
    Removed once Phase 6 (main shell) lands."""
    root = QFrame()
    root.setProperty("class", "card")
    layout = QVBoxLayout(root)
    layout.setContentsMargins(20, 20, 20, 20)
    layout.setSpacing(12)

    title = QLabel("Budget Tracker")
    title.setProperty("class", "h1")
    subtitle = QLabel("Theme preview — Phase 5 ready")
    subtitle.setProperty("class", "muted")

    row = QHBoxLayout()
    row.setSpacing(8)
    primary = QPushButton("Primary")
    primary.setProperty("class", "primary")
    secondary = QPushButton("Secondary")
    secondary.setProperty("class", "secondary")
    ghost = QPushButton("Ghost")
    ghost.setProperty("class", "ghost")
    danger = QPushButton("Danger")
    danger.setProperty("class", "danger")
    for b in (primary, secondary, ghost, danger):
        row.addWidget(b)
    row.addStretch(1)

    edit = QLineEdit()
    edit.setPlaceholderText("Search transactions…")

    bar = QProgressBar()
    bar.setRange(0, 100)
    bar.setValue(72)
    bar.setProperty("status", "warning")

    bar2 = QProgressBar()
    bar2.setRange(0, 100)
    bar2.setValue(42)

    chip = QLabel("Food")
    chip.setProperty("class", "chip")

    db_label = QLabel(f"DB: {db_path()}")
    db_label.setProperty("class", "subtle")

    layout.addWidget(title)
    layout.addWidget(subtitle)
    layout.addLayout(row)
    layout.addWidget(edit)
    layout.addWidget(bar)
    layout.addWidget(bar2)
    layout.addWidget(chip)
    layout.addStretch(1)
    layout.addWidget(db_label)

    return root


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_DISPLAY_NAME)
    app.setOrganizationName(ORG_NAME)

    conn = init_db()
    settings = SettingsService(conn)
    settings.apply_to_session()
    apply_theme(app, settings.get_theme())

    window = QMainWindow()
    window.setWindowTitle(APP_DISPLAY_NAME)
    window.resize(1200, 760)

    central = QWidget()
    outer = QVBoxLayout(central)
    outer.setContentsMargins(40, 40, 40, 40)
    outer.setAlignment(Qt.AlignmentFlag.AlignTop)
    outer.addWidget(_theme_preview(central))
    window.setCentralWidget(central)

    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
