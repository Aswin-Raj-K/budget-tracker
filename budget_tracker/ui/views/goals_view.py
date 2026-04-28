from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout

from budget_tracker.ui.views.base import BaseView
from budget_tracker.ui.widgets.empty_state import EmptyState


class GoalsView(BaseView):
    title = "Goals"
    primary_action_label = "+ Add Goal"

    def __init__(self, conn, parent=None):
        super().__init__(conn, parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)
        layout.addWidget(EmptyState(
            "Goals view",
            "Savings goals and debt payoff cards — landing in Phase 10.",
        ))
        layout.addStretch(1)
