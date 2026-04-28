from __future__ import annotations

from budget_tracker.core.repositories.categories import CategoryRepository
from budget_tracker.services.seeder import (
    DEFAULT_CATEGORIES,
    seed_default_categories_if_empty,
)


def test_seeds_when_empty(db):
    inserted = seed_default_categories_if_empty(db)
    assert inserted == len(DEFAULT_CATEGORIES)
    cats = CategoryRepository(db).list(include_archived=True)
    assert len(cats) == len(DEFAULT_CATEGORIES)


def test_skips_when_categories_exist(db):
    seed_default_categories_if_empty(db)
    inserted = seed_default_categories_if_empty(db)
    assert inserted == 0


def test_default_categories_have_expected_kinds():
    expense = [c for c in DEFAULT_CATEGORIES if c[1] == "expense"]
    income  = [c for c in DEFAULT_CATEGORIES if c[1] == "income"]
    assert len(expense) >= 5  # need a useful set
    assert len(income) >= 1
