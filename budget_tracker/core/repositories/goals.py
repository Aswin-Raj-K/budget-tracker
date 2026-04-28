from __future__ import annotations

import sqlite3
from datetime import date

from budget_tracker.core.models import Goal, GoalKind


def _row_to_goal(row: sqlite3.Row) -> Goal:
    deadline = row["deadline"]
    return Goal(
        id=row["id"],
        name=row["name"],
        kind=row["kind"],
        target_amount=row["target_amount"],
        current_amount=row["current_amount"],
        deadline=date.fromisoformat(deadline) if deadline else None,
        archived=bool(row["archived"]),
        created_at=row["created_at"],
    )


class GoalRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def add(self, goal: Goal) -> Goal:
        cur = self.conn.execute(
            "INSERT INTO goals(name, kind, target_amount, current_amount, deadline, archived) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                goal.name,
                goal.kind,
                goal.target_amount,
                goal.current_amount,
                goal.deadline.isoformat() if goal.deadline else None,
                int(goal.archived),
            ),
        )
        self.conn.commit()
        return self.get(cur.lastrowid)  # type: ignore[arg-type]

    def get(self, goal_id: int) -> Goal:
        row = self.conn.execute(
            "SELECT * FROM goals WHERE id = ?", (goal_id,)
        ).fetchone()
        if not row:
            raise LookupError(f"Goal {goal_id} not found")
        return _row_to_goal(row)

    def list(
        self,
        *,
        kind: GoalKind | None = None,
        include_archived: bool = False,
    ) -> list[Goal]:
        clauses, params = [], []
        if not include_archived:
            clauses.append("archived = 0")
        if kind is not None:
            clauses.append("kind = ?")
            params.append(kind)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"SELECT * FROM goals{where} ORDER BY created_at DESC"
        return [_row_to_goal(r) for r in self.conn.execute(sql, params).fetchall()]

    def update(self, goal: Goal) -> Goal:
        if goal.id is None:
            raise ValueError("Cannot update goal without id")
        self.conn.execute(
            "UPDATE goals SET name = ?, kind = ?, target_amount = ?, current_amount = ?, "
            "deadline = ?, archived = ? WHERE id = ?",
            (
                goal.name,
                goal.kind,
                goal.target_amount,
                goal.current_amount,
                goal.deadline.isoformat() if goal.deadline else None,
                int(goal.archived),
                goal.id,
            ),
        )
        self.conn.commit()
        return self.get(goal.id)

    def contribute(self, goal_id: int, delta_minor: int) -> Goal:
        """Add (or subtract, with negative delta) to current_amount. Clamped at 0."""
        goal = self.get(goal_id)
        new_amount = max(0, goal.current_amount + delta_minor)
        self.conn.execute(
            "UPDATE goals SET current_amount = ? WHERE id = ?",
            (new_amount, goal_id),
        )
        self.conn.commit()
        return self.get(goal_id)

    def delete(self, goal_id: int) -> None:
        self.conn.execute("DELETE FROM goals WHERE id = ?", (goal_id,))
        self.conn.commit()
