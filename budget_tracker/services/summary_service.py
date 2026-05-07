from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
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


@dataclass
class CategorySpend:
    category: Category
    own_amount: int          # spend recorded directly on this category (excludes children)
    rolled_up_amount: int    # for parents, includes all child spend; for subs, == own_amount
    percent: float           # of the month's total expense (0..100)


@dataclass
class CategoryGroup:
    """A top-level category and its (optional) subcategory rows."""
    parent: CategorySpend
    children: list[CategorySpend] = field(default_factory=list)


@dataclass
class CategoryBreakdown:
    month: str
    total: int                                  # sum of expense across the month
    groups: list[CategoryGroup]                 # ordered by parent rolled-up amount, descending
    uncategorised: int                          # expense with category_id IS NULL


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

    def category_breakdown_for_month(
        self, month: str | None = None
    ) -> CategoryBreakdown:
        """Group every category that has expense in the month into
        parent → children rows with own / rolled-up amounts and a
        percent of total."""
        month = month or current_month()
        start, end = month_bounds(month)

        by_cat = self.tx.sum_by_category(start=start, end=end, kind="expense")
        cats = {c.id: c for c in self.categories.list(include_archived=True)}

        # Roll subcategory amounts up to parents.
        own: dict[Optional[int], int] = dict(by_cat)            # by category id
        rolled: dict[int, int] = {}
        for cat_id, amount in by_cat.items():
            if cat_id is None:
                continue
            cat = cats.get(cat_id)
            if cat is None:
                continue
            target = cat.parent_id if cat.parent_id is not None else cat_id
            rolled[target] = rolled.get(target, 0) + amount

        total = sum(by_cat.values())
        uncategorised = own.get(None, 0)

        def _pct(n: int) -> float:
            return (n / total * 100.0) if total > 0 else 0.0

        groups: list[CategoryGroup] = []
        seen_subs: set[int] = set()

        # Top-level parents that had any spend (own or via children).
        parent_ids_with_spend = sorted(
            (pid for pid in rolled if cats.get(pid) and cats[pid].parent_id is None),
            key=lambda pid: rolled[pid],
            reverse=True,
        )
        for pid in parent_ids_with_spend:
            parent_cat = cats[pid]
            parent_row = CategorySpend(
                category=parent_cat,
                own_amount=own.get(pid, 0),
                rolled_up_amount=rolled[pid],
                percent=_pct(rolled[pid]),
            )
            children: list[CategorySpend] = []
            for cid, c in cats.items():
                if c.parent_id == pid and own.get(cid, 0) > 0:
                    children.append(CategorySpend(
                        category=c,
                        own_amount=own[cid],
                        rolled_up_amount=own[cid],
                        percent=_pct(own[cid]),
                    ))
                    seen_subs.add(cid)
            children.sort(key=lambda r: r.own_amount, reverse=True)
            groups.append(CategoryGroup(parent=parent_row, children=children))

        # Orphan subcategories whose parent had no spend (or parent was
        # archived/missing). Surface them as their own rows so the
        # breakdown still adds up.
        for cid, c in cats.items():
            if c.parent_id is None or cid in seen_subs:
                continue
            amt = own.get(cid, 0)
            if amt <= 0:
                continue
            groups.append(CategoryGroup(
                parent=CategorySpend(
                    category=c, own_amount=amt, rolled_up_amount=amt, percent=_pct(amt),
                ),
            ))

        return CategoryBreakdown(
            month=month,
            total=total,
            groups=groups,
            uncategorised=uncategorised,
        )
