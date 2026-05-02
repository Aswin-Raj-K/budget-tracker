from __future__ import annotations

import sqlite3

from budget_tracker.core.repositories.accounts import AccountRepository


class AccountService:
    """Per-account running balance.

    balance(account) = opening_balance
                     + Σ amount where kind='income'   AND account_id   = account
                     - Σ amount where kind='expense'  AND account_id   = account
                     - Σ amount where kind='transfer' AND account_id   = account   (outgoing)
                     + Σ amount where kind='transfer' AND transfer_account_id = account  (incoming)
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.repo = AccountRepository(conn)

    def balances(self) -> dict[int, int]:
        """Running balance for every account (active + archived), keyed by id."""
        balances: dict[int, int] = {
            row["id"]: row["opening_balance"]
            for row in self.conn.execute(
                "SELECT id, opening_balance FROM accounts"
            )
        }

        # Income (+) / expense (-) on the source account.
        for row in self.conn.execute(
            "SELECT account_id, kind, COALESCE(SUM(amount), 0) AS total "
            "FROM transactions "
            "WHERE kind IN ('income', 'expense') "
            "GROUP BY account_id, kind"
        ):
            acc_id = row["account_id"]
            if acc_id is None:
                continue
            sign = 1 if row["kind"] == "income" else -1
            balances[acc_id] = balances.get(acc_id, 0) + sign * row["total"]

        # Transfers leave source (-) and arrive at destination (+).
        for row in self.conn.execute(
            "SELECT account_id, transfer_account_id, COALESCE(SUM(amount), 0) AS total "
            "FROM transactions "
            "WHERE kind = 'transfer' "
            "GROUP BY account_id, transfer_account_id"
        ):
            src = row["account_id"]
            dst = row["transfer_account_id"]
            total = row["total"]
            if src is not None:
                balances[src] = balances.get(src, 0) - total
            if dst is not None:
                balances[dst] = balances.get(dst, 0) + total

        return balances

    def balance_for(self, account_id: int) -> int:
        return self.balances().get(account_id, 0)
