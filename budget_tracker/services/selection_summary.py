"""Aggregate a selection of transactions by kind.

Pure helper — no Qt, no DB. Used by the Transactions view to render the
"M selected · …" status line as the user (de)selects rows in the table.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from budget_tracker.core.models import Transaction


@dataclass(frozen=True)
class SelectionSummary:
    count: int
    income_total: int        # minor units
    expense_total: int       # minor units
    transfer_total: int      # minor units

    @property
    def net(self) -> int:
        """Income minus expense; transfers don't affect net."""
        return self.income_total - self.expense_total

    @property
    def has_income(self) -> bool:
        return self.income_total > 0

    @property
    def has_expense(self) -> bool:
        return self.expense_total > 0

    @property
    def has_transfer(self) -> bool:
        return self.transfer_total > 0


_EMPTY = SelectionSummary(count=0, income_total=0, expense_total=0, transfer_total=0)


def summarize(transactions: Iterable[Transaction]) -> SelectionSummary:
    """Roll up a collection of transactions into per-kind totals."""
    count = 0
    income = 0
    expense = 0
    transfer = 0
    for tx in transactions:
        count += 1
        if tx.kind == "income":
            income += tx.amount
        elif tx.kind == "expense":
            expense += tx.amount
        elif tx.kind == "transfer":
            transfer += tx.amount
    if count == 0:
        return _EMPTY
    return SelectionSummary(
        count=count,
        income_total=income,
        expense_total=expense,
        transfer_total=transfer,
    )
