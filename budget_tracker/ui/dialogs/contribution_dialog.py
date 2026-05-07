from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
)

from budget_tracker.core import money
from budget_tracker.core.models import Account, Category

Direction = Literal["add", "withdraw"]
LinkedKind = Literal["transfer", "expense"]


@dataclass(frozen=True)
class LinkedTransaction:
    """What the dialog returns when the user opted in to "also record"."""
    kind: LinkedKind
    from_account_id: int
    to_account_id: Optional[int]    # transfer only
    category_id: Optional[int]      # expense only (may still be None — uncategorised)


class ContributionDialog(QDialog):
    """Single-amount input with an optional "also record this as a
    transaction" section.

    When ``accounts`` is provided, a checkbox + a Transfer/Expense
    toggle appear:
      * Transfer mode — ``From`` and ``To`` account pickers; posts a
        transfer between two accounts the user owns (e.g. checking →
        savings, or checking → tracked credit card).
      * Expense mode — ``From`` account + optional ``Category``; posts
        an expense (the destination is outside the app, e.g. an
        external mortgage or student-loan servicer).

    The default mode comes from ``default_mode``: 'transfer' for
    savings contributions, 'expense' for debt-payoff payments.
    """

    def __init__(
        self,
        title: str,
        action_label: str,
        max_value: Optional[int] = None,
        accounts: Optional[Iterable[Account]] = None,
        categories: Optional[Iterable[Category]] = None,
        default_mode: LinkedKind = "transfer",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._amount_minor: Optional[int] = None
        self._linked: Optional[LinkedTransaction] = None

        self._max_value = max_value
        self._action_label = action_label
        self._accounts: list[Account] = list(accounts or [])
        self._categories: list[Category] = list(categories or [])
        self._default_mode = default_mode

        self.setWindowTitle(title)
        self.setMinimumWidth(420)
        self.setModal(True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 22, 24, 20)
        outer.setSpacing(14)

        title_lbl = QLabel(title)
        title_lbl.setProperty("class", "h2")
        outer.addWidget(title_lbl)

        form = QFormLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self._amount = QDoubleSpinBox()
        self._amount.setDecimals(2)
        upper = (max_value / 100.0) if max_value is not None else 99_99_99_999.99
        self._amount.setRange(0.0, upper)
        self._amount.setSingleStep(500.0)
        self._amount.setPrefix(f"{money.active().symbol} ")
        self._amount.setAlignment(Qt.AlignmentFlag.AlignRight)
        form.addRow("Amount", self._amount)

        # Optional record-as-transaction section. Hidden until the user
        # opts in so the simple "just bump the counter" flow stays clean.
        self._record_check: Optional[QCheckBox] = None
        self._mode_group: Optional[QButtonGroup] = None
        self._transfer_radio: Optional[QRadioButton] = None
        self._expense_radio: Optional[QRadioButton] = None
        self._from_combo: Optional[QComboBox] = None
        self._to_combo: Optional[QComboBox] = None
        self._category_combo: Optional[QComboBox] = None

        if self._accounts:
            self._record_check = QCheckBox("Also record this as a transaction")
            self._record_check.toggled.connect(self._on_toggle_record)
            form.addRow("", self._record_check)

            mode_row = QHBoxLayout()
            mode_row.setSpacing(12)
            self._transfer_radio = QRadioButton("Transfer to another account")
            self._expense_radio = QRadioButton("Expense (paid outside the app)")
            self._mode_group = QButtonGroup(self)
            self._mode_group.addButton(self._transfer_radio)
            self._mode_group.addButton(self._expense_radio)
            mode_row.addWidget(self._transfer_radio)
            mode_row.addWidget(self._expense_radio)
            mode_row.addStretch(1)
            self._mode_label = QLabel("Record as")
            form.addRow(self._mode_label, mode_row)
            self._transfer_radio.toggled.connect(self._refresh_mode_fields)

            # From account — used in BOTH modes.
            self._from_combo = QComboBox()
            for a in self._accounts:
                self._from_combo.addItem(f"{a.name}  ·  {a.type}", a.id)
            self._from_label = QLabel("From")
            form.addRow(self._from_label, self._from_combo)

            # To account — transfer mode only.
            self._to_combo = QComboBox()
            for a in self._accounts:
                self._to_combo.addItem(f"{a.name}  ·  {a.type}", a.id)
            self._to_label = QLabel("To")
            form.addRow(self._to_label, self._to_combo)

            # Category — expense mode only. "None" allowed for
            # uncategorised expenses.
            self._category_combo = QComboBox()
            self._category_combo.addItem("Uncategorised", None)
            for c in self._categories:
                if c.kind == "expense":
                    label = (
                        f"   │  {c.name}" if c.parent_id is not None else c.name
                    )
                    self._category_combo.addItem(label, c.id)
            self._category_label = QLabel("Category")
            form.addRow(self._category_label, self._category_combo)

            # Initial state: collapsed.
            self._set_record_section_visible(False)

        outer.addLayout(form)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.setProperty("class", "secondary")
        cancel.clicked.connect(self.reject)
        save = QPushButton(action_label)
        save.setProperty("class", "primary")
        save.setDefault(True)
        save.clicked.connect(self._on_save)
        button_row.addWidget(cancel)
        button_row.addWidget(save)
        outer.addLayout(button_row)

    # ---------- mode + visibility plumbing ----------

    def _set_record_section_visible(self, visible: bool) -> None:
        for w in (
            self._mode_label,
            self._transfer_radio,
            self._expense_radio,
        ):
            if w is not None:
                w.setVisible(visible)
        if not visible:
            for w in (
                self._from_label, self._from_combo,
                self._to_label, self._to_combo,
                self._category_label, self._category_combo,
            ):
                if w is not None:
                    w.setVisible(False)
            return
        # Default mode kicks in here so the right fields show first.
        if self._default_mode == "expense":
            assert self._expense_radio is not None
            self._expense_radio.setChecked(True)
        else:
            assert self._transfer_radio is not None
            self._transfer_radio.setChecked(True)
        self._refresh_mode_fields()

    def _on_toggle_record(self, checked: bool) -> None:
        self._set_record_section_visible(checked)

    def _refresh_mode_fields(self) -> None:
        if self._record_check is None or not self._record_check.isChecked():
            return
        is_transfer = self._transfer_radio is not None and self._transfer_radio.isChecked()
        # From is shared.
        if self._from_label is not None:
            self._from_label.setVisible(True)
        if self._from_combo is not None:
            self._from_combo.setVisible(True)
        # To: transfer only.
        if self._to_label is not None:
            self._to_label.setVisible(is_transfer)
        if self._to_combo is not None:
            self._to_combo.setVisible(is_transfer)
        # Category: expense only.
        if self._category_label is not None:
            self._category_label.setVisible(not is_transfer)
        if self._category_combo is not None:
            self._category_combo.setVisible(not is_transfer)

    # ---------- save / read-back ----------

    def _on_save(self) -> None:
        m = money.to_minor(self._amount.value())
        if m <= 0:
            QMessageBox.warning(self, "Cannot save", "Amount must be greater than zero.")
            return

        if self._record_check is not None and self._record_check.isChecked():
            assert self._from_combo is not None
            from_id = self._from_combo.currentData()
            if from_id is None:
                QMessageBox.warning(
                    self, "Cannot save",
                    "Pick the account the money is coming from.",
                )
                return

            is_transfer = self._transfer_radio is not None and self._transfer_radio.isChecked()
            if is_transfer:
                assert self._to_combo is not None
                to_id = self._to_combo.currentData()
                if to_id is None:
                    QMessageBox.warning(
                        self, "Cannot save",
                        "Pick a destination account, or switch to Expense mode.",
                    )
                    return
                if from_id == to_id:
                    QMessageBox.warning(
                        self, "Cannot save",
                        "Source and destination accounts must be different.",
                    )
                    return
                self._linked = LinkedTransaction(
                    kind="transfer",
                    from_account_id=from_id,
                    to_account_id=to_id,
                    category_id=None,
                )
            else:
                cat_id = self._category_combo.currentData() if self._category_combo else None
                self._linked = LinkedTransaction(
                    kind="expense",
                    from_account_id=from_id,
                    to_account_id=None,
                    category_id=cat_id,
                )

        self._amount_minor = m
        self.accept()

    def amount_minor(self) -> Optional[int]:
        return self._amount_minor

    def linked_transaction(self) -> Optional[LinkedTransaction]:
        return self._linked

    # ---------- back-compat shim so older callers / tests still work ----------

    def transfer_accounts(self) -> Optional[tuple[int, int]]:
        if self._linked is None or self._linked.kind != "transfer":
            return None
        return self._linked.from_account_id, self._linked.to_account_id  # type: ignore[return-value]
