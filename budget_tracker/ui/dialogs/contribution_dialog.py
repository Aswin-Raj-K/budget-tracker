from __future__ import annotations

from typing import Iterable, Literal, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
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
from budget_tracker.core.models import Account

Direction = Literal["add", "withdraw"]


class ContributionDialog(QDialog):
    """Single-amount input with an optional "also record as a transfer"
    section. The caller decides whether the resulting value increases or
    decreases the goal's current amount.

    When ``accounts`` is provided, a checkbox + two account pickers
    appear. If the user enables the checkbox and picks valid accounts,
    ``transfer_accounts()`` returns ``(from_id, to_id)`` so the caller
    can post a real transfer alongside the goal-progress bump.
    """

    def __init__(
        self,
        title: str,
        action_label: str,
        max_value: Optional[int] = None,
        accounts: Optional[Iterable[Account]] = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._amount_minor: Optional[int] = None
        self._transfer_from_id: Optional[int] = None
        self._transfer_to_id: Optional[int] = None

        self._max_value = max_value
        self._action_label = action_label
        self._accounts: list[Account] = list(accounts or [])

        self.setWindowTitle(title)
        self.setMinimumWidth(380)
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

        # Optional transfer section — only shown when the caller passed
        # accounts in. The checkbox stays unchecked by default so users
        # who just want to track progress see no extra fields.
        self._record_check: Optional[QCheckBox] = None
        self._from_combo: Optional[QComboBox] = None
        self._to_combo: Optional[QComboBox] = None
        if self._accounts:
            self._record_check = QCheckBox("Also record this as a transfer between accounts")
            self._record_check.toggled.connect(self._on_toggle_transfer)
            form.addRow("", self._record_check)

            self._from_combo = QComboBox()
            self._to_combo = QComboBox()
            for a in self._accounts:
                label = f"{a.name}  ·  {a.type}"
                self._from_combo.addItem(label, a.id)
                self._to_combo.addItem(label, a.id)
            self._from_combo.setVisible(False)
            self._to_combo.setVisible(False)
            self._from_label = QLabel("From")
            self._from_label.setVisible(False)
            self._to_label = QLabel("To")
            self._to_label.setVisible(False)
            form.addRow(self._from_label, self._from_combo)
            form.addRow(self._to_label, self._to_combo)

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

    def _on_toggle_transfer(self, checked: bool) -> None:
        for w in (self._from_label, self._from_combo, self._to_label, self._to_combo):
            if w is not None:
                w.setVisible(checked)

    def _on_save(self) -> None:
        m = money.to_minor(self._amount.value())
        if m <= 0:
            QMessageBox.warning(self, "Cannot save", "Amount must be greater than zero.")
            return

        if self._record_check is not None and self._record_check.isChecked():
            assert self._from_combo is not None and self._to_combo is not None
            from_id = self._from_combo.currentData()
            to_id = self._to_combo.currentData()
            if from_id is None or to_id is None:
                QMessageBox.warning(
                    self, "Cannot save",
                    "Pick both a source and a destination account, or uncheck the transfer option.",
                )
                return
            if from_id == to_id:
                QMessageBox.warning(
                    self, "Cannot save",
                    "Source and destination accounts must be different.",
                )
                return
            self._transfer_from_id = from_id
            self._transfer_to_id = to_id

        self._amount_minor = m
        self.accept()

    def amount_minor(self) -> Optional[int]:
        return self._amount_minor

    def transfer_accounts(self) -> Optional[tuple[int, int]]:
        """``(from_id, to_id)`` if the user enabled the transfer checkbox,
        otherwise ``None``."""
        if self._transfer_from_id is None or self._transfer_to_id is None:
            return None
        return self._transfer_from_id, self._transfer_to_id
