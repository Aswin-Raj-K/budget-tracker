from __future__ import annotations

import sqlite3
from typing import Optional

from budget_tracker.core.models import Budget


def _row_to_budget(row: sqlite3.Row) -> Budget:
    return Budget(
        id=row["id"],
        category_id=row["category_id"],
        amount=row["amount"],
        effective_from=row["effective_from"],
    )


class BudgetRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def upsert(self, budget: Budget) -> Budget:
        """Insert or update a budget for (category_id, effective_from)."""
        self.conn.execute(
            "INSERT INTO budgets(category_id, amount, effective_from) "
            "VALUES (?, ?, ?) "
            "ON CONFLICT(category_id, effective_from) DO UPDATE SET amount = excluded.amount",
            (budget.category_id, budget.amount, budget.effective_from),
        )
        self.conn.commit()
        row = self.conn.execute(
            "SELECT * FROM budgets WHERE category_id = ? AND effective_from = ?",
            (budget.category_id, budget.effective_from),
        ).fetchone()
        return _row_to_budget(row)

    def get(self, budget_id: int) -> Budget:
        row = self.conn.execute(
            "SELECT * FROM budgets WHERE id = ?", (budget_id,)
        ).fetchone()
        if not row:
            raise LookupError(f"Budget {budget_id} not found")
        return _row_to_budget(row)

    def for_month(self, month: str) -> list[Budget]:
        """Get all budgets effective for the given YYYY-MM month — i.e. the
        latest budget per category whose effective_from <= month."""
        rows = self.conn.execute(
            """
            SELECT b1.* FROM budgets b1
            JOIN (
                SELECT category_id, MAX(effective_from) AS ef
                FROM budgets
                WHERE effective_from <= ?
                GROUP BY category_id
            ) b2
              ON b1.category_id = b2.category_id
             AND b1.effective_from = b2.ef
            ORDER BY b1.category_id
            """,
            (month,),
        ).fetchall()
        return [_row_to_budget(r) for r in rows]

    def for_category(self, category_id: int) -> list[Budget]:
        rows = self.conn.execute(
            "SELECT * FROM budgets WHERE category_id = ? ORDER BY effective_from",
            (category_id,),
        ).fetchall()
        return [_row_to_budget(r) for r in rows]

    def latest_for_category(self, category_id: int, month: str) -> Optional[Budget]:
        row = self.conn.execute(
            "SELECT * FROM budgets WHERE category_id = ? AND effective_from <= ? "
            "ORDER BY effective_from DESC LIMIT 1",
            (category_id, month),
        ).fetchone()
        return _row_to_budget(row) if row else None

    def delete(self, budget_id: int) -> None:
        self.conn.execute("DELETE FROM budgets WHERE id = ?", (budget_id,))
        self.conn.commit()
