from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Literal

from budget_tracker.core.models import Category
from budget_tracker.core.repositories.budgets import BudgetRepository
from budget_tracker.core.repositories.categories import CategoryRepository
from budget_tracker.core.repositories.transactions import TransactionRepository
from budget_tracker.services._month import current_month, month_bounds

BudgetStatus = Literal["under", "warning", "over"]

WARNING_THRESHOLD = 80.0


@dataclass
class BudgetUsage:
    category: Category
    budget_amount: int       # monthly limit, minor units
    spent_amount: int        # actual spend this month, minor units (rolled up)
    percent: float           # 0..N (can exceed 100)
    status: BudgetStatus
    remaining: int           # may be negative when over


class BudgetService:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.budgets = BudgetRepository(conn)
        self.categories = CategoryRepository(conn)
        self.tx = TransactionRepository(conn)

    def usage_for_month(self, month: str | None = None) -> list[BudgetUsage]:
        month = month or current_month()
        start, end = month_bounds(month)

        budgets = self.budgets.for_month(month)
        if not budgets:
            return []

        spend_by_cat = self.tx.sum_by_category(start=start, end=end, kind="expense")
        all_categories = self.categories.list(include_archived=True)
        by_id = {c.id: c for c in all_categories}

        # Roll subcategory spend up into the parent. Budgets are top-level only.
        spend_by_top: dict[int, int] = {}
        for cat_id, amount in spend_by_cat.items():
            if cat_id is None:
                continue
            cat = by_id.get(cat_id)
            top_id = cat.parent_id if cat and cat.parent_id is not None else cat_id
            spend_by_top[top_id] = spend_by_top.get(top_id, 0) + amount

        out: list[BudgetUsage] = []
        for b in budgets:
            cat = by_id.get(b.category_id)
            if cat is None:
                continue
            spent = spend_by_top.get(b.category_id, 0)
            percent = (spent / b.amount * 100.0) if b.amount > 0 else 0.0
            status: BudgetStatus
            if percent >= 100:
                status = "over"
            elif percent >= WARNING_THRESHOLD:
                status = "warning"
            else:
                status = "under"
            out.append(
                BudgetUsage(
                    category=cat,
                    budget_amount=b.amount,
                    spent_amount=spent,
                    percent=percent,
                    status=status,
                    remaining=b.amount - spent,
                )
            )
        # sort by highest percent first — most-pressing budgets up top
        out.sort(key=lambda u: u.percent, reverse=True)
        return out
