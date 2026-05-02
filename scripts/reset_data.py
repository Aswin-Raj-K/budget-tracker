"""Wipe all user-entered data so the app starts fresh.

Clears: accounts, categories, transactions, budgets, goals, subscriptions.
Keeps:  settings (currency, theme), schema_migrations.

On next app launch, `seed_default_categories_if_empty()` will re-seed
the default category list — you'll start with no accounts, no
transactions, no budgets, etc., but the UI won't look empty of
categories.

Usage::

    python scripts/reset_data.py
"""
from __future__ import annotations

from budget_tracker.config import db_path
from budget_tracker.core.db import init_db


_DATA_TABLES = (
    "transactions",
    "budgets",
    "subscriptions",
    "goals",
    "categories",
    "accounts",
)


def main() -> None:
    conn = init_db()
    counts: dict[str, int] = {}
    for table in _DATA_TABLES:
        counts[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        conn.execute(f"DELETE FROM {table}")
    conn.commit()
    print(f"Reset {db_path()}")
    for table in _DATA_TABLES:
        print(f"  {table}: cleared {counts[table]} rows")


if __name__ == "__main__":
    main()
