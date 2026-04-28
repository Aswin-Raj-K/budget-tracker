from __future__ import annotations

import sqlite3
from typing import Optional

from PySide6.QtWidgets import QWidget


class BaseView(QWidget):
    """Common base for all top-level views.

    Subclasses get a SQLite connection and may override:
      - `title`: shown in the topbar.
      - `primary_action_label`: text for the topbar "+" button (None hides).
      - `on_primary_action()`: invoked when the button is clicked.
      - `refresh()`: called when the view becomes visible / data changes.
    """

    title: str = "Untitled"
    primary_action_label: Optional[str] = None

    def __init__(self, conn: sqlite3.Connection, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.conn = conn

    def on_primary_action(self) -> None:
        pass

    def refresh(self) -> None:
        pass
