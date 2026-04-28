from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout

from budget_tracker.ui.views.base import BaseView
from budget_tracker.ui.widgets.empty_state import EmptyState


class HomeView(BaseView):
    title = "Home"
    primary_action_label = "+ Add Transaction"

    def __init__(self, conn, parent=None):
        super().__init__(conn, parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)
        layout.addWidget(EmptyState(
            "Home view",
            "KPI cards, recent transactions, and budget glance — landing in Phase 7.",
        ))
        layout.addStretch(1)
