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
        transfer_from_id: Optional[int] = None,
        transfer_to_id: Optional[int] = None,
        occurred_on: Optional[date] = None,
    ) -> Goal:
        """Bump the goal's current_amount by ``delta_minor`` (signed —
        positive to contribute / pay down, negative to withdraw).

        If both ``transfer_from_id`` and ``transfer_to_id`` are set, also
        post a real ``transfer`` transaction for ``abs(delta_minor)`` so
        the move shows up in the user's account balances and KPIs. The
        transfer's ``occurred_on`` defaults to today.
        """
        if (transfer_from_id is None) != (transfer_to_id is None):
            raise ValueError("Provide both source and destination accounts, or neither.")
        if transfer_from_id is not None and transfer_from_id == transfer_to_id:
            raise ValueError("Source and destination accounts must differ.")

        if transfer_from_id is not None and delta_minor != 0:
            goal = self.repo.get(goal_id)
            self.tx_repo.add(Transaction(
                id=None,
                occurred_on=occurred_on or date.today(),
                kind="transfer",
                amount=abs(delta_minor),
                account_id=transfer_from_id,
                transfer_account_id=transfer_to_id,
                category_id=None,
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
