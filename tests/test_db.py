from __future__ import annotations

from budget_tracker.core.db import connect, init_db, run_migrations

EXPECTED_TABLES = {
    "settings",
    "accounts",
    "categories",
    "transactions",
    "budgets",
    "goals",
    "subscriptions",
    "schema_migrations",
}


def _table_names(conn) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {r["name"] for r in rows}


def test_run_migrations_creates_all_tables():
    conn = init_db(":memory:")
    assert EXPECTED_TABLES.issubset(_table_names(conn))


def test_run_migrations_is_idempotent():
    conn = connect(":memory:")
    first = run_migrations(conn)
    second = run_migrations(conn)
    assert len(first) >= 1
    assert second == []


def test_foreign_keys_enabled():
    conn = init_db(":memory:")
    fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    assert fk == 1


def test_schema_migrations_records_applied():
    conn = init_db(":memory:")
    rows = conn.execute("SELECT name FROM schema_migrations ORDER BY name").fetchall()
    names = [r["name"] for r in rows]
    assert "001_init.sql" in names
    assert "002_subcategories.sql" in names


def test_categories_has_parent_id_column():
    conn = init_db(":memory:")
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(categories)")}
    assert "parent_id" in cols


def test_check_constraint_blocks_bad_account_type():
    conn = init_db(":memory:")
    try:
        conn.execute(
            "INSERT INTO accounts(name, type) VALUES (?, ?)",
            ("Bad", "not_a_real_type"),
        )
    except Exception as e:
        assert "CHECK" in str(e) or "constraint" in str(e).lower()
    else:
        raise AssertionError("CHECK constraint should have rejected the row")
