from __future__ import annotations

from datetime import date
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout

from budget_tracker.core import money
from budget_tracker.core.models import Category, Transaction
from budget_tracker.ui.widgets.progress_row import ColorDot

_MONTHS = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _format_date(d: date) -> str:
    return f"{_MONTHS[d.month]} {d.day:02d}"


class TransactionRow(QFrame):
    """Single transaction line used inside the Recent Transactions card."""

    def __init__(
        self,
        tx: Transaction,
        category: Optional[Category] = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 4, 0, 4)
        root.setSpacing(12)

        # Date column
        date_lbl = QLabel(_format_date(tx.occurred_on))
        date_lbl.setProperty("class", "subtle")
        date_lbl.setFixedWidth(58)
        root.addWidget(date_lbl)

        # Category dot + name (or "Transfer" / "Income")
        dot_color = category.color if category else "#6B6B7A"
        root.addWidget(ColorDot(dot_color))

        name = (
            category.name if category else
            "Transfer" if tx.kind == "transfer" else
            "Income" if tx.kind == "income" else
            "Uncategorised"
        )
        cat_lbl = QLabel(name)
        cat_lbl.setProperty("class", "h3")
        root.addWidget(cat_lbl)

        # Note (subtle, takes available space)
        if tx.note:
            note_lbl = QLabel(tx.note)
            note_lbl.setProperty("class", "muted")
            note_lbl.setMaximumWidth(260)
            note_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
            root.addWidget(note_lbl)

        root.addStretch(1)

        # Amount: red for expense, green for income, neutral for transfer
        sign = "-" if tx.kind == "expense" else "+" if tx.kind == "income" else ""
        amount_text = f"{sign}{money.format_amount(tx.amount)}"
        amt_lbl = QLabel(amount_text)
        amt_lbl.setProperty("class", "h3")
        color = (
            "danger" if tx.kind == "expense"
            else "success" if tx.kind == "income"
            else "muted"
        )
        amt_lbl.setProperty("color", color)
        # Inline color since QSS color-by-property would need extra rules:
        if tx.kind == "expense":
            amt_lbl.setStyleSheet("color: #F87171;")
        elif tx.kind == "income":
            amt_lbl.setStyleSheet("color: #34D399;")
        amt_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        root.addWidget(amt_lbl)
