"""Drop sample data into the user's local DB so the UI has something to look at.

Run once during development:

    python scripts/seed_demo.py

Idempotent-ish — wipes existing accounts/categories/transactions/budgets
before re-inserting, so feel free to run it repeatedly. Settings stay
intact.
"""
from __future__ import annotations

from datetime import date, timedelta

from budget_tracker.core.db import init_db
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
from budget_tracker.services._month import current_month, to_month_key


def _wipe(conn) -> None:
    for table in (
        "transactions", "budgets", "subscriptions", "goals",
        "categories", "accounts",
    ):
        conn.execute(f"DELETE FROM {table}")
    conn.commit()


CATEGORIES = [
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
]


def main() -> None:
    conn = init_db()
    _wipe(conn)

    accounts = AccountRepository(conn)
    cats = CategoryRepository(conn)
    txs = TransactionRepository(conn)
    budgets = BudgetRepository(conn)
    goals = GoalRepository(conn)
    subs = SubscriptionRepository(conn)

    # Accounts
    a_check = accounts.add(Account(None, "HDFC Checking", "checking", opening_balance=15000_00))
    a_save = accounts.add(Account(None, "ICICI Savings", "savings", opening_balance=120000_00))
    a_card = accounts.add(Account(None, "Amazon Pay Card", "credit", opening_balance=0))

    # Categories
    cat_ids: dict[str, int] = {}
    for name, kind, color, icon in CATEGORIES:
        c = cats.add(Category(None, name, kind, color, icon))
        cat_ids[name] = c.id

    today = date.today()
    month = current_month()

    # Salary income
    txs.add(Transaction(
        None, today.replace(day=1), "income", 95000_00,
        a_check.id, None, cat_ids["Salary"], "April salary",
    ))

    # Spread a handful of expenses across the month
    sample_expenses = [
        ("Groceries", 1245_00, "BigBasket"),
        ("Dining",    480_00,  "Lunch with team"),
        ("Transport", 260_00,  "Uber"),
        ("Groceries", 890_00,  "Local store"),
        ("Dining",    1320_00, "Sunday dinner"),
        ("Rent",      28000_00,"Monthly rent"),
        ("Utilities", 1850_00, "Electricity"),
        ("Shopping",  3499_00, "T-shirts"),
        ("Health",    600_00,  "Pharmacy"),
        ("Entertainment", 499_00, "Movie"),
        ("Subscriptions", 199_00, "Spotify"),
        ("Subscriptions", 649_00, "Netflix"),
        ("Transport", 320_00, "Metro card"),
        ("Dining",    260_00,  "Coffee"),
    ]
    for i, (cat_name, amount, note) in enumerate(sample_expenses):
        d = today - timedelta(days=i * 2)
        txs.add(Transaction(
            None, d, "expense", amount,
            a_check.id if i % 3 else a_card.id, None,
            cat_ids[cat_name], note,
        ))

    # Budgets for the current month
    budget_plan = {
        "Groceries":     6000_00,
        "Dining":        4000_00,
        "Transport":     3000_00,
        "Rent":          28000_00,
        "Utilities":     3500_00,
        "Shopping":      5000_00,
        "Entertainment": 2000_00,
        "Subscriptions": 1500_00,
    }
    for name, amount in budget_plan.items():
        budgets.upsert(Budget(None, cat_ids[name], amount, month))

    # Goals
    goals.add(Goal(None, "Emergency Fund", "savings", 200000_00, 78000_00, today + timedelta(days=180)))
    goals.add(Goal(None, "Tokyo Trip",     "savings", 150000_00, 22500_00, today + timedelta(days=300)))
    goals.add(Goal(None, "Card Balance",   "debt",    35000_00,  12000_00, None))

    # Subscriptions
    subs.add(Subscription(None, "Netflix",  649_00,  "monthly", today + timedelta(days=8),  cat_ids["Subscriptions"], a_card.id))
    subs.add(Subscription(None, "Spotify",  199_00,  "monthly", today + timedelta(days=12), cat_ids["Subscriptions"], a_card.id))
    subs.add(Subscription(None, "iCloud",   75_00,   "monthly", today + timedelta(days=20), cat_ids["Subscriptions"], a_card.id))
    subs.add(Subscription(None, "Domain",   1200_00, "yearly",  today + timedelta(days=200), cat_ids["Subscriptions"], a_check.id))

    print("Seeded demo data into:", conn)
    print(f"  accounts={len(accounts.list())} categories={len(cats.list())} "
          f"transactions={len(txs.list())} budgets={len(budgets.for_month(month))} "
          f"goals={len(goals.list())} subscriptions={len(subs.list())}")


if __name__ == "__main__":
    main()
