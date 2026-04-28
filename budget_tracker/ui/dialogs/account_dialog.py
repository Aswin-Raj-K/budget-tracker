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
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from budget_tracker.core import money
from budget_tracker.core.models import Account, AccountType
from budget_tracker.core.repositories.accounts import AccountRepository

TYPE_LABELS: list[tuple[AccountType, str]] = [
    ("checking", "Checking"),
    ("savings",  "Savings"),
    ("credit",   "Credit card"),
    ("cash",     "Cash"),
    ("wallet",   "Wallet"),
]


class AccountDialog(QDialog):
    def __init__(
        self,
        conn: sqlite3.Connection,
        account: Optional[Account] = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._editing = account
        self._repo = AccountRepository(conn)
        self._saved: Optional[Account] = None

        self.setWindowTitle("Edit account" if account else "Add account")
        self.setMinimumWidth(380)
        self.setModal(True)

        self._build()
        if account is not None:
            self._prefill(account)
        self._name.setFocus()

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 22, 24, 20)
        outer.setSpacing(14)

        title = QLabel("Edit account" if self._editing else "Add account")
        title.setProperty("class", "h2")
        outer.addWidget(title)

        form = QFormLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self._name = QLineEdit()
        self._name.setPlaceholderText("e.g. HDFC Savings")
        form.addRow("Name", self._name)

        self._type = QComboBox()
        for value, label in TYPE_LABELS:
            self._type.addItem(label, value)
        form.addRow("Type", self._type)

        self._opening = QDoubleSpinBox()
        self._opening.setDecimals(2)
        self._opening.setRange(-99_99_99_999.99, 99_99_99_999.99)
        self._opening.setSingleStep(1000.0)
        self._opening.setPrefix(f"{money.active().symbol} ")
        self._opening.setAlignment(Qt.AlignmentFlag.AlignRight)
        form.addRow("Opening balance", self._opening)

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

    def _prefill(self, a: Account) -> None:
        self._name.setText(a.name)
        idx = next(i for i, (v, _) in enumerate(TYPE_LABELS) if v == a.type)
        self._type.setCurrentIndex(idx)
        self._opening.setValue(float(money.to_major(a.opening_balance)) if a.opening_balance >= 0
                               else -float(money.to_major(-a.opening_balance)))

    def _on_save(self) -> None:
        name = self._name.text().strip()
        if not name:
            QMessageBox.warning(self, "Cannot save", "Account needs a name.")
            return
        opening = self._opening.value()
        # to_minor doesn't accept negatives — convert sign manually.
        opening_minor = money.to_minor(abs(opening))
        if opening < 0:
            opening_minor = -opening_minor

        a = Account(
            id=self._editing.id if self._editing else None,
            name=name,
            type=self._type.currentData(),
            opening_balance=opening_minor,
            archived=self._editing.archived if self._editing else False,
        )
        self._saved = self._repo.update(a) if self._editing else self._repo.add(a)
        self.accept()

    def saved(self) -> Optional[Account]:
        return self._saved
