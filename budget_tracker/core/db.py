from __future__ import annotations

import sqlite3
from pathlib import Path

from budget_tracker.config import MIGRATIONS_DIR, db_path

_SCHEMA_MIGRATIONS_DDL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    name       TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP)
)
"""


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    """Open a SQLite connection with foreign keys on and Row factory.

    Pass `:memory:` (or a Path/str) explicitly for tests; default is the
    user's data directory.
    """
    if path is None:
        target: Path | str = db_path()
    else:
        target = path
    conn = sqlite3.connect(str(target))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def run_migrations(
    conn: sqlite3.Connection,
    migrations_dir: Path = MIGRATIONS_DIR,
) -> list[str]:
    """Apply any pending *.sql migrations in lexical order. Idempotent.

    Returns the list of migration filenames newly applied this call.
    """
    conn.execute(_SCHEMA_MIGRATIONS_DDL)
    conn.commit()

    applied = {row["name"] for row in conn.execute("SELECT name FROM schema_migrations")}

    files = sorted(p for p in migrations_dir.glob("*.sql"))
    newly_applied: list[str] = []
    for f in files:
        if f.name in applied:
            continue
        sql = f.read_text(encoding="utf-8")
        conn.executescript(sql)
        conn.execute("INSERT INTO schema_migrations(name) VALUES (?)", (f.name,))
        conn.commit()
        newly_applied.append(f.name)
    return newly_applied


def init_db(path: Path | str | None = None) -> sqlite3.Connection:
    """Open a connection and ensure the schema is up to date."""
    conn = connect(path)
    run_migrations(conn)
    return conn
