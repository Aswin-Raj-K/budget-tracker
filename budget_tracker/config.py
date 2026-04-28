from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "BudgetTracker"
APP_DISPLAY_NAME = "Budget Tracker"
ORG_NAME = "Snello"


def data_dir() -> Path:
    """Per-user data directory. Created on first access."""
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / ".local" / "share")
    path = Path(base) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def db_path() -> Path:
    return data_dir() / "budget.sqlite3"


PACKAGE_ROOT = Path(__file__).resolve().parent
MIGRATIONS_DIR = PACKAGE_ROOT / "core" / "migrations"
THEME_DIR = PACKAGE_ROOT / "ui" / "theme"
ICONS_DIR = PACKAGE_ROOT / "ui" / "icons"
