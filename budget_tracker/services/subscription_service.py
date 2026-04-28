from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from budget_tracker.core.models import Subscription
from budget_tracker.core.repositories.subscriptions import SubscriptionRepository


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


@dataclass
class SubscriptionSummary:
    items: list[Subscription]
    total_monthly: int                   # minor units
    monthly_per_item: dict[int, int]     # subscription.id → monthly equivalent


class SubscriptionService:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.repo = SubscriptionRepository(conn)

    def summary(self, *, active_only: bool = True) -> SubscriptionSummary:
        items = self.repo.list(active_only=active_only)
        per_item = {s.id: monthly_equivalent(s) for s in items if s.id is not None}
        total = sum(per_item.values())
        return SubscriptionSummary(items=items, total_monthly=total, monthly_per_item=per_item)
