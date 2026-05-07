from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date
from typing import Optional

from budget_tracker.core.models import Goal, GoalKind, Transaction
from budget_tracker.core.repositories.goals import GoalRepository
from budget_tracker.core.repositories.transactions import TransactionRepository


@dataclass
class GoalProgress:
    goal: Goal
    percent: float                      # 0..100
    remaining: int                      # minor units; >=0
    days_remaining: Optional[int]       # None if no deadline; negative if past
    is_complete: bool


class GoalService:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.repo = GoalRepository(conn)
        self.tx_repo = TransactionRepository(conn)

    def list_with_progress(
        self, *, kind: GoalKind | None = None, today: Optional[date] = None
    ) -> list[GoalProgress]:
        today = today or date.today()
        return [self._progress(g, today) for g in self.repo.list(kind=kind)]

    def progress(self, goal_id: int, *, today: Optional[date] = None) -> GoalProgress:
        return self._progress(self.repo.get(goal_id), today or date.today())

    def contribute(
        self,
        goal_id: int,
        delta_minor: int,
        *,
        from_account_id: Optional[int] = None,
        to_account_id: Optional[int] = None,
        category_id: Optional[int] = None,
        occurred_on: Optional[date] = None,
        # Back-compat aliases for an earlier signature; both names map
        # to from_account_id / to_account_id and we accept either.
        transfer_from_id: Optional[int] = None,
        transfer_to_id: Optional[int] = None,
    ) -> Goal:
        """Bump the goal's current_amount by ``delta_minor`` (signed —
        positive to contribute / pay down, negative to withdraw).

        Optionally also posts a real transaction so the move shows up
        in account balances and Home KPIs:

        - ``from_account_id`` + ``to_account_id`` → ``transfer``
          (e.g. checking → savings, or checking → tracked credit card).
        - ``from_account_id`` only (no ``to_account_id``) → ``expense``
          (debt is paid to a payee outside the app, like a mortgage
          or student-loan servicer). ``category_id`` is optional.
        - Neither → no transaction, only the goal counter moves.

        The new transaction's ``occurred_on`` defaults to today.
        """
        # Coalesce the back-compat aliases.
        if from_account_id is None and transfer_from_id is not None:
            from_account_id = transfer_from_id
        if to_account_id is None and transfer_to_id is not None:
            to_account_id = transfer_to_id

        if from_account_id is None and to_account_id is not None:
            raise ValueError("Provide a source account when a destination is set.")
        if (
            from_account_id is not None
            and to_account_id is not None
            and from_account_id == to_account_id
        ):
            raise ValueError("Source and destination accounts must differ.")

        if from_account_id is not None and delta_minor != 0:
            goal = self.repo.get(goal_id)
            kind = "transfer" if to_account_id is not None else "expense"
            self.tx_repo.add(Transaction(
                id=None,
                occurred_on=occurred_on or date.today(),
                kind=kind,
                amount=abs(delta_minor),
                account_id=from_account_id,
                transfer_account_id=to_account_id,            # None for expense
                category_id=category_id if kind == "expense" else None,
                note=goal.name,
                goal_id=goal_id,
            ))
        return self.repo.contribute(goal_id, delta_minor)

    def _progress(self, goal: Goal, today: date) -> GoalProgress:
        target = max(goal.target_amount, 1)
        percent = min(100.0, max(0.0, goal.current_amount / target * 100.0))
        remaining = max(0, goal.target_amount - goal.current_amount)
        days_remaining = (goal.deadline - today).days if goal.deadline else None
        return GoalProgress(
            goal=goal,
            percent=percent,
            remaining=remaining,
            days_remaining=days_remaining,
            is_complete=goal.current_amount >= goal.target_amount,
        )
