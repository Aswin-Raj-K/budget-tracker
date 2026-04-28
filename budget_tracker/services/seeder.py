"""First-launch seeding of default reference data."""
from __future__ import annotations

import sqlite3

from budget_tracker.core.models import Category
from budget_tracker.core.repositories.categories import CategoryRepository

# (name, kind, color, icon)
DEFAULT_CATEGORIES: list[tuple[str, str, str, str]] = [
    ("Groceries",     "expense", "#34D399", "🛒"),
    ("Dining",        "expense", "#F97316", "🍽"),
    ("Transport",     "expense", "#3B82F6", "🚌"),
    ("Rent",          "expense", "#EF4444", "🏠"),
    ("Utilities",     "expense", "#A855F7", "💡"),
    ("Shopping",      "expense", "#EC4899", "🛍"),
    ("Entertainment", "expense", "#F59E0B", "🎬"),
    ("Health",        "expense", "#06B6D4", "🩺"),
    ("Education",     "expense", "#10B981", "🎓"),
    ("Subscriptions", "expense", "#8B5CF6", "🔁"),
    ("Other",         "expense", "#6B7280", "•"),
    ("Salary",        "income",  "#22C55E", "💼"),
    ("Freelance",     "income",  "#14B8A6", "🧑‍💻"),
    ("Gifts",         "income",  "#F472B6", "🎁"),
    ("Other income",  "income",  "#94A3B8", "•"),
]


def seed_default_categories_if_empty(conn: sqlite3.Connection) -> int:
    """Insert the default category set if no categories exist yet.

    Returns the number of categories inserted (0 if seeding was skipped).
    """
    repo = CategoryRepository(conn)
    if repo.list(include_archived=True):
        return 0
    for name, kind, color, icon in DEFAULT_CATEGORIES:
        repo.add(Category(id=None, name=name, kind=kind, color=color, icon=icon))
    return len(DEFAULT_CATEGORIES)
