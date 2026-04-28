from __future__ import annotations

import pytest

from budget_tracker.core.db import init_db


@pytest.fixture
def db():
    """Fresh in-memory SQLite connection with migrations applied."""
    conn = init_db(":memory:")
    yield conn
    conn.close()
