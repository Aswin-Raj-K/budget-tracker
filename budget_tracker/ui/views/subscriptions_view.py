from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout

from budget_tracker.ui.views.base import BaseView
from budget_tracker.ui.widgets.empty_state import EmptyState


class SubscriptionsView(BaseView):
    title = "Subscriptions"
    primary_action_label = "+ Add Subscription"

    def __init__(self, conn, parent=None):
        super().__init__(conn, parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)
        layout.addWidget(EmptyState(
            "Subscriptions view",
            "Recurring charges with monthly cost summary — landing in Phase 11.",
        ))
        layout.addStretch(1)
