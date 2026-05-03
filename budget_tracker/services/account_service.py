from __future__ import annotations

import sqlite3

from budget_tracker.core.repositories.accounts import AccountRepository


class AccountService:
    """Per-account running balance.

    Asset accounts (checking / savings / cash / wallet):
        balance = opening_balance
                + Σ income on account
                - Σ expense on account
                - Σ transfer out (account is the source)
                + Σ transfer in  (account is the destination)

    Credit accounts (liabilities) flip every sign so the resulting
    number represents *debt owed* — positive when you owe money,
    negative if you've overpaid the card. The expected mental model:

        balance = opening_balance (existing debt)
                + Σ expense on card        (spending grows the debt)
                - Σ income on card         (refund / cashback shrinks it)
                + Σ transfer out from card (cash advance grows the debt)
                - Σ transfer in to card    (paying the card shrinks it)
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.repo = AccountRepository(conn)

    def balances(self) -> dict[int, int]:
        """Running balance for every account (active + archived), keyed by id."""
        # Capture the type alongside opening balance so we know which sign
        # convention to apply per account.
        types: dict[int, str] = {}
        balances: dict[int, int] = {}
        for row in self.conn.execute(
            "SELECT id, type, opening_balance FROM accounts"
        ):
            types[row["id"]] = row["type"]
            balances[row["id"]] = row["opening_balance"]

        def is_credit(acc_id: int) -> bool:
            return types.get(acc_id) == "credit"

        # Income / expense on the source account.
        for row in self.conn.execute(
            "SELECT account_id, kind, COALESCE(SUM(amount), 0) AS total "
            "FROM transactions "
            "WHERE kind IN ('income', 'expense') "
            "GROUP BY account_id, kind"
        ):
            acc_id = row["account_id"]
            if acc_id is None:
                continue
            credit = is_credit(acc_id)
            if row["kind"] == "income":
                sign = -1 if credit else 1     # cashback shrinks card debt
            else:                              # expense
                sign = 1 if credit else -1     # spending grows card debt
            balances[acc_id] = balances.get(acc_id, 0) + sign * row["total"]

        # Transfers — outgoing on the source, incoming on the destination.
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
                # Asset src: money leaves (-). Credit src (cash advance): debt grows (+).
                sign = 1 if is_credit(src) else -1
                balances[src] = balances.get(src, 0) + sign * total
            if dst is not None:
                # Asset dst: money arrives (+). Credit dst (paying the card): debt shrinks (-).
                sign = -1 if is_credit(dst) else 1
                balances[dst] = balances.get(dst, 0) + sign * total

        return balances

    def balance_for(self, account_id: int) -> int:
        return self.balances().get(account_id, 0)
