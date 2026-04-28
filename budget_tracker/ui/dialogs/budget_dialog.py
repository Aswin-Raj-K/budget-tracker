from __future__ import annotations

import sqlite3
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from budget_tracker.core import money
from budget_tracker.core.models import Budget
from budget_tracker.core.repositories.budgets import BudgetRepository
from budget_tracker.core.repositories.categories import CategoryRepository


class BudgetDialog(QDialog):
    """Add or edit a monthly budget for a category.

    - Add mode: pass `month` (YYYY-MM); category combo lists expense
      categories that don't yet have a budget for that month.
    - Edit mode: pass `budget` plus its `category_name`; the category
      combo is locked to that single entry.
    """

    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        budget: Optional[Budget] = None,
        month: Optional[str] = None,
        category_name: Optional[str] = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        if budget is None and month is None:
            raise ValueError("Add mode requires a month")

        self.conn = conn
        self._editing = budget
        self._month = budget.effective_from if budget else month  # type: ignore[union-attr]

        self._budgets = BudgetRepository(conn)
        self._categories = CategoryRepository(conn)
        self._saved: Optional[Budget] = None

        self.setWindowTitle("Edit budget" if budget else "Add budget")
        self.setMinimumWidth(380)
        self.setModal(True)

        self._build()
        self._populate_categories(locked_name=category_name)
        if budget is not None:
            self._amount.setValue(float(money.to_major(budget.amount)))

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 22, 24, 20)
        outer.setSpacing(14)

        title = QLabel("Edit budget" if self._editing else "Add budget")
        title.setProperty("class", "h2")
        outer.addWidget(title)

        sub = QLabel(f"Effective from {self._month}")
        sub.setProperty("class", "subtle")
        outer.addWidget(sub)

        form = QFormLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self._category = QComboBox()
        form.addRow("Category", self._category)

        self._amount = QDoubleSpinBox()
        self._amount.setDecimals(2)
        self._amount.setRange(0.0, 99_99_99_999.99)
        self._amount.setSingleStep(500.0)
        self._amount.setPrefix(f"{money.active().symbol} ")
        self._amount.setAlignment(Qt.AlignmentFlag.AlignRight)
        form.addRow("Monthly limit", self._amount)

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

    def _populate_categories(self, *, locked_name: Optional[str] = None) -> None:
        self._category.clear()
        if self._editing is not None:
            cat = self._categories.get(self._editing.category_id)
            self._category.addItem(cat.name, cat.id)
            self._category.setEnabled(False)
            return

        used = {b.category_id for b in self._budgets.for_month(self._month)}  # type: ignore[arg-type]
        for c in self._categories.list(kind="expense"):
            if c.id in used:
                continue
            self._category.addItem(c.name, c.id)

        if self._category.count() == 0:
            QMessageBox.information(
                self,
                "All expense categories are budgeted",
                f"Every expense category already has a budget for {self._month}.\n"
                "Edit an existing one or add a new category in Settings.",
            )
            self.reject()

    def _on_save(self) -> None:
        category_id = self._category.currentData()
        if not category_id:
            QMessageBox.warning(self, "Cannot save", "Select a category.")
            return
        amount_minor = money.to_minor(self._amount.value())
        if amount_minor <= 0:
            QMessageBox.warning(self, "Cannot save", "Monthly limit must be greater than zero.")
            return

        budget = Budget(
            id=self._editing.id if self._editing else None,
            category_id=category_id,
            amount=amount_minor,
            effective_from=self._month,  # type: ignore[arg-type]
        )
        self._saved = self._budgets.upsert(budget)
        self.accept()

    def saved(self) -> Optional[Budget]:
        return self._saved
