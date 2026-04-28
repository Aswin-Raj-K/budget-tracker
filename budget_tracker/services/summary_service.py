from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Optional

from budget_tracker.core.models import Category, Transaction
from budget_tracker.core.repositories.categories import CategoryRepository
from budget_tracker.core.repositories.transactions import TransactionRepository
from budget_tracker.services._month import current_month, month_bounds


@dataclass
class MonthlyKpis:
    month: str
    spent: int
    income: int
    savings_rate: float                  # 0..100, 0 if no income
    top_category: Optional[Category]     # highest expense category (rolled up to parent), may be None
    top_category_amount: int             # 0 if no top category


class SummaryService:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.tx = TransactionRepository(conn)
        self.categories = CategoryRepository(conn)

    def kpis_for_month(self, month: str | None = None) -> MonthlyKpis:
        month = month or current_month()
        start, end = month_bounds(month)

        spent = self.tx.sum_by_kind(kind="expense", start=start, end=end)
        income = self.tx.sum_by_kind(kind="income", start=start, end=end)
        savings_rate = 0.0
        if income > 0:
            savings_rate = max(0.0, (income - spent) / income * 100.0)

        # Top category: roll subcategory spend up to the parent so the KPI
        # shows "Groceries" rather than "Chicken".
        by_cat = self.tx.sum_by_category(start=start, end=end, kind="expense")
        cats = {c.id: c for c in self.categories.list(include_archived=True)}

        rolled: dict[int, int] = {}
        for cat_id, amount in by_cat.items():
            if cat_id is None:
                continue
            cat = cats.get(cat_id)
            top_id = cat.parent_id if cat and cat.parent_id is not None else cat_id
            rolled[top_id] = rolled.get(top_id, 0) + amount

        top_cat: Optional[Category] = None
        top_amount = 0
        if rolled:
            top_id, top_amount = max(rolled.items(), key=lambda kv: kv[1])
            top_cat = cats.get(top_id)

        return MonthlyKpis(
            month=month,
            spent=spent,
            income=income,
            savings_rate=savings_rate,
            top_category=top_cat,
            top_category_amount=top_amount,
        )

    def recent_transactions(
        self,
        limit: int = 8,
        month: Optional[str] = None,
    ) -> list[Transaction]:
        """Most-recent transactions, optionally restricted to a calendar month."""
        if month is None:
            return self.tx.list(limit=limit)
        start, end = month_bounds(month)
        return self.tx.list(start=start, end=end, limit=limit)
