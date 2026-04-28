from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from budget_tracker.config import APP_DISPLAY_NAME, ORG_NAME
from budget_tracker.core.db import init_db
from budget_tracker.services.settings_service import SettingsService
from budget_tracker.ui.main_window import MainWindow
from budget_tracker.ui.theme import apply_theme


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_DISPLAY_NAME)
    app.setOrganizationName(ORG_NAME)

    conn = init_db()
    settings = SettingsService(conn)
    settings.apply_to_session()
    apply_theme(app, settings.get_theme())

    window = MainWindow(conn, settings)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
