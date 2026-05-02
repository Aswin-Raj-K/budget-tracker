from __future__ import annotations

import json
import os
from pathlib import Path

APP_NAME = "BudgetTracker"
APP_DISPLAY_NAME = "Budget Tracker"
ORG_NAME = "Snello"

_CONFIG_FILE = "config.json"
_DB_NAME = "budget.sqlite3"
KEY_DB_PATH = "db_path"
KEY_LEGACY_DB_PATH = "legacy_db_path"   # written during a move; cleaned up on next startup


def data_dir() -> Path:
    """Per-user data directory. Created on first access."""
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / ".local" / "share")
    path = Path(base) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def app_config_path() -> Path:
    """JSON pointer file. Lives in the per-user data dir; tracks the chosen
    database location and any post-move cleanup state."""
    return data_dir() / _CONFIG_FILE


def load_app_config() -> dict:
    p = app_config_path()
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_app_config(cfg: dict) -> None:
    p = app_config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def default_db_path() -> Path:
    return data_dir() / _DB_NAME


def db_path() -> Path:
    """Current database file path. Honours the user's chosen location if
    set; otherwise falls back to the default in the per-user data dir."""
    cfg = load_app_config()
    custom = cfg.get(KEY_DB_PATH)
    if custom:
        return Path(custom)
    return default_db_path()


PACKAGE_ROOT = Path(__file__).resolve().parent
MIGRATIONS_DIR = PACKAGE_ROOT / "core" / "migrations"
STYLES_DIR = PACKAGE_ROOT / "ui" / "styles"
THEMES_DIR = STYLES_DIR / "themes"
ICONS_DIR = PACKAGE_ROOT / "ui" / "icons"
