from __future__ import annotations

import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QDialog

from budget_tracker.config import APP_DISPLAY_NAME, ICONS_DIR, ORG_NAME
from budget_tracker.core.db import init_db
from budget_tracker.services.db_location_service import cleanup_legacy_db_file
from budget_tracker.services.seeder import seed_default_categories_if_empty
from budget_tracker.services.settings_service import SettingsService
from budget_tracker.ui.dialogs.welcome_dialog import WelcomeDialog
from budget_tracker.ui.main_window import MainWindow
from budget_tracker.ui.styles import apply_theme


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_DISPLAY_NAME)
    app.setOrganizationName(ORG_NAME)
    app.setWindowIcon(QIcon(str(ICONS_DIR / "budget_tracker_icon.svg")))

    # If the user moved the DB last session, the previous file may still
    # be on disk (the move ran while the connection was open and locked
    # it on Windows). Clean it up before opening the new one.
    cleanup_legacy_db_file()

    conn = init_db()
    seed_default_categories_if_empty(conn)
    settings = SettingsService(conn)

    # Apply the theme as early as possible so the welcome dialog (and any
    # error message before that) is themed consistently.
    apply_theme(app, settings.get_theme())

    if not settings.has_currency():
        welcome = WelcomeDialog()
        chosen = welcome.currency_code()
        if welcome.exec() == QDialog.DialogCode.Accepted:
            chosen = welcome.currency_code()
        # In either branch, persist a currency so the dialog never reappears.
        settings.set_currency(chosen)

    settings.apply_to_session()

    window = MainWindow(conn, settings)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
