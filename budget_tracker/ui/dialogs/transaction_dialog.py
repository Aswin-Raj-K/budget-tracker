from __future__ import annotations

import sqlite3
from datetime import date
from typing import Optional

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
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
    QWidget,
)

from budget_tracker.core import money
from budget_tracker.core.models import Account, Category, Transaction, TxKind
from budget_tracker.core.repositories.accounts import AccountRepository
from budget_tracker.core.repositories.categories import CategoryRepository
from budget_tracker.core.repositories.transactions import TransactionRepository

KIND_LABELS: list[tuple[TxKind, str]] = [
    ("expense", "Expense"),
    ("income", "Income"),
    ("transfer", "Transfer"),
]


class TransactionDialog(QDialog):
    """Modal form to add or edit a transaction.

    Returns QDialog.Accepted on a successful save; the saved Transaction
    is available via `saved()`.
    """

    def __init__(
        self,
        conn: sqlite3.Connection,
        transaction: Optional[Transaction] = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.conn = conn
        self._editing = transaction
        self._saved: Optional[Transaction] = None

        self._tx_repo = TransactionRepository(conn)
        self._account_repo = AccountRepository(conn)
        self._category_repo = CategoryRepository(conn)

        self._accounts: list[Account] = self._account_repo.list()
        self._all_categories: list[Category] = self._category_repo.list()

        self.setWindowTitle("Edit transaction" if transaction else "Add transaction")
        self.setMinimumWidth(440)
        self.setModal(True)

        self._build()

        if not self._accounts:
            QMessageBox.information(
                self,
                "Add an account first",
                "You need at least one account before adding transactions.\n"
                "Open Settings → Accounts and create one.",
            )
            self.reject()
            return

        if transaction is not None:
            self._prefill(transaction)
        else:
            self._kind.setCurrentIndex(0)
            self._on_kind_changed()
            self._date.setDate(QDate.currentDate())

        # Land on the amount field — the value the user nearly always
        # wants to type next.
        self._amount.setFocus()
        self._amount.selectAll()

    # ---------- UI ----------

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 22, 24, 20)
        outer.setSpacing(14)

        title = QLabel("Edit transaction" if self._editing else "Add transaction")
        title.setProperty("class", "h2")
        outer.addWidget(title)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        # Kind
        self._kind = QComboBox()
        for value, label in KIND_LABELS:
            self._kind.addItem(label, value)
        self._kind.currentIndexChanged.connect(self._on_kind_changed)
        form.addRow("Type", self._kind)

        # Date
        self._date = QDateEdit()
        self._date.setCalendarPopup(True)
        self._date.setDisplayFormat("dd MMM yyyy")
        self._date.setDate(QDate.currentDate())
        form.addRow("Date", self._date)

        # Amount
        self._amount = QDoubleSpinBox()
        self._amount.setDecimals(2)
        self._amount.setRange(0.0, 99_99_99_999.99)
        self._amount.setSingleStep(100.0)
        self._amount.setPrefix(f"{money.active().symbol} ")
        self._amount.setAlignment(Qt.AlignmentFlag.AlignRight)
        form.addRow("Amount", self._amount)

        # Account (source)
        self._account = QComboBox()
        for a in self._accounts:
            self._account.addItem(f"{a.name}  ·  {a.type}", a.id)
        form.addRow("Account", self._account)

        # Transfer-to (only visible for transfer kind)
        self._transfer_to = QComboBox()
        for a in self._accounts:
            self._transfer_to.addItem(f"{a.name}  ·  {a.type}", a.id)
        self._transfer_label = QLabel("Transfer to")
        form.addRow(self._transfer_label, self._transfer_to)

        # Category
        self._category = QComboBox()
        self._category_label = QLabel("Category")
        form.addRow(self._category_label, self._category)

        # Note
        self._note = QLineEdit()
        self._note.setPlaceholderText("Optional note")
        form.addRow("Note", self._note)

        outer.addLayout(form)

        # Buttons
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

    def _on_kind_changed(self) -> None:
        kind = self._current_kind()
        is_transfer = kind == "transfer"
        self._category.setVisible(not is_transfer)
        self._category_label.setVisible(not is_transfer)
        self._transfer_to.setVisible(is_transfer)
        self._transfer_label.setVisible(is_transfer)
        self._populate_categories(kind)

    def _populate_categories(self, kind: TxKind) -> None:
        self._category.clear()
        if kind == "transfer":
            return
        for c in self._all_categories:
            if c.kind == kind:
                self._category.addItem(c.name, c.id)

    def _prefill(self, tx: Transaction) -> None:
        idx = next(i for i, (v, _) in enumerate(KIND_LABELS) if v == tx.kind)
        self._kind.setCurrentIndex(idx)
        self._on_kind_changed()
        self._date.setDate(QDate(tx.occurred_on.year, tx.occurred_on.month, tx.occurred_on.day))
        self._amount.setValue(float(money.to_major(tx.amount)))
        # Account
        acc_idx = self._account.findData(tx.account_id)
        if acc_idx >= 0:
            self._account.setCurrentIndex(acc_idx)
        # Transfer
        if tx.transfer_account_id is not None:
            t_idx = self._transfer_to.findData(tx.transfer_account_id)
            if t_idx >= 0:
                self._transfer_to.setCurrentIndex(t_idx)
        # Category
        if tx.category_id is not None:
            c_idx = self._category.findData(tx.category_id)
            if c_idx >= 0:
                self._category.setCurrentIndex(c_idx)
        # Note
        if tx.note:
            self._note.setText(tx.note)

    # ---------- behaviour ----------

    def _current_kind(self) -> TxKind:
        return self._kind.currentData()

    def _on_save(self) -> None:
        try:
            tx = self._build_from_form()
        except ValueError as e:
            QMessageBox.warning(self, "Cannot save", str(e))
            return

        if self._editing and self._editing.id is not None:
            tx.id = self._editing.id
            self._saved = self._tx_repo.update(tx)
        else:
            self._saved = self._tx_repo.add(tx)
        self.accept()

    def _build_from_form(self) -> Transaction:
        kind = self._current_kind()
        amount_minor = money.to_minor(self._amount.value())
        if amount_minor <= 0:
            raise ValueError("Amount must be greater than zero.")

        account_id = self._account.currentData()
        if not account_id:
            raise ValueError("Select an account.")

        qd = self._date.date()
        occurred_on = date(qd.year(), qd.month(), qd.day())
        note = (self._note.text() or "").strip() or None

        category_id = None
        transfer_account_id = None

        if kind == "transfer":
            transfer_account_id = self._transfer_to.currentData()
            if not transfer_account_id:
                raise ValueError("Select a destination account.")
            if transfer_account_id == account_id:
                raise ValueError("Source and destination accounts must differ.")
        else:
            category_id = self._category.currentData()
            if not category_id:
                raise ValueError("Select a category.")

        return Transaction(
            id=None,
            occurred_on=occurred_on,
            kind=kind,
            amount=amount_minor,
            account_id=account_id,
            transfer_account_id=transfer_account_id,
            category_id=category_id,
            note=note,
        )

    def saved(self) -> Optional[Transaction]:
        return self._saved
