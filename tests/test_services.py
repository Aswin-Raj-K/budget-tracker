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
from budget_tracker.services._month import (
    current_month,
    human_month,
    month_bounds,
    parse_month,
    shift_month,
    to_month_key,
)
from budget_tracker.services.account_service import AccountService
from budget_tracker.services.budget_service import BudgetService
from budget_tracker.services.goal_service import GoalService
from budget_tracker.services.settings_service import SettingsService
from budget_tracker.services.subscription_service import (
    SubscriptionService,
    monthly_equivalent,
    next_billing_after,
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


def test_shift_month_handles_year_boundaries():
    assert shift_month("2026-04", 1) == "2026-05"
    assert shift_month("2026-04", -1) == "2026-03"
    assert shift_month("2026-12", 1) == "2027-01"
    assert shift_month("2026-01", -1) == "2025-12"
    assert shift_month("2026-04", 12) == "2027-04"


def test_human_month():
    assert human_month("2026-04") == "April 2026"
    assert human_month("2026-12") == "December 2026"


def test_current_month_format():
    cm = current_month()
    assert len(cm) == 7 and cm[4] == "-"


# ---- settings service ----

def test_settings_service_theme(db):
    s = SettingsService(db)
    assert s.get_theme() == "dark"             # default when unset
    s.set_theme("light")
    assert s.get_theme() == "light"
    s.set_theme("midnight")                    # any non-empty id is fine
    assert s.get_theme() == "midnight"
    with pytest.raises(ValueError):
        s.set_theme("")                        # empty id rejected


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


def test_budget_usage_rolls_subcategory_spend_into_parent(db):
    """Spend on Groceries → Chicken counts toward the Groceries budget."""
    acct = AccountRepository(db).add(Account(None, "Cash", "cash"))
    parent = CategoryRepository(db).add(Category(None, "Groceries", "expense", "#F00", "x"))
    child = CategoryRepository(db).add(
        Category(None, "Chicken", "expense", "#F00", "x", parent_id=parent.id)
    )
    BudgetRepository(db).upsert(Budget(None, parent.id, 10000, "2026-04"))

    tx = TransactionRepository(db)
    # Mix of parent-direct and child spend, all rolls up to parent's budget.
    tx.add(Transaction(None, date(2026, 4, 5), "expense", 3000, acct.id, None, parent.id))
    tx.add(Transaction(None, date(2026, 4, 10), "expense", 4000, acct.id, None, child.id))

    usages = BudgetService(db).usage_for_month("2026-04")
    assert len(usages) == 1
    u = usages[0]
    assert u.category.name == "Groceries"
    assert u.spent_amount == 7000      # 3000 + 4000
    assert u.percent == pytest.approx(70.0)
    assert u.status == "under"


# ---- account service ----

def test_account_balance_starts_at_opening_balance(db):
    a = AccountRepository(db).add(Account(None, "Cash", "cash", opening_balance=15000))
    assert AccountService(db).balance_for(a.id) == 15000


def test_account_balance_with_income_and_expense(db):
    a = AccountRepository(db).add(Account(None, "Cash", "cash", opening_balance=10000))
    tx = TransactionRepository(db)
    tx.add(Transaction(None, date(2026, 5, 1), "income", 5000, a.id))
    tx.add(Transaction(None, date(2026, 5, 2), "expense", 2000, a.id))
    # 10000 + 5000 - 2000 = 13000
    assert AccountService(db).balance_for(a.id) == 13000


def test_account_balance_for_transfers(db):
    src = AccountRepository(db).add(Account(None, "Checking", "checking", opening_balance=20000))
    dst = AccountRepository(db).add(Account(None, "Savings",  "savings",  opening_balance=0))
    tx = TransactionRepository(db)
    tx.add(Transaction(
        None, date(2026, 5, 5), "transfer", 7500,
        account_id=src.id, transfer_account_id=dst.id,
    ))
    balances = AccountService(db).balances()
    assert balances[src.id] == 12500    # 20000 - 7500
    assert balances[dst.id] == 7500     # 0 + 7500


def test_account_balance_combined(db):
    """Income + expense + outgoing transfer + incoming transfer all in one
    account, plus the matching counterparty for the transfers."""
    main = AccountRepository(db).add(Account(None, "Main", "checking", opening_balance=10000))
    other = AccountRepository(db).add(Account(None, "Other", "savings"))
    tx = TransactionRepository(db)
    tx.add(Transaction(None, date(2026, 5, 1), "income",   3000, main.id))
    tx.add(Transaction(None, date(2026, 5, 2), "expense",  500,  main.id))
    # Out from main → other
    tx.add(Transaction(None, date(2026, 5, 3), "transfer", 1000, main.id, transfer_account_id=other.id))
    # In to main from other
    tx.add(Transaction(None, date(2026, 5, 4), "transfer", 200,  other.id, transfer_account_id=main.id))

    balances = AccountService(db).balances()
    # main: 10000 + 3000 - 500 - 1000 + 200 = 11700
    assert balances[main.id] == 11700
    # other: 0 + 1000 - 200 = 800
    assert balances[other.id] == 800


def test_account_balance_for_unknown_account(db):
    assert AccountService(db).balance_for(9999) == 0


# ---- credit-card balance (liability semantics) ----

def test_credit_card_expense_increases_debt(db):
    card = AccountRepository(db).add(Account(None, "Visa", "credit", opening_balance=0))
    tx = TransactionRepository(db)
    tx.add(Transaction(None, date(2026, 5, 1), "expense", 10000, card.id))
    tx.add(Transaction(None, date(2026, 5, 2), "expense", 5000, card.id))
    # Two expenses of 100 + 50 → owe 150 on the card.
    assert AccountService(db).balance_for(card.id) == 15000


def test_credit_card_opening_balance_is_existing_debt(db):
    """The opening balance on a credit card is the debt you already owe."""
    card = AccountRepository(db).add(Account(None, "Visa", "credit", opening_balance=50000))
    tx = TransactionRepository(db)
    tx.add(Transaction(None, date(2026, 5, 1), "expense", 10000, card.id))
    # Started at 500 owed, spent another 100 → owe 600.
    assert AccountService(db).balance_for(card.id) == 60000


def test_credit_card_income_reduces_debt(db):
    """Cashback / refunds posted as 'income' on the card reduce what's owed."""
    card = AccountRepository(db).add(Account(None, "Visa", "credit", opening_balance=10000))
    tx = TransactionRepository(db)
    tx.add(Transaction(None, date(2026, 5, 5), "income", 2000, card.id))
    # Owed 100, got 20 cashback → owe 80.
    assert AccountService(db).balance_for(card.id) == 8000


def test_credit_card_payment_from_checking_reduces_debt(db):
    """Transfer from checking → credit card pays down the card."""
    checking = AccountRepository(db).add(Account(None, "Bank", "checking", opening_balance=50000))
    card = AccountRepository(db).add(Account(None, "Visa", "credit", opening_balance=10000))
    tx = TransactionRepository(db)
    tx.add(Transaction(
        None, date(2026, 5, 10), "transfer", 7000,
        account_id=checking.id, transfer_account_id=card.id,
    ))
    balances = AccountService(db).balances()
    assert balances[checking.id] == 43000   # 500 − 70 paid
    assert balances[card.id] == 3000        # 100 owed → 30 owed


def test_credit_card_overpayment_goes_negative(db):
    """Paying more than you owe leaves a credit (negative debt) on the card."""
    checking = AccountRepository(db).add(Account(None, "Bank", "checking", opening_balance=50000))
    card = AccountRepository(db).add(Account(None, "Visa", "credit", opening_balance=2000))
    tx = TransactionRepository(db)
    tx.add(Transaction(
        None, date(2026, 5, 10), "transfer", 5000,
        account_id=checking.id, transfer_account_id=card.id,
    ))
    balances = AccountService(db).balances()
    assert balances[card.id] == -3000       # paid 50 against 20 owed → 30 credit


def test_credit_card_cash_advance_increases_debt(db):
    """Transfer FROM card → checking is a cash advance and grows the debt."""
    checking = AccountRepository(db).add(Account(None, "Bank", "checking", opening_balance=10000))
    card = AccountRepository(db).add(Account(None, "Visa", "credit", opening_balance=0))
    tx = TransactionRepository(db)
    tx.add(Transaction(
        None, date(2026, 5, 12), "transfer", 5000,
        account_id=card.id, transfer_account_id=checking.id,
    ))
    balances = AccountService(db).balances()
    assert balances[checking.id] == 15000   # 100 + 50 advanced
    assert balances[card.id] == 5000        # 0 → 50 owed


def test_subcategory_budget_tracks_own_spend_only(db):
    """A budget on Chicken only counts spend on Chicken, not on the parent."""
    acct = AccountRepository(db).add(Account(None, "Cash", "cash"))
    parent = CategoryRepository(db).add(Category(None, "Groceries", "expense", "#F00", "x"))
    chicken = CategoryRepository(db).add(
        Category(None, "Chicken", "expense", "#F00", "x", parent_id=parent.id)
    )
    BudgetRepository(db).upsert(Budget(None, chicken.id, 5000, "2026-04"))

    tx = TransactionRepository(db)
    tx.add(Transaction(None, date(2026, 4, 5), "expense", 3000, acct.id, None, chicken.id))
    tx.add(Transaction(None, date(2026, 4, 10), "expense", 9999, acct.id, None, parent.id))

    usages = BudgetService(db).usage_for_month("2026-04")
    assert len(usages) == 1
    assert usages[0].category.name == "Chicken"
    assert usages[0].spent_amount == 3000   # parent-direct spend is NOT included


def test_parent_and_subcategory_budgets_coexist(db):
    """Parent budget aggregates everything; sub budget tracks only itself.

    A single transaction on the subcategory counts toward both budgets —
    that's the YNAB-style overlap we explicitly want.
    """
    acct = AccountRepository(db).add(Account(None, "Cash", "cash"))
    parent = CategoryRepository(db).add(Category(None, "Groceries", "expense", "#F00", "x"))
    chicken = CategoryRepository(db).add(
        Category(None, "Chicken", "expense", "#F00", "x", parent_id=parent.id)
    )
    veg = CategoryRepository(db).add(
        Category(None, "Vegetables", "expense", "#0F0", "x", parent_id=parent.id)
    )
    repo = BudgetRepository(db)
    repo.upsert(Budget(None, parent.id, 10000, "2026-04"))
    repo.upsert(Budget(None, chicken.id, 3000, "2026-04"))

    tx = TransactionRepository(db)
    tx.add(Transaction(None, date(2026, 4, 5), "expense", 3500, acct.id, None, chicken.id))
    tx.add(Transaction(None, date(2026, 4, 6), "expense", 2000, acct.id, None, veg.id))

    by_name = {u.category.name: u for u in BudgetService(db).usage_for_month("2026-04")}

    # Parent rolls up Chicken + Vegetables.
    assert by_name["Groceries"].spent_amount == 5500
    assert by_name["Groceries"].budget_amount == 10000
    assert by_name["Groceries"].status == "under"

    # Chicken sub-budget tracks its own ₹3500 against ₹3000 cap → over.
    assert by_name["Chicken"].spent_amount == 3500
    assert by_name["Chicken"].budget_amount == 3000
    assert by_name["Chicken"].status == "over"

    # Vegetables has no budget so it doesn't appear separately.
    assert "Vegetables" not in by_name


def test_summary_top_category_rolls_up_to_parent(db):
    """KPI 'Top category' shows the parent name even when spend was on a child."""
    acct = AccountRepository(db).add(Account(None, "Cash", "cash"))
    groceries = CategoryRepository(db).add(Category(None, "Groceries", "expense", "#F00", "x"))
    chicken = CategoryRepository(db).add(
        Category(None, "Chicken", "expense", "#F00", "x", parent_id=groceries.id)
    )
    rent = CategoryRepository(db).add(Category(None, "Rent", "expense", "#0F0", "x"))

    tx = TransactionRepository(db)
    tx.add(Transaction(None, date(2026, 4, 1), "expense", 4000, acct.id, None, chicken.id))
    tx.add(Transaction(None, date(2026, 4, 5), "expense", 3500, acct.id, None, groceries.id))
    tx.add(Transaction(None, date(2026, 4, 10), "expense", 5000, acct.id, None, rent.id))

    k = SummaryService(db).kpis_for_month("2026-04")
    # Groceries rolled up = 7500, beats Rent at 5000.
    assert k.top_category is not None
    assert k.top_category.name == "Groceries"
    assert k.top_category_amount == 7500


def test_recent_transactions_filters_by_month(db):
    acct = AccountRepository(db).add(Account(None, "Cash", "cash"))
    tx = TransactionRepository(db)
    tx.add(Transaction(None, date(2026, 3, 15), "expense", 100, acct.id))
    tx.add(Transaction(None, date(2026, 4, 10), "expense", 200, acct.id))
    tx.add(Transaction(None, date(2026, 4, 28), "expense", 300, acct.id))

    svc = SummaryService(db)
    march = svc.recent_transactions(month="2026-03")
    april = svc.recent_transactions(month="2026-04")
    everything = svc.recent_transactions()
    assert [t.amount for t in march] == [100]
    assert [t.amount for t in april] == [300, 200]    # newest first
    assert len(everything) == 3


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


def test_goal_contribute_with_transfer_posts_real_money(db):
    """Contribute to a savings goal AND mirror it as a transfer between
    two real accounts. Both the goal counter and the account balances
    should reflect the move."""
    checking = AccountRepository(db).add(Account(None, "Checking", "checking", opening_balance=100000))
    savings = AccountRepository(db).add(Account(None, "Savings", "savings", opening_balance=0))
    g = GoalRepository(db).add(Goal(None, "Trip", "savings", 50000, 0))

    GoalService(db).contribute(
        g.id, 20000,
        transfer_from_id=checking.id,
        transfer_to_id=savings.id,
    )

    assert GoalRepository(db).get(g.id).current_amount == 20000
    balances = AccountService(db).balances()
    assert balances[checking.id] == 80000     # 1000 → 800
    assert balances[savings.id] == 20000      # 0 → 200


def test_goal_withdraw_with_transfer_reverses_direction(db):
    """A withdrawal is a negative delta; the user picks from = savings,
    to = checking, so real money flows back from savings to checking."""
    checking = AccountRepository(db).add(Account(None, "Checking", "checking", opening_balance=20000))
    savings = AccountRepository(db).add(Account(None, "Savings", "savings", opening_balance=80000))
    g = GoalRepository(db).add(Goal(None, "Trip", "savings", 50000, 80000))

    GoalService(db).contribute(
        g.id, -30000,
        transfer_from_id=savings.id,
        transfer_to_id=checking.id,
    )

    assert GoalRepository(db).get(g.id).current_amount == 50000
    balances = AccountService(db).balances()
    assert balances[savings.id] == 50000      # 800 − 300
    assert balances[checking.id] == 50000     # 200 + 300


def test_goal_contribute_without_transfer_only_bumps_progress(db):
    """If neither transfer account is provided, behaviour matches the old
    contribute(): only the goal counter changes, no transactions."""
    checking = AccountRepository(db).add(Account(None, "Checking", "checking", opening_balance=100000))
    g = GoalRepository(db).add(Goal(None, "Save", "savings", 50000, 0))

    GoalService(db).contribute(g.id, 5000)

    assert GoalRepository(db).get(g.id).current_amount == 5000
    assert AccountService(db).balance_for(checking.id) == 100000   # untouched
    assert TransactionRepository(db).list() == []


def test_goal_contribute_rejects_destination_without_source(db):
    """A destination without a source is meaningless. Previously we also
    rejected source-without-destination, but that's now valid — it's
    the expense path (paying an external payee from a tracked account).
    """
    g = GoalRepository(db).add(Goal(None, "Save", "savings", 50000, 0))
    acct = AccountRepository(db).add(Account(None, "Bank", "checking"))

    with pytest.raises(ValueError, match="source account"):
        GoalService(db).contribute(g.id, 1000, to_account_id=acct.id)


def test_goal_contribute_rejects_same_source_and_destination(db):
    g = GoalRepository(db).add(Goal(None, "Save", "savings", 50000, 0))
    acct = AccountRepository(db).add(Account(None, "Bank", "checking"))

    with pytest.raises(ValueError, match="must differ"):
        GoalService(db).contribute(
            g.id, 1000,
            transfer_from_id=acct.id,
            transfer_to_id=acct.id,
        )


def test_goal_contribute_with_transfer_tags_transaction_with_goal_id(db):
    """The transfer transaction posted on contribute carries goal_id back
    to the goal, so the Goals tab can find its linked transactions."""
    checking = AccountRepository(db).add(Account(None, "Checking", "checking", opening_balance=100000))
    savings = AccountRepository(db).add(Account(None, "Savings", "savings"))
    g = GoalRepository(db).add(Goal(None, "Trip", "savings", 50000, 0))

    GoalService(db).contribute(
        g.id, 5000,
        transfer_from_id=checking.id,
        transfer_to_id=savings.id,
    )
    linked = TransactionRepository(db).list(goal_id=g.id)
    assert len(linked) == 1
    assert linked[0].amount == 5000
    assert linked[0].kind == "transfer"
    assert linked[0].goal_id == g.id


def test_goal_make_payment_as_expense_for_external_debt(db):
    """A debt payment to a payee outside the app — e.g. a mortgage —
    should post as an expense from the chosen account, with optional
    category, NOT a transfer."""
    checking = AccountRepository(db).add(Account(None, "Checking", "checking", opening_balance=300000))
    cat = CategoryRepository(db).add(Category(None, "Loan Payment", "expense", "#F87171", "🏦"))
    g = GoalRepository(db).add(Goal(None, "Mortgage", "debt", 5_000_000, 0))

    GoalService(db).contribute(
        g.id, 150000,
        from_account_id=checking.id,
        category_id=cat.id,
    )

    # Goal counter advanced.
    assert GoalRepository(db).get(g.id).current_amount == 150000

    # An expense was posted, not a transfer — and it's tagged with goal_id + category.
    txs = TransactionRepository(db).list(goal_id=g.id)
    assert len(txs) == 1
    assert txs[0].kind == "expense"
    assert txs[0].account_id == checking.id
    assert txs[0].transfer_account_id is None
    assert txs[0].category_id == cat.id

    # Account balance reflects the outflow.
    assert AccountService(db).balance_for(checking.id) == 150000


def test_goal_expense_mode_works_without_category(db):
    """Category is optional in expense mode (uncategorised loan payment)."""
    checking = AccountRepository(db).add(Account(None, "Checking", "checking", opening_balance=200000))
    g = GoalRepository(db).add(Goal(None, "Loan", "debt", 1_000_000, 0))

    GoalService(db).contribute(g.id, 50000, from_account_id=checking.id)

    txs = TransactionRepository(db).list(goal_id=g.id)
    assert len(txs) == 1
    assert txs[0].kind == "expense"
    assert txs[0].category_id is None


def test_goal_delete_unlinks_transactions(db):
    """Deleting a goal preserves the linked transactions but clears their
    goal_id so they're no longer attached to a non-existent goal."""
    checking = AccountRepository(db).add(Account(None, "Checking", "checking", opening_balance=100000))
    savings = AccountRepository(db).add(Account(None, "Savings", "savings"))
    g = GoalRepository(db).add(Goal(None, "Trip", "savings", 50000, 0))
    GoalService(db).contribute(
        g.id, 5000,
        transfer_from_id=checking.id,
        transfer_to_id=savings.id,
    )

    GoalRepository(db).delete(g.id)

    # Transactions are still on file (history preserved), just unlinked.
    all_tx = TransactionRepository(db).list()
    assert len(all_tx) == 1
    assert all_tx[0].goal_id is None

    # Account balances are still affected by those transactions.
    balances = AccountService(db).balances()
    assert balances[checking.id] == 95000
    assert balances[savings.id] == 5000


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


# ---- next_billing_after (cycle math) ----

def test_next_billing_after_weekly():
    assert next_billing_after(date(2026, 5, 1), "weekly") == date(2026, 5, 8)


def test_next_billing_after_monthly_simple():
    assert next_billing_after(date(2026, 5, 1), "monthly") == date(2026, 6, 1)


def test_next_billing_after_monthly_clamps_end_of_month():
    # Jan 31 + 1 month → Feb 28 (or Feb 29 in a leap year), not "Feb 31".
    assert next_billing_after(date(2026, 1, 31), "monthly") == date(2026, 2, 28)
    assert next_billing_after(date(2024, 1, 31), "monthly") == date(2024, 2, 29)


def test_next_billing_after_monthly_year_rollover():
    assert next_billing_after(date(2026, 12, 15), "monthly") == date(2027, 1, 15)


def test_next_billing_after_yearly():
    assert next_billing_after(date(2026, 5, 1), "yearly") == date(2027, 5, 1)


def test_next_billing_after_yearly_leap_day_clamps():
    assert next_billing_after(date(2024, 2, 29), "yearly") == date(2025, 2, 28)


def test_next_billing_after_unknown_cycle():
    with pytest.raises(ValueError):
        next_billing_after(date(2026, 5, 1), "fortnightly")


# ---- mark_as_paid ----

def test_mark_as_paid_creates_expense_and_rolls_date(db):
    acct = AccountRepository(db).add(Account(None, "Card", "credit"))
    cat = CategoryRepository(db).add(Category(None, "Subs", "expense", "#7C5CFF", "🔁"))
    sub = SubscriptionRepository(db).add(Subscription(
        None, "Netflix", 50000, "monthly", date(2026, 5, 1),
        category_id=cat.id, account_id=acct.id,
    ))

    svc = SubscriptionService(db)
    tx = svc.mark_as_paid(sub.id)

    assert tx.id is not None
    assert tx.kind == "expense"
    assert tx.amount == 50000
    assert tx.account_id == acct.id
    assert tx.category_id == cat.id
    assert tx.note == "Netflix"
    assert tx.occurred_on == date(2026, 5, 1)

    refreshed = SubscriptionRepository(db).get(sub.id)
    assert refreshed.next_billing_date == date(2026, 6, 1)


def test_mark_as_paid_yearly_rolls_a_year(db):
    acct = AccountRepository(db).add(Account(None, "Bank", "checking"))
    sub = SubscriptionRepository(db).add(Subscription(
        None, "Domain", 120000, "yearly", date(2026, 7, 15),
        account_id=acct.id,
    ))

    SubscriptionService(db).mark_as_paid(sub.id)

    refreshed = SubscriptionRepository(db).get(sub.id)
    assert refreshed.next_billing_date == date(2027, 7, 15)


def test_mark_as_paid_without_account_raises(db):
    sub = SubscriptionRepository(db).add(Subscription(
        None, "Mystery", 1000, "monthly", date(2026, 5, 1),
        # account_id omitted → no debit target
    ))
    with pytest.raises(ValueError, match="no account set"):
        SubscriptionService(db).mark_as_paid(sub.id)


def test_mark_as_paid_carries_into_credit_card_balance(db):
    """End-to-end: marking a subscription paid should land in the credit
    card's running balance via AccountService."""
    card = AccountRepository(db).add(Account(None, "Visa", "credit"))
    sub = SubscriptionRepository(db).add(Subscription(
        None, "Spotify", 9900, "monthly", date(2026, 5, 1),
        account_id=card.id,
    ))

    SubscriptionService(db).mark_as_paid(sub.id)

    # Credit card debt grows by the subscription amount.
    assert AccountService(db).balance_for(card.id) == 9900
