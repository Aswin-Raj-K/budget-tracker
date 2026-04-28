from __future__ import annotations

import sqlite3

from budget_tracker.core.models import Account


def _row_to_account(row: sqlite3.Row) -> Account:
    return Account(
        id=row["id"],
        name=row["name"],
        type=row["type"],
        opening_balance=row["opening_balance"],
        archived=bool(row["archived"]),
        created_at=row["created_at"],
    )


class AccountRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def add(self, account: Account) -> Account:
        cur = self.conn.execute(
            "INSERT INTO accounts(name, type, opening_balance, archived) "
            "VALUES (?, ?, ?, ?)",
            (account.name, account.type, account.opening_balance, int(account.archived)),
        )
        self.conn.commit()
        return self.get(cur.lastrowid)  # type: ignore[arg-type]

    def get(self, account_id: int) -> Account:
        row = self.conn.execute(
            "SELECT * FROM accounts WHERE id = ?", (account_id,)
        ).fetchone()
        if not row:
            raise LookupError(f"Account {account_id} not found")
        return _row_to_account(row)

    def list(self, *, include_archived: bool = False) -> list[Account]:
        sql = "SELECT * FROM accounts"
        if not include_archived:
            sql += " WHERE archived = 0"
        sql += " ORDER BY name"
        return [_row_to_account(r) for r in self.conn.execute(sql).fetchall()]

    def update(self, account: Account) -> Account:
        if account.id is None:
            raise ValueError("Cannot update account without id")
        self.conn.execute(
            "UPDATE accounts SET name = ?, type = ?, opening_balance = ?, archived = ? "
            "WHERE id = ?",
            (
                account.name,
                account.type,
                account.opening_balance,
                int(account.archived),
                account.id,
            ),
        )
        self.conn.commit()
        return self.get(account.id)

    def delete(self, account_id: int) -> None:
        self.conn.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
        self.conn.commit()
