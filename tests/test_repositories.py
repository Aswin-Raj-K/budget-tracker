from __future__ import annotations

from datetime import date

import pytest

from budget_tracker.core.models import (
    Account,
    Budget,
    Category,
    Goal,
    Subscription,
    Transaction,
)
from budget_tracker.core.repositories.accounts import AccountRepository
from budget_tracker.core.repositories.budgets import BudgetRepository
from budget_tracker.core.repositories.categories import CategoryRepository
from budget_tracker.core.repositories.goals import GoalRepository
from budget_tracker.core.repositories.settings import SettingsRepository
from budget_tracker.core.repositories.subscriptions import SubscriptionRepository
from budget_tracker.core.repositories.transactions import TransactionRepository


# ---- helpers ----

def _make_account(db, name="Checking", type_="checking", opening=0) -> Account:
    return AccountRepository(db).add(
        Account(id=None, name=name, type=type_, opening_balance=opening)
    )


def _make_category(db, name="Food", kind="expense", color="#FF0000", icon="utensils") -> Category:
    return CategoryRepository(db).add(
        Category(id=None, name=name, kind=kind, color=color, icon=icon)
    )


# ---- settings ----

def test_settings_set_and_get(db):
    s = SettingsRepository(db)
    assert s.get("theme") is None
    s.set("theme", "dark")
    assert s.get("theme") == "dark"
    s.set("theme", "light")  # upsert
    assert s.get("theme") == "light"


def test_settings_all(db):
    s = SettingsRepository(db)
    s.set("theme", "dark")
    s.set("currency", "INR")
    assert s.all() == {"theme": "dark", "currency": "INR"}


# ---- accounts ----

def test_account_add_get_list(db):
    repo = AccountRepository(db)
    a = repo.add(Account(id=None, name="Cash", type="cash", opening_balance=5000))
    assert a.id is not None
    assert a.name == "Cash"
    assert a.opening_balance == 5000

    fetched = repo.get(a.id)
    assert fetched.name == "Cash"

    assert len(repo.list()) == 1


def test_account_archived_filter(db):
    repo = AccountRepository(db)
    a = repo.add(Account(id=None, name="Old", type="cash"))
    a.archived = True
    repo.update(a)

    assert repo.list() == []
    assert len(repo.list(include_archived=True)) == 1


def test_account_invalid_type_rejected(db):
    repo = AccountRepository(db)
    with pytest.raises(Exception):
        repo.add(Account(id=None, name="X", type="bogus"))  # type: ignore[arg-type]


# ---- categories ----

def test_category_filter_by_kind(db):
    repo = CategoryRepository(db)
    repo.add(Category(id=None, name="Food", kind="expense", color="#F00", icon="x"))
    repo.add(Category(id=None, name="Salary", kind="income", color="#0F0", icon="x"))
    assert [c.name for c in repo.list(kind="expense")] == ["Food"]
    assert [c.name for c in repo.list(kind="income")] == ["Salary"]
    assert len(repo.list()) == 2


def test_category_parent_id_round_trip(db):
    repo = CategoryRepository(db)
    parent = repo.add(Category(None, "Groceries", "expense", "#F00", "x"))
    child = repo.add(Category(None, "Chicken", "expense", "#F00", "x", parent_id=parent.id))
    fetched = repo.get(child.id)
    assert fetched.parent_id == parent.id


def test_list_top_level_excludes_children(db):
    repo = CategoryRepository(db)
    parent = repo.add(Category(None, "Groceries", "expense", "#F00", "x"))
    repo.add(Category(None, "Chicken", "expense", "#F00", "x", parent_id=parent.id))
    repo.add(Category(None, "Salary", "income", "#0F0", "x"))

    expense_top = [c.name for c in repo.list_top_level(kind="expense")]
    assert expense_top == ["Groceries"]

    all_top = {c.name for c in repo.list_top_level()}
    assert all_top == {"Groceries", "Salary"}


def test_children_of(db):
    repo = CategoryRepository(db)
    parent = repo.add(Category(None, "Groceries", "expense", "#F00", "x"))
    repo.add(Category(None, "Chicken", "expense", "#F00", "x", parent_id=parent.id))
    repo.add(Category(None, "Vegetables", "expense", "#F00", "x", parent_id=parent.id))
    other = repo.add(Category(None, "Dining", "expense", "#F00", "x"))

    kids = repo.children_of(parent.id)
    assert sorted(c.name for c in kids) == ["Chicken", "Vegetables"]
    assert repo.children_of(other.id) == []


def test_top_level_id_for(db):
    repo = CategoryRepository(db)
    parent = repo.add(Category(None, "Groceries", "expense", "#F00", "x"))
    child = repo.add(Category(None, "Chicken", "expense", "#F00", "x", parent_id=parent.id))
    assert repo.top_level_id_for(parent.id) == parent.id
    assert repo.top_level_id_for(child.id) == parent.id


def test_delete_parent_promotes_children_to_top_level(db):
    repo = CategoryRepository(db)
    parent = repo.add(Category(None, "Groceries", "expense", "#F00", "x"))
    child = repo.add(Category(None, "Chicken", "expense", "#F00", "x", parent_id=parent.id))
    repo.delete(parent.id)

    surviving = repo.get(child.id)
    assert surviving.parent_id is None


# ---- transactions ----

def test_transaction_add_and_list(db):
    acct = _make_account(db)
    cat = _make_category(db)
    repo = TransactionRepository(db)

    tx = repo.add(
        Transaction(
            id=None,
            occurred_on=date(2026, 4, 1),
            kind="expense",
            amount=12345,
            account_id=acct.id,  # type: ignore[arg-type]
            category_id=cat.id,
            note="lunch",
        )
    )
    assert tx.id is not None

    rows = repo.list()
    assert len(rows) == 1
    assert rows[0].note == "lunch"


def test_transaction_filters(db):
    acct = _make_account(db)
    food = _make_category(db, name="Food")
    rent = _make_category(db, name="Rent")
    repo = TransactionRepository(db)

    repo.add(Transaction(None, date(2026, 4, 1), "expense", 100, acct.id, None, food.id))  # type: ignore[arg-type]
    repo.add(Transaction(None, date(2026, 4, 15), "expense", 200, acct.id, None, rent.id))  # type: ignore[arg-type]
    repo.add(Transaction(None, date(2026, 5, 1), "income", 5000, acct.id, None, None))  # type: ignore[arg-type]

    apr = repo.list(start=date(2026, 4, 1), end=date(2026, 4, 30))
    assert len(apr) == 2

    food_only = repo.list(category_id=food.id)
    assert len(food_only) == 1
    assert food_only[0].amount == 100

    incomes = repo.list(kind="income")
    assert len(incomes) == 1


def test_transaction_aggregations(db):
    acct = _make_account(db)
    food = _make_category(db, name="Food")
    rent = _make_category(db, name="Rent")
    repo = TransactionRepository(db)

    repo.add(Transaction(None, date(2026, 4, 1), "expense", 100, acct.id, None, food.id))  # type: ignore[arg-type]
    repo.add(Transaction(None, date(2026, 4, 15), "expense", 250, acct.id, None, food.id))  # type: ignore[arg-type]
    repo.add(Transaction(None, date(2026, 4, 20), "expense", 500, acct.id, None, rent.id))  # type: ignore[arg-type]
    repo.add(Transaction(None, date(2026, 4, 30), "income", 9000, acct.id, None, None))  # type: ignore[arg-type]

    total_exp = repo.sum_by_kind(kind="expense", start=date(2026, 4, 1), end=date(2026, 4, 30))
    assert total_exp == 850

    total_inc = repo.sum_by_kind(kind="income", start=date(2026, 4, 1), end=date(2026, 4, 30))
    assert total_inc == 9000

    by_cat = repo.sum_by_category(start=date(2026, 4, 1), end=date(2026, 4, 30))
    assert by_cat[food.id] == 350
    assert by_cat[rent.id] == 500


# ---- budgets ----

def test_budget_upsert_replaces_amount(db):
    cat = _make_category(db)
    repo = BudgetRepository(db)
    b1 = repo.upsert(Budget(id=None, category_id=cat.id, amount=10000, effective_from="2026-04"))
    b2 = repo.upsert(Budget(id=None, category_id=cat.id, amount=15000, effective_from="2026-04"))
    assert b1.id == b2.id
    assert b2.amount == 15000


def test_budget_for_month_picks_latest_effective(db):
    cat = _make_category(db)
    repo = BudgetRepository(db)
    repo.upsert(Budget(None, cat.id, 5000, "2026-01"))
    repo.upsert(Budget(None, cat.id, 8000, "2026-04"))

    march = repo.for_month("2026-03")
    assert march[0].amount == 5000

    may = repo.for_month("2026-05")
    assert may[0].amount == 8000

    pre = repo.for_month("2025-12")
    assert pre == []


# ---- goals ----

def test_goal_contribute_clamped_at_zero(db):
    repo = GoalRepository(db)
    g = repo.add(Goal(id=None, name="Trip", kind="savings", target_amount=100000, current_amount=2000))
    assert repo.contribute(g.id, 5000).current_amount == 7000
    assert repo.contribute(g.id, -3000).current_amount == 4000
    assert repo.contribute(g.id, -99999).current_amount == 0  # clamped


def test_goal_filter_by_kind(db):
    repo = GoalRepository(db)
    repo.add(Goal(None, "Trip", "savings", 100))
    repo.add(Goal(None, "Loan", "debt", 100))
    assert {g.name for g in repo.list(kind="savings")} == {"Trip"}
    assert {g.name for g in repo.list(kind="debt")} == {"Loan"}


# ---- subscriptions ----

def test_subscription_active_filter(db):
    repo = SubscriptionRepository(db)
    repo.add(Subscription(None, "Netflix", 50000, "monthly", date(2026, 5, 1)))
    s_inactive = repo.add(
        Subscription(None, "Old Mag", 20000, "yearly", date(2026, 12, 1))
    )
    s_inactive.active = False
    repo.update(s_inactive)

    assert {s.name for s in repo.list(active_only=True)} == {"Netflix"}
    assert len(repo.list()) == 2
