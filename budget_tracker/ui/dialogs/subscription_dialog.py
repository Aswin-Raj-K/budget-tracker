from __future__ import annotations

import sqlite3
from datetime import date
from typing import Optional

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from budget_tracker.core import money
from budget_tracker.core.models import SubCycle, Subscription
from budget_tracker.core.repositories.accounts import AccountRepository
from budget_tracker.core.repositories.categories import CategoryRepository
from budget_tracker.core.repositories.subscriptions import SubscriptionRepository

CYCLE_LABELS: list[tuple[SubCycle, str]] = [
    ("monthly", "Monthly"),
    ("yearly",  "Yearly"),
    ("weekly",  "Weekly"),
]

NONE_VALUE = -1


class SubscriptionDialog(QDialog):
    def __init__(
        self,
        conn: sqlite3.Connection,
        subscription: Optional[Subscription] = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._editing = subscription
        self._repo = SubscriptionRepository(conn)
        self._accounts = AccountRepository(conn).list()
        self._categories = CategoryRepository(conn).list(kind="expense")
        self._saved: Optional[Subscription] = None

        self.setWindowTitle("Edit subscription" if subscription else "Add subscription")
        self.setMinimumWidth(420)
        self.setModal(True)

        self._build()
        if subscription is not None:
            self._prefill(subscription)
        else:
            self._next_date.setDate(QDate.currentDate())
        self._name.setFocus()

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 22, 24, 20)
        outer.setSpacing(14)

        title = QLabel("Edit subscription" if self._editing else "Add subscription")
        title.setProperty("class", "h2")
        outer.addWidget(title)

        form = QFormLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self._name = QLineEdit()
        self._name.setPlaceholderText("e.g. Netflix")
        form.addRow("Name", self._name)

        self._amount = QDoubleSpinBox()
        self._amount.setDecimals(2)
        self._amount.setRange(0.0, 99_99_99_999.99)
        self._amount.setSingleStep(50.0)
        self._amount.setPrefix(f"{money.active().symbol} ")
        self._amount.setAlignment(Qt.AlignmentFlag.AlignRight)
        form.addRow("Amount", self._amount)

        self._cycle = QComboBox()
        for value, label in CYCLE_LABELS:
            self._cycle.addItem(label, value)
        form.addRow("Billing cycle", self._cycle)

        self._next_date = QDateEdit()
        self._next_date.setCalendarPopup(True)
        self._next_date.setDisplayFormat("dd MMM yyyy")
        self._next_date.setDate(QDate.currentDate())
        form.addRow("Next billing", self._next_date)

        self._category = QComboBox()
        self._category.addItem("None", NONE_VALUE)
        for c in self._categories:
            self._category.addItem(c.name, c.id)
        form.addRow("Category", self._category)

        self._account = QComboBox()
        self._account.addItem("None", NONE_VALUE)
        for a in self._accounts:
            self._account.addItem(f"{a.name}  ·  {a.type}", a.id)
        form.addRow("Account", self._account)

        self._active = QCheckBox("Active")
        self._active.setChecked(True)
        form.addRow("", self._active)

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

    def _prefill(self, sub: Subscription) -> None:
        self._name.setText(sub.name)
        self._amount.setValue(float(money.to_major(sub.amount)))
        idx = next(i for i, (v, _) in enumerate(CYCLE_LABELS) if v == sub.cycle)
        self._cycle.setCurrentIndex(idx)
        self._next_date.setDate(
            QDate(sub.next_billing_date.year, sub.next_billing_date.month, sub.next_billing_date.day)
        )
        if sub.category_id is not None:
            i = self._category.findData(sub.category_id)
            if i >= 0:
                self._category.setCurrentIndex(i)
        if sub.account_id is not None:
            i = self._account.findData(sub.account_id)
            if i >= 0:
                self._account.setCurrentIndex(i)
        self._active.setChecked(sub.active)

    def _on_save(self) -> None:
        name = self._name.text().strip()
        if not name:
            QMessageBox.warning(self, "Cannot save", "Subscription needs a name.")
            return
        amount_minor = money.to_minor(self._amount.value())
        if amount_minor <= 0:
            QMessageBox.warning(self, "Cannot save", "Amount must be greater than zero.")
            return

        qd = self._next_date.date()
        category_id = self._category.currentData()
        account_id = self._account.currentData()

        sub = Subscription(
            id=self._editing.id if self._editing else None,
            name=name,
            amount=amount_minor,
            cycle=self._cycle.currentData(),
            next_billing_date=date(qd.year(), qd.month(), qd.day()),
            category_id=category_id if category_id != NONE_VALUE else None,
            account_id=account_id if account_id != NONE_VALUE else None,
            active=self._active.isChecked(),
        )
        if self._editing:
            self._saved = self._repo.update(sub)
        else:
            self._saved = self._repo.add(sub)
        self.accept()

    def saved(self) -> Optional[Subscription]:
        return self._saved
