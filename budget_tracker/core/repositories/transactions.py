from __future__ import annotations

import sqlite3
from datetime import date
from typing import Optional

from budget_tracker.core.models import Transaction, TxKind


def _row_to_tx(row: sqlite3.Row) -> Transaction:
    keys = row.keys()
    return Transaction(
        id=row["id"],
        occurred_on=date.fromisoformat(row["occurred_on"]),
        kind=row["kind"],
        amount=row["amount"],
        account_id=row["account_id"],
        transfer_account_id=row["transfer_account_id"],
        category_id=row["category_id"],
        note=row["note"],
        # goal_id was added in migration 003 — guard so older snapshots
        # still parse cleanly during tests.
        goal_id=row["goal_id"] if "goal_id" in keys else None,
        created_at=row["created_at"],
    )


class TransactionRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def add(self, tx: Transaction) -> Transaction:
        cur = self.conn.execute(
            "INSERT INTO transactions("
            "  occurred_on, kind, amount, account_id, transfer_account_id, "
            "  category_id, note, goal_id"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                tx.occurred_on.isoformat(),
                tx.kind,
                tx.amount,
                tx.account_id,
                tx.transfer_account_id,
                tx.category_id,
                tx.note,
                tx.goal_id,
            ),
        )
        self.conn.commit()
        return self.get(cur.lastrowid)  # type: ignore[arg-type]

    def get(self, tx_id: int) -> Transaction:
        row = self.conn.execute(
            "SELECT * FROM transactions WHERE id = ?", (tx_id,)
        ).fetchone()
        if not row:
            raise LookupError(f"Transaction {tx_id} not found")
        return _row_to_tx(row)

    def list(
        self,
        *,
        start: Optional[date] = None,
        end: Optional[date] = None,
        account_id: Optional[int] = None,
        category_id: Optional[int] = None,
        kind: Optional[TxKind] = None,
        text: Optional[str] = None,
        goal_id: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> list[Transaction]:
        clauses, params = [], []
        if start is not None:
            clauses.append("occurred_on >= ?")
            params.append(start.isoformat())
        if end is not None:
            clauses.append("occurred_on <= ?")
            params.append(end.isoformat())
        if account_id is not None:
            clauses.append("(account_id = ? OR transfer_account_id = ?)")
            params.extend([account_id, account_id])
        if category_id is not None:
            clauses.append("category_id = ?")
            params.append(category_id)
        if kind is not None:
            clauses.append("kind = ?")
            params.append(kind)
        if text:
            clauses.append("note LIKE ?")
            params.append(f"%{text}%")
        if goal_id is not None:
            clauses.append("goal_id = ?")
            params.append(goal_id)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"SELECT * FROM transactions{where} ORDER BY occurred_on DESC, id DESC"
        if limit is not None:
            sql += f" LIMIT {int(limit)}"
        return [_row_to_tx(r) for r in self.conn.execute(sql, params).fetchall()]

    def update(self, tx: Transaction) -> Transaction:
        if tx.id is None:
            raise ValueError("Cannot update transaction without id")
        self.conn.execute(
            "UPDATE transactions SET "
            "  occurred_on = ?, kind = ?, amount = ?, account_id = ?, "
            "  transfer_account_id = ?, category_id = ?, note = ?, goal_id = ? "
            "WHERE id = ?",
            (
                tx.occurred_on.isoformat(),
                tx.kind,
                tx.amount,
                tx.account_id,
                tx.transfer_account_id,
                tx.category_id,
                tx.note,
                tx.goal_id,
                tx.id,
            ),
        )
        self.conn.commit()
        return self.get(tx.id)

    def delete(self, tx_id: int) -> None:
        self.conn.execute("DELETE FROM transactions WHERE id = ?", (tx_id,))
        self.conn.commit()

    # --- Aggregations used by services ---

    def sum_by_kind(
        self, *, kind: TxKind, start: date, end: date
    ) -> int:
        row = self.conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total FROM transactions "
            "WHERE kind = ? AND occurred_on >= ? AND occurred_on <= ?",
            (kind, start.isoformat(), end.isoformat()),
        ).fetchone()
        return int(row["total"])

    def sum_by_category(
        self, *, start: date, end: date, kind: TxKind = "expense"
    ) -> dict[Optional[int], int]:
        rows = self.conn.execute(
            "SELECT category_id, COALESCE(SUM(amount), 0) AS total "
            "FROM transactions "
            "WHERE kind = ? AND occurred_on >= ? AND occurred_on <= ? "
            "GROUP BY category_id",
            (kind, start.isoformat(), end.isoformat()),
        ).fetchall()
        return {r["category_id"]: int(r["total"]) for r in rows}
