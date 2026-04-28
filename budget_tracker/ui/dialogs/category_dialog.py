from __future__ import annotations

import sqlite3
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from budget_tracker.core.models import Category, CategoryKind
from budget_tracker.core.repositories.categories import CategoryRepository

KIND_LABELS: list[tuple[CategoryKind, str]] = [
    ("expense", "Expense"),
    ("income",  "Income"),
]


class _ColorButton(QPushButton):
    def __init__(self, initial: str = "#7C5CFF", parent=None):
        super().__init__(parent)
        self.setFixedSize(40, 32)
        self.setProperty("class", "secondary")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._color = initial
        self.clicked.connect(self._pick)
        self._refresh()

    def color(self) -> str:
        return self._color

    def set_color(self, hex_str: str) -> None:
        self._color = hex_str
        self._refresh()

    def _pick(self) -> None:
        c = QColorDialog.getColor(QColor(self._color), self.parent(), "Pick a colour")
        if c.isValid():
            self.set_color(c.name())

    def _refresh(self) -> None:
        # Inline style avoids fighting the global QSS for this single swatch.
        self.setStyleSheet(
            f"background-color: {self._color}; border: 1px solid rgba(0,0,0,40); "
            "border-radius: 6px;"
        )


class CategoryDialog(QDialog):
    def __init__(
        self,
        conn: sqlite3.Connection,
        category: Optional[Category] = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._editing = category
        self._repo = CategoryRepository(conn)
        self._saved: Optional[Category] = None

        self.setWindowTitle("Edit category" if category else "Add category")
        self.setMinimumWidth(380)
        self.setModal(True)

        self._build()
        if category is not None:
            self._prefill(category)

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 22, 24, 20)
        outer.setSpacing(14)

        title = QLabel("Edit category" if self._editing else "Add category")
        title.setProperty("class", "h2")
        outer.addWidget(title)

        form = QFormLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self._name = QLineEdit()
        self._name.setPlaceholderText("e.g. Groceries")
        form.addRow("Name", self._name)

        self._kind = QComboBox()
        for value, label in KIND_LABELS:
            self._kind.addItem(label, value)
        form.addRow("Kind", self._kind)

        self._icon = QLineEdit()
        self._icon.setMaxLength(2)
        self._icon.setPlaceholderText("emoji or single char")
        self._icon.setText("•")
        form.addRow("Icon", self._icon)

        self._color = _ColorButton()
        form.addRow("Colour", self._color)

        outer.addLayout(form)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.setProperty("class", "secondary")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Save")
        save.setProperty("class", "primary")
        save.setDefault(True)
        save.clicked.connect(self._on_save)
        button_row.addWidget(cancel)
        button_row.addWidget(save)
        outer.addLayout(button_row)

    def _prefill(self, c: Category) -> None:
        self._name.setText(c.name)
        idx = next(i for i, (v, _) in enumerate(KIND_LABELS) if v == c.kind)
        self._kind.setCurrentIndex(idx)
        self._icon.setText(c.icon or "•")
        self._color.set_color(c.color or "#7C5CFF")

    def _on_save(self) -> None:
        name = self._name.text().strip()
        if not name:
            QMessageBox.warning(self, "Cannot save", "Category needs a name.")
            return
        c = Category(
            id=self._editing.id if self._editing else None,
            name=name,
            kind=self._kind.currentData(),
            color=self._color.color(),
            icon=(self._icon.text() or "•").strip() or "•",
            archived=self._editing.archived if self._editing else False,
        )
        self._saved = self._repo.update(c) if self._editing else self._repo.add(c)
        self.accept()

    def saved(self) -> Optional[Category]:
        return self._saved
