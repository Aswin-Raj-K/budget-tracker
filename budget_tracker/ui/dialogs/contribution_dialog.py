from __future__ import annotations

from typing import Literal, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
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

Direction = Literal["add", "withdraw"]


class ContributionDialog(QDialog):
    """Single-amount input. The caller decides whether the resulting value
    increases or decreases the goal's current amount."""

    def __init__(
        self,
        title: str,
        action_label: str,
        max_value: Optional[int] = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._amount_minor: Optional[int] = None
        self._max_value = max_value
        self._action_label = action_label
        self.setWindowTitle(title)
        self.setMinimumWidth(360)
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

    def _on_save(self) -> None:
        m = money.to_minor(self._amount.value())
        if m <= 0:
            QMessageBox.warning(self, "Cannot save", "Amount must be greater than zero.")
            return
        self._amount_minor = m
        self.accept()

    def amount_minor(self) -> Optional[int]:
        return self._amount_minor
