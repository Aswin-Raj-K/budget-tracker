from __future__ import annotations

import sqlite3
from typing import Optional

from budget_tracker.core.models import Category, CategoryKind


def _row_to_category(row: sqlite3.Row) -> Category:
    return Category(
        id=row["id"],
        name=row["name"],
        kind=row["kind"],
        color=row["color"],
        icon=row["icon"],
        parent_id=row["parent_id"] if "parent_id" in row.keys() else None,
        archived=bool(row["archived"]),
    )


class CategoryRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def add(self, category: Category) -> Category:
        cur = self.conn.execute(
            "INSERT INTO categories(name, kind, color, icon, parent_id, archived) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                category.name,
                category.kind,
                category.color,
                category.icon,
                category.parent_id,
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

    def list_top_level(
        self,
        *,
        kind: CategoryKind | None = None,
        include_archived: bool = False,
    ) -> list[Category]:
        clauses = ["parent_id IS NULL"]
        params: list = []
        if not include_archived:
            clauses.append("archived = 0")
        if kind is not None:
            clauses.append("kind = ?")
            params.append(kind)
        sql = f"SELECT * FROM categories WHERE {' AND '.join(clauses)} ORDER BY name"
        return [_row_to_category(r) for r in self.conn.execute(sql, params).fetchall()]

    def children_of(
        self,
        parent_id: int,
        *,
        include_archived: bool = False,
    ) -> list[Category]:
        clauses = ["parent_id = ?"]
        params: list = [parent_id]
        if not include_archived:
            clauses.append("archived = 0")
        sql = f"SELECT * FROM categories WHERE {' AND '.join(clauses)} ORDER BY name"
        return [_row_to_category(r) for r in self.conn.execute(sql, params).fetchall()]

    def top_level_id_for(self, category_id: int) -> int:
        """Return the top-level ancestor id. With one-level nesting this is
        either the category itself (if parent_id IS NULL) or its parent."""
        row = self.conn.execute(
            "SELECT id, parent_id FROM categories WHERE id = ?", (category_id,)
        ).fetchone()
        if not row:
            raise LookupError(f"Category {category_id} not found")
        return row["parent_id"] if row["parent_id"] is not None else row["id"]

    def update(self, category: Category) -> Category:
        if category.id is None:
            raise ValueError("Cannot update category without id")
        self.conn.execute(
            "UPDATE categories SET name = ?, kind = ?, color = ?, icon = ?, "
            "parent_id = ?, archived = ? WHERE id = ?",
            (
                category.name,
                category.kind,
                category.color,
                category.icon,
                category.parent_id,
                int(category.archived),
                category.id,
            ),
        )
        self.conn.commit()
        return self.get(category.id)

    def delete(self, category_id: int) -> None:
        # Promote any children to top-level so they don't disappear with their
        # parent. This is the SET-NULL behaviour we'd otherwise rely on the FK
        # for, but enforcing it explicitly keeps it robust across SQLite
        # versions and across columns added via ALTER TABLE.
        self.conn.execute(
            "UPDATE categories SET parent_id = NULL WHERE parent_id = ?",
            (category_id,),
        )
        self.conn.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        self.conn.commit()
