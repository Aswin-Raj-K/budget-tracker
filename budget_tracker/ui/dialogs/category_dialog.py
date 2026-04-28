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

NO_PARENT = -1  # sentinel value for "top-level"


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

        # Pre-compute which categories already have children — those can't
        # become subcategories themselves (we enforce one level of nesting).
        self._has_children: set[int] = set()
        for c in self._repo.list(include_archived=True):
            if c.parent_id is not None:
                self._has_children.add(c.parent_id)

        self.setWindowTitle("Edit category" if category else "Add category")
        self.setMinimumWidth(400)
        self.setModal(True)

        self._build()
        if category is not None:
            self._prefill(category)
        else:
            self._refresh_parent_options()

        self._name.setFocus()

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
        self._name.setPlaceholderText("e.g. Groceries  ·  or  Chicken under Groceries")
        form.addRow("Name", self._name)

        self._kind = QComboBox()
        for value, label in KIND_LABELS:
            self._kind.addItem(label, value)
        self._kind.currentIndexChanged.connect(self._on_kind_changed)
        form.addRow("Kind", self._kind)

        # Parent picker (None = top-level)
        self._parent = QComboBox()
        self._parent.currentIndexChanged.connect(self._on_parent_changed)
        form.addRow("Parent", self._parent)

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

    # ---------- parent / kind interaction ----------

    def _refresh_parent_options(self) -> None:
        """Repopulate the Parent combo for the currently selected kind."""
        previous = self._parent.currentData() if self._parent.count() else NO_PARENT

        self._parent.blockSignals(True)
        self._parent.clear()
        self._parent.addItem("None  ·  top-level", NO_PARENT)

        kind = self._kind.currentData()
        editing_id = self._editing.id if self._editing else None
        for cand in self._repo.list_top_level(kind=kind):
            # Cannot pick self as parent.
            if cand.id == editing_id:
                continue
            self._parent.addItem(cand.name, cand.id)

        # Restore previous selection if still valid; otherwise fall back to None.
        idx = self._parent.findData(previous) if previous is not None else 0
        self._parent.setCurrentIndex(idx if idx >= 0 else 0)
        self._parent.blockSignals(False)

        # If we're editing a category that itself has children, it can't be
        # demoted to a subcategory — lock parent to "None".
        if editing_id is not None and editing_id in self._has_children:
            self._parent.setCurrentIndex(0)
            self._parent.setEnabled(False)
            self._parent.setToolTip(
                "This category has subcategories of its own, so it must stay top-level."
            )
        else:
            self._parent.setEnabled(True)
            self._parent.setToolTip("")

    def _on_kind_changed(self) -> None:
        # If the user flips kind manually, refresh the eligible parents.
        # When a parent is selected, kind is locked, so this only fires for
        # top-level categories.
        if self._parent.isEnabled():
            self._refresh_parent_options()

    def _on_parent_changed(self) -> None:
        parent_id = self._parent.currentData()
        if parent_id is None or parent_id == NO_PARENT:
            self._kind.setEnabled(True)
            self._kind.setToolTip("")
            return
        # Force kind to match the parent's kind and disable the kind combo.
        try:
            parent = self._repo.get(parent_id)
        except LookupError:
            return
        idx = next(i for i, (v, _) in enumerate(KIND_LABELS) if v == parent.kind)
        self._kind.blockSignals(True)
        self._kind.setCurrentIndex(idx)
        self._kind.blockSignals(False)
        self._kind.setEnabled(False)
        self._kind.setToolTip("Subcategories inherit kind from their parent.")

    def _prefill(self, c: Category) -> None:
        self._name.setText(c.name)
        idx = next(i for i, (v, _) in enumerate(KIND_LABELS) if v == c.kind)
        self._kind.setCurrentIndex(idx)
        self._icon.setText(c.icon or "•")
        self._color.set_color(c.color or "#7C5CFF")
        # Populate the parent options for the selected kind, then select.
        self._refresh_parent_options()
        if c.parent_id is not None:
            i = self._parent.findData(c.parent_id)
            if i >= 0:
                self._parent.setCurrentIndex(i)
                self._on_parent_changed()

    def _on_save(self) -> None:
        name = self._name.text().strip()
        if not name:
            QMessageBox.warning(self, "Cannot save", "Category needs a name.")
            return

        parent_data = self._parent.currentData()
        parent_id = None if parent_data == NO_PARENT else parent_data

        kind: CategoryKind = self._kind.currentData()
        if parent_id is not None:
            # Belt + suspenders: enforce parent's kind even if combo was disabled.
            try:
                parent = self._repo.get(parent_id)
                kind = parent.kind
            except LookupError:
                parent_id = None

        c = Category(
            id=self._editing.id if self._editing else None,
            name=name,
            kind=kind,
            color=self._color.color(),
            icon=(self._icon.text() or "•").strip() or "•",
            parent_id=parent_id,
            archived=self._editing.archived if self._editing else False,
        )
        self._saved = self._repo.update(c) if self._editing else self._repo.add(c)
        self.accept()

    def saved(self) -> Optional[Category]:
        return self._saved
