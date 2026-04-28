from __future__ import annotations

import sqlite3
from datetime import date

from budget_tracker.core.models import Subscription


def _row_to_sub(row: sqlite3.Row) -> Subscription:
    return Subscription(
        id=row["id"],
        name=row["name"],
        amount=row["amount"],
        cycle=row["cycle"],
        next_billing_date=date.fromisoformat(row["next_billing_date"]),
        category_id=row["category_id"],
        account_id=row["account_id"],
        active=bool(row["active"]),
    )


class SubscriptionRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def add(self, sub: Subscription) -> Subscription:
        cur = self.conn.execute(
            "INSERT INTO subscriptions("
            "  name, amount, cycle, next_billing_date, category_id, account_id, active"
            ") VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                sub.name,
                sub.amount,
                sub.cycle,
                sub.next_billing_date.isoformat(),
                sub.category_id,
                sub.account_id,
                int(sub.active),
            ),
        )
        self.conn.commit()
        return self.get(cur.lastrowid)  # type: ignore[arg-type]

    def get(self, sub_id: int) -> Subscription:
        row = self.conn.execute(
            "SELECT * FROM subscriptions WHERE id = ?", (sub_id,)
        ).fetchone()
        if not row:
            raise LookupError(f"Subscription {sub_id} not found")
        return _row_to_sub(row)

    def list(self, *, active_only: bool = False) -> list[Subscription]:
        sql = "SELECT * FROM subscriptions"
        if active_only:
            sql += " WHERE active = 1"
        sql += " ORDER BY next_billing_date"
        return [_row_to_sub(r) for r in self.conn.execute(sql).fetchall()]

    def update(self, sub: Subscription) -> Subscription:
        if sub.id is None:
            raise ValueError("Cannot update subscription without id")
        self.conn.execute(
            "UPDATE subscriptions SET name = ?, amount = ?, cycle = ?, "
            "next_billing_date = ?, category_id = ?, account_id = ?, active = ? "
            "WHERE id = ?",
            (
                sub.name,
                sub.amount,
                sub.cycle,
                sub.next_billing_date.isoformat(),
                sub.category_id,
                sub.account_id,
                int(sub.active),
                sub.id,
            ),
        )
        self.conn.commit()
        return self.get(sub.id)

    def delete(self, sub_id: int) -> None:
        self.conn.execute("DELETE FROM subscriptions WHERE id = ?", (sub_id,))
        self.conn.commit()
