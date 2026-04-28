from __future__ import annotations

import sqlite3

from budget_tracker.core.models import Category, CategoryKind


def _row_to_category(row: sqlite3.Row) -> Category:
    return Category(
        id=row["id"],
        name=row["name"],
        kind=row["kind"],
        color=row["color"],
        icon=row["icon"],
        archived=bool(row["archived"]),
    )


class CategoryRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def add(self, category: Category) -> Category:
        cur = self.conn.execute(
            "INSERT INTO categories(name, kind, color, icon, archived) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                category.name,
                category.kind,
                category.color,
                category.icon,
                int(category.archived),
            ),
        )
        self.conn.commit()
        return self.get(cur.lastrowid)  # type: ignore[arg-type]

    def get(self, category_id: int) -> Category:
        row = self.conn.execute(
            "SELECT * FROM categories WHERE id = ?", (category_id,)
        ).fetchone()
        if not row:
            raise LookupError(f"Category {category_id} not found")
        return _row_to_category(row)

    def list(
        self,
        *,
        kind: CategoryKind | None = None,
        include_archived: bool = False,
    ) -> list[Category]:
        clauses, params = [], []
        if not include_archived:
            clauses.append("archived = 0")
        if kind is not None:
            clauses.append("kind = ?")
            params.append(kind)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"SELECT * FROM categories{where} ORDER BY name"
        return [_row_to_category(r) for r in self.conn.execute(sql, params).fetchall()]

    def update(self, category: Category) -> Category:
        if category.id is None:
            raise ValueError("Cannot update category without id")
        self.conn.execute(
            "UPDATE categories SET name = ?, kind = ?, color = ?, icon = ?, archived = ? "
            "WHERE id = ?",
            (
                category.name,
                category.kind,
                category.color,
                category.icon,
                int(category.archived),
                category.id,
            ),
        )
        self.conn.commit()
        return self.get(category.id)

    def delete(self, category_id: int) -> None:
        self.conn.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        self.conn.commit()
