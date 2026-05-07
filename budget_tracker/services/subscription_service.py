from __future__ import annotations

import sqlite3
from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta

from budget_tracker.core.models import Subscription, Transaction
from budget_tracker.core.repositories.subscriptions import SubscriptionRepository
from budget_tracker.core.repositories.transactions import TransactionRepository


def monthly_equivalent(sub: Subscription) -> int:
    """Convert any subscription cycle to its equivalent monthly cost (minor units).

    Uses simple ratios: weekly→/12 (52/12), yearly→/12. Result is rounded
    to the nearest minor unit using banker's-style truncation toward zero.
    """
    if sub.cycle == "monthly":
        return sub.amount
    if sub.cycle == "yearly":
        return sub.amount // 12
    if sub.cycle == "weekly":
        return sub.amount * 52 // 12
    raise ValueError(f"Unknown cycle: {sub.cycle!r}")


def next_billing_after(current: date, cycle: str) -> date:
    """Roll a billing date forward by one cycle.

    Handles month-end clamping correctly: Jan 31 + 1 month → Feb 28/29,
    not the next valid 31st. Yearly is just 12 monthly steps so leap-day
    subscriptions (Feb 29 → Feb 28) are clamped the same way.
    """
    if cycle == "weekly":
        return current + timedelta(days=7)
    if cycle == "monthly":
        return _add_months(current, 1)
    if cycle == "yearly":
        return _add_months(current, 12)
    raise ValueError(f"Unknown cycle: {cycle!r}")


def _add_months(d: date, months: int) -> date:
    new_idx = (d.month - 1) + months          # 0-indexed month after shift
    new_year = d.year + new_idx // 12
    new_month = (new_idx % 12) + 1
    last_day = monthrange(new_year, new_month)[1]
    return date(new_year, new_month, min(d.day, last_day))


@dataclass
class SubscriptionSummary:
    items: list[Subscription]
    total_monthly: int                   # minor units
    monthly_per_item: dict[int, int]     # subscription.id → monthly equivalent


class SubscriptionService:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.repo = SubscriptionRepository(conn)
        self.tx_repo = TransactionRepository(conn)

    def summary(self, *, active_only: bool = True) -> SubscriptionSummary:
        items = self.repo.list(active_only=active_only)
        per_item = {s.id: monthly_equivalent(s) for s in items if s.id is not None}
        total = sum(per_item.values())
        return SubscriptionSummary(items=items, total_monthly=total, monthly_per_item=per_item)

    def mark_as_paid(self, sub_id: int) -> Transaction:
        """Post a real expense transaction for this billing cycle and roll
        the subscription's `next_billing_date` forward by one cycle.

        Returns the created Transaction so the caller can confirm it.
        Raises ValueError if the subscription has no `account_id` set —
        the transaction needs an account to debit.
        """
        sub = self.repo.get(sub_id)
        if sub.account_id is None:
            raise ValueError(
                "This subscription has no account set. Edit it and pick "
                "the account it's billed to before marking it paid."
            )

        tx = self.tx_repo.add(Transaction(
            id=None,
            occurred_on=sub.next_billing_date,
            kind="expense",
            amount=sub.amount,
            account_id=sub.account_id,
            transfer_account_id=None,
            category_id=sub.category_id,
            note=sub.name,
        ))

        sub.next_billing_date = next_billing_after(sub.next_billing_date, sub.cycle)
        self.repo.update(sub)
        return tx
