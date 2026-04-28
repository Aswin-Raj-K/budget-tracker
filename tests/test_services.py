from __future__ import annotations

from datetime import date

import pytest

from budget_tracker.core import money
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
from budget_tracker.core.repositories.subscriptions import SubscriptionRepository
from budget_tracker.core.repositories.transactions import TransactionRepository
from budget_tracker.services._month import current_month, month_bounds, parse_month, to_month_key
from budget_tracker.services.budget_service import BudgetService
from budget_tracker.services.goal_service import GoalService
from budget_tracker.services.settings_service import SettingsService
from budget_tracker.services.subscription_service import (
    SubscriptionService,
    monthly_equivalent,
)
from budget_tracker.services.summary_service import SummaryService


# ---- _month helpers ----

def test_month_bounds():
    assert month_bounds("2026-04") == (date(2026, 4, 1), date(2026, 4, 30))
    assert month_bounds("2026-02") == (date(2026, 2, 1), date(2026, 2, 28))
    assert month_bounds("2024-02") == (date(2024, 2, 1), date(2024, 2, 29))  # leap


def test_parse_month_validates():
    with pytest.raises(ValueError):
        parse_month("2026")
    with pytest.raises(ValueError):
        parse_month("2026-13")


def test_to_month_key():
    assert to_month_key(date(2026, 4, 15)) == "2026-04"
    assert to_month_key(date(2026, 1, 1)) == "2026-01"


def test_current_month_format():
    cm = current_month()
    assert len(cm) == 7 and cm[4] == "-"


# ---- settings service ----

def test_settings_service_theme(db):
    s = SettingsService(db)
    assert s.get_theme() == "dark"             # default when unset
    s.set_theme("light")
    assert s.get_theme() == "light"
    with pytest.raises(ValueError):
        s.set_theme("neon")


def test_settings_service_currency_lifecycle(db):
    s = SettingsService(db)
    assert s.has_currency() is False
    s.set_currency("USD")
    assert s.has_currency() is True
    assert s.get_currency_code() == "USD"
    assert money.active().code == "USD"        # session updated

    s.apply_to_session()
    assert money.active().code == "USD"

    with pytest.raises(ValueError):
        s.set_currency("XYZ")
    money.set_active("INR")  # restore


# ---- budget service ----

def _seed_budget_scenario(db):
    acct = AccountRepository(db).add(Account(None, "Cash", "cash"))
    food = CategoryRepository(db).add(Category(None, "Food", "expense", "#F00", "x"))
    rent = CategoryRepository(db).add(Category(None, "Rent", "expense", "#0F0", "x"))
    BudgetRepository(db).upsert(Budget(None, food.id, 10000, "2026-04"))
    BudgetRepository(db).upsert(Budget(None, rent.id, 50000, "2026-04"))
    return acct, food, rent


def test_budget_usage_under_warning_over(db):
    acct, food, rent = _seed_budget_scenario(db)
    tx = TransactionRepository(db)
    # food: 9000 / 10000 = 90% -> warning
    tx.add(Transaction(None, date(2026, 4, 5), "expense", 9000, acct.id, None, food.id))
    # rent: 60000 / 50000 = 120% -> over
    tx.add(Transaction(None, date(2026, 4, 10), "expense", 60000, acct.id, None, rent.id))

    usages = BudgetService(db).usage_for_month("2026-04")
    by_name = {u.category.name: u for u in usages}
    assert by_name["Food"].status == "warning"
    assert by_name["Food"].percent == pytest.approx(90.0)
    assert by_name["Rent"].status == "over"
    assert by_name["Rent"].remaining == -10000
    # sorted by descending percent — Rent (120) before Food (90)
    assert usages[0].category.name == "Rent"


def test_budget_usage_under_with_no_spend(db):
    _, food, _ = _seed_budget_scenario(db)
    usages = BudgetService(db).usage_for_month("2026-04")
    food_usage = next(u for u in usages if u.category.name == "Food")
    assert food_usage.spent_amount == 0
    assert food_usage.status == "under"
    assert food_usage.percent == 0.0


def test_budget_usage_empty_when_no_budgets(db):
    assert BudgetService(db).usage_for_month("2026-04") == []


# ---- goal service ----

def test_goal_progress_basic(db):
    g = GoalRepository(db).add(
        Goal(None, "Trip", "savings", target_amount=100000, current_amount=25000,
             deadline=date(2026, 6, 1))
    )
    p = GoalService(db).progress(g.id, today=date(2026, 4, 27))
    assert p.percent == pytest.approx(25.0)
    assert p.remaining == 75000
    assert p.days_remaining == (date(2026, 6, 1) - date(2026, 4, 27)).days
    assert p.is_complete is False


def test_goal_progress_complete_caps_at_100(db):
    g = GoalRepository(db).add(
        Goal(None, "Done", "savings", target_amount=1000, current_amount=5000)
    )
    p = GoalService(db).progress(g.id)
    assert p.percent == 100.0
    assert p.is_complete is True
    assert p.remaining == 0


def test_goal_contribute_via_service(db):
    g = GoalRepository(db).add(Goal(None, "Save", "savings", 10000, 0))
    GoalService(db).contribute(g.id, 3000)
    assert GoalRepository(db).get(g.id).current_amount == 3000


# ---- summary service ----

def test_summary_kpis(db):
    acct = AccountRepository(db).add(Account(None, "Cash", "cash"))
    food = CategoryRepository(db).add(Category(None, "Food", "expense", "#F00", "x"))
    rent = CategoryRepository(db).add(Category(None, "Rent", "expense", "#0F0", "x"))
    tx = TransactionRepository(db)
    tx.add(Transaction(None, date(2026, 4, 1), "expense", 1000, acct.id, None, food.id))
    tx.add(Transaction(None, date(2026, 4, 5), "expense", 4000, acct.id, None, rent.id))
    tx.add(Transaction(None, date(2026, 4, 10), "income", 10000, acct.id, None, None))

    k = SummaryService(db).kpis_for_month("2026-04")
    assert k.spent == 5000
    assert k.income == 10000
    assert k.savings_rate == pytest.approx(50.0)
    assert k.top_category is not None
    assert k.top_category.name == "Rent"
    assert k.top_category_amount == 4000


def test_summary_kpis_empty_month(db):
    k = SummaryService(db).kpis_for_month("2026-04")
    assert k.spent == 0
    assert k.income == 0
    assert k.savings_rate == 0.0
    assert k.top_category is None


def test_summary_kpis_savings_rate_when_overspent(db):
    acct = AccountRepository(db).add(Account(None, "Cash", "cash"))
    food = CategoryRepository(db).add(Category(None, "Food", "expense", "#F00", "x"))
    tx = TransactionRepository(db)
    tx.add(Transaction(None, date(2026, 4, 1), "expense", 5000, acct.id, None, food.id))
    tx.add(Transaction(None, date(2026, 4, 10), "income", 1000, acct.id, None, None))
    k = SummaryService(db).kpis_for_month("2026-04")
    assert k.savings_rate == 0.0  # clamped at 0 when overspent


def test_summary_recent_transactions_limit(db):
    acct = AccountRepository(db).add(Account(None, "Cash", "cash"))
    tx = TransactionRepository(db)
    for i in range(15):
        tx.add(Transaction(None, date(2026, 4, i + 1), "expense", 100 + i, acct.id, None, None))
    recent = SummaryService(db).recent_transactions(limit=5)
    assert len(recent) == 5
    # newest first
    assert recent[0].occurred_on == date(2026, 4, 15)


# ---- subscription service ----

def test_monthly_equivalent_for_each_cycle():
    base = Subscription(None, "X", 12000, "monthly", date(2026, 5, 1))
    assert monthly_equivalent(base) == 12000

    yearly = Subscription(None, "X", 144000, "yearly", date(2026, 5, 1))
    assert monthly_equivalent(yearly) == 12000

    weekly = Subscription(None, "X", 1000, "weekly", date(2026, 5, 1))
    # 1000 * 52 / 12 = 4333
    assert monthly_equivalent(weekly) == 4333


def test_subscription_summary_total(db):
    repo = SubscriptionRepository(db)
    repo.add(Subscription(None, "Netflix", 50000, "monthly", date(2026, 5, 1)))
    repo.add(Subscription(None, "Annual SaaS", 240000, "yearly", date(2026, 12, 1)))

    summary = SubscriptionService(db).summary()
    # 50000 + (240000 / 12 = 20000) = 70000
    assert summary.total_monthly == 70000
    assert len(summary.items) == 2


def test_subscription_summary_active_only(db):
    repo = SubscriptionRepository(db)
    repo.add(Subscription(None, "On", 10000, "monthly", date(2026, 5, 1)))
    inactive = repo.add(Subscription(None, "Off", 50000, "monthly", date(2026, 5, 1)))
    inactive.active = False
    repo.update(inactive)

    summary = SubscriptionService(db).summary()
    assert summary.total_monthly == 10000
    assert len(summary.items) == 1
