"""Move the SQLite database to a user-chosen location.

The DB pointer lives in ``data_dir()/config.json`` (see ``config.py``).
``db_path()`` reads that file at every call, so the rest of the app
just needs to be (re)connected after a move.

Because the running app holds an open SQLite connection to the file,
we can't safely delete the source on Windows during the move. We copy
to the target, update the pointer, and remember the old path under
``legacy_db_path``. On next startup ``cleanup_legacy_db_file()`` runs
and removes the orphaned source file.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from budget_tracker.config import (
    KEY_DB_PATH,
    KEY_LEGACY_DB_PATH,
    db_path,
    default_db_path,
    load_app_config,
    save_app_config,
)

_DB_FILENAME = "budget.sqlite3"


def is_default_location() -> bool:
    return db_path().resolve() == default_db_path().resolve()


def move_database(target_dir: Path | str) -> Path:
    """Copy the current DB into ``target_dir`` and update the pointer.

    The caller is expected to relaunch the app after a successful move
    so the new connection opens the file at the new location. The old
    file is cleaned up at startup, not here, because the live
    connection still holds it locked on Windows.
    """
    target_dir = Path(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / _DB_FILENAME

    current = db_path()
    if not current.exists():
        raise FileNotFoundError(f"Current database file not found at {current}.")
    # Same-location must be checked first; otherwise the existing source
    # file IS the would-be target and we'd raise FileExistsError instead
    # of the more useful "you're moving it to where it already is" error.
    if current.resolve() == target.resolve():
        raise ValueError("Source and destination are the same location.")
    if target.exists():
        raise FileExistsError(
            f"A budget database already exists at {target}. "
            "Move or remove it first."
        )

    shutil.copy2(current, target)

    cfg = load_app_config()
    cfg[KEY_DB_PATH] = str(target)
    cfg[KEY_LEGACY_DB_PATH] = str(current)
    save_app_config(cfg)
    return target


def revert_to_default() -> Path:
    """Forget any custom DB location. Doesn't move the file — the next
    launch will use whatever sits at the default path (or create a new
    empty DB there)."""
    cfg = load_app_config()
    cfg.pop(KEY_DB_PATH, None)
    save_app_config(cfg)
    return default_db_path()


def cleanup_legacy_db_file() -> None:
    """Remove the file remembered as ``legacy_db_path`` after a move.

    Safe to call on every startup — it's a no-op if no legacy path is
    recorded or the file is already gone. If the file can't be removed
    (still locked, perms), the flag is left in place so we retry on the
    next startup.
    """
    cfg = load_app_config()
    legacy = cfg.get(KEY_LEGACY_DB_PATH)
    if not legacy:
        return
    legacy_path = Path(legacy)
    if legacy_path.exists():
        try:
            legacy_path.unlink()
        except OSError:
            return  # still locked / no perms — try again next launch
    cfg.pop(KEY_LEGACY_DB_PATH, None)
    save_app_config(cfg)
