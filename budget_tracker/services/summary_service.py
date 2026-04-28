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
    top_category: Optional[Category]     # highest expense category, may be None
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

        by_cat = self.tx.sum_by_category(start=start, end=end, kind="expense")
        top_cat: Optional[Category] = None
        top_amount = 0
        if by_cat:
            cat_id, top_amount = max(by_cat.items(), key=lambda kv: kv[1])
            if cat_id is not None:
                cats = {c.id: c for c in self.categories.list(include_archived=True)}
                top_cat = cats.get(cat_id)

        return MonthlyKpis(
            month=month,
            spent=spent,
            income=income,
            savings_rate=savings_rate,
            top_category=top_cat,
            top_category_amount=top_amount,
        )

    def recent_transactions(self, limit: int = 8) -> list[Transaction]:
        return self.tx.list(limit=limit)
