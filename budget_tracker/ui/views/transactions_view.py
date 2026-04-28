from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout

from budget_tracker.ui.views.base import BaseView
from budget_tracker.ui.widgets.empty_state import EmptyState


class TransactionsView(BaseView):
    title = "Transactions"
    primary_action_label = "+ Add Transaction"

    def __init__(self, conn, parent=None):
        super().__init__(conn, parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)
        layout.addWidget(EmptyState(
            "Transactions view",
            "Filterable table of every transaction — landing in Phase 8.",
        ))
        layout.addStretch(1)
