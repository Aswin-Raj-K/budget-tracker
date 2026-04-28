from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout

from budget_tracker.ui.views.base import BaseView
from budget_tracker.ui.widgets.empty_state import EmptyState


class BudgetsView(BaseView):
    title = "Budgets"
    primary_action_label = "+ Add Budget"

    def __init__(self, conn, parent=None):
        super().__init__(conn, parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)
        layout.addWidget(EmptyState(
            "Budgets view",
            "Per-category monthly budgets with progress — landing in Phase 9.",
        ))
        layout.addStretch(1)
