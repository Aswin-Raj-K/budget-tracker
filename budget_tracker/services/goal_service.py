from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date
from typing import Optional

from budget_tracker.core.models import Goal, GoalKind
from budget_tracker.core.repositories.goals import GoalRepository


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

    def list_with_progress(
        self, *, kind: GoalKind | None = None, today: Optional[date] = None
    ) -> list[GoalProgress]:
        today = today or date.today()
        return [self._progress(g, today) for g in self.repo.list(kind=kind)]

    def progress(self, goal_id: int, *, today: Optional[date] = None) -> GoalProgress:
        return self._progress(self.repo.get(goal_id), today or date.today())

    def contribute(self, goal_id: int, delta_minor: int) -> Goal:
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
