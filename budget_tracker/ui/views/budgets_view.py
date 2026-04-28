from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from budget_tracker.core import money
from budget_tracker.core.repositories.budgets import BudgetRepository
from budget_tracker.services._month import current_month, human_month, shift_month
from budget_tracker.services.budget_service import BudgetService, BudgetUsage
from budget_tracker.ui.dialogs.budget_dialog import BudgetDialog
from budget_tracker.ui.views.base import BaseView
from budget_tracker.ui.widgets.progress_row import ProgressRow


class _BudgetCard(QFrame):
    """Clickable card row for a single budget."""

    edit_requested = Signal()
    delete_requested = Signal()

    def __init__(self, usage: BudgetUsage, parent=None):
        super().__init__(parent)
        self.setProperty("class", "card")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._open_context)

        amount_label = (
            f"{money.format_amount(usage.spent_amount, with_symbol=False)}"
            f" / {money.format_amount(usage.budget_amount)}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 18)
        layout.setSpacing(8)

        layout.addWidget(
            ProgressRow(
                usage.category.name,
                amount_label,
                usage.percent,
                status=usage.status,
                color=usage.category.color,
            )
        )

        # Status footer
        if usage.status == "over":
            footer_text = f"Over budget by {money.format_amount(-usage.remaining)}"
            footer_color = "#F87171"
        elif usage.status == "warning":
            footer_text = (
                f"{money.format_amount(usage.remaining)} left  ·  {usage.percent:.0f}% used"
            )
            footer_color = "#FBBF24"
        else:
            footer_text = (
                f"{money.format_amount(usage.remaining)} left  ·  {usage.percent:.0f}% used"
            )
            footer_color = ""
        footer = QLabel(footer_text)
        footer.setProperty("class", "subtle")
        if footer_color:
            footer.setStyleSheet(f"color: {footer_color};")
        layout.addWidget(footer)

    def mouseDoubleClickEvent(self, ev) -> None:  # noqa: N802 (Qt naming)
        if ev.button() == Qt.MouseButton.LeftButton:
            self.edit_requested.emit()
        super().mouseDoubleClickEvent(ev)

    def _open_context(self, pos) -> None:
        menu = QMenu(self)
        edit = QAction("Edit", self)
        edit.triggered.connect(self.edit_requested.emit)
        delete = QAction("Delete", self)
        delete.triggered.connect(self.delete_requested.emit)
        menu.addAction(edit)
        menu.addSeparator()
        menu.addAction(delete)
        menu.exec(self.mapToGlobal(pos))


class BudgetsView(BaseView):
    title = "Budgets"
    primary_action_label = "+ Add Budget"

    def __init__(self, conn, parent=None):
        super().__init__(conn, parent)
        self._budgets_repo = BudgetRepository(conn)
        self._service = BudgetService(conn)

        self._month = current_month()
        self._build()
        self.refresh()

    # ---------- UI ----------

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 22, 28, 24)
        outer.setSpacing(16)

        # Month switcher
        switch_row = QHBoxLayout()
        switch_row.setSpacing(6)

        self._prev_btn = QPushButton("‹")
        self._prev_btn.setProperty("class", "icon")
        self._prev_btn.setFixedWidth(36)
        self._prev_btn.clicked.connect(lambda: self._shift(-1))

        self._month_lbl = QLabel("")
        self._month_lbl.setProperty("class", "h2")

        self._next_btn = QPushButton("›")
        self._next_btn.setProperty("class", "icon")
        self._next_btn.setFixedWidth(36)
        self._next_btn.clicked.connect(lambda: self._shift(1))

        self._this_month_btn = QPushButton("This month")
        self._this_month_btn.setProperty("class", "ghost")
        self._this_month_btn.clicked.connect(self._jump_to_current)

        switch_row.addWidget(self._prev_btn)
        switch_row.addWidget(self._month_lbl)
        switch_row.addWidget(self._next_btn)
        switch_row.addStretch(1)
        switch_row.addWidget(self._this_month_btn)
        outer.addLayout(switch_row)

        # Total / count summary
        self._summary_lbl = QLabel("")
        self._summary_lbl.setProperty("class", "subtle")
        outer.addWidget(self._summary_lbl)

        # Scrollable list of budget cards
        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._list_host = QWidget(self._scroll)
        self._list_layout = QVBoxLayout(self._list_host)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(10)
        self._scroll.setWidget(self._list_host)
        outer.addWidget(self._scroll, 1)

        # Empty placeholder
        self._empty = QLabel(
            'No budgets for this month yet.\nClick “+ Add Budget” to set one.'
        )
        self._empty.setProperty("class", "muted")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setVisible(False)
        outer.addWidget(self._empty, 1)

    # ---------- behaviour ----------

    def _shift(self, delta: int) -> None:
        self._month = shift_month(self._month, delta)
        self.refresh()

    def _jump_to_current(self) -> None:
        self._month = current_month()
        self.refresh()

    def refresh(self) -> None:
        self._month_lbl.setText(human_month(self._month))
        usages = self._service.usage_for_month(self._month)

        self._clear_list()
        self._scroll.setVisible(bool(usages))
        self._empty.setVisible(not usages)

        total_limit = sum(u.budget_amount for u in usages)
        total_spent = sum(u.spent_amount for u in usages)
        if usages:
            self._summary_lbl.setText(
                f"{len(usages)} budgets  ·  Spent {money.format_amount(total_spent)}"
                f" of {money.format_amount(total_limit)}"
            )
        else:
            self._summary_lbl.setText("")

        for u in usages:
            card = _BudgetCard(u, parent=self._list_host)
            card.edit_requested.connect(lambda usage=u: self._edit(usage))
            card.delete_requested.connect(lambda usage=u: self._delete(usage))
            self._list_layout.addWidget(card)
        self._list_layout.addStretch(1)

    def _clear_list(self) -> None:
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    # ---------- actions ----------

    def on_primary_action(self) -> None:
        dlg = BudgetDialog(self.conn, month=self._month, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _edit(self, usage: BudgetUsage) -> None:
        budget = self._budgets_repo.latest_for_category(usage.category.id, self._month)
        if budget is None:
            return
        dlg = BudgetDialog(
            self.conn,
            budget=budget,
            category_name=usage.category.name,
            parent=self,
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _delete(self, usage: BudgetUsage) -> None:
        budget = self._budgets_repo.latest_for_category(usage.category.id, self._month)
        if budget is None or budget.id is None:
            return
        msg = QMessageBox(self)
        msg.setWindowTitle("Delete budget")
        msg.setText(
            f"Remove the {money.format_amount(usage.budget_amount)} "
            f"budget for {usage.category.name}?\n\n"
            "Transactions are not affected."
        )
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        msg.setDefaultButton(QMessageBox.StandardButton.Cancel)
        if msg.exec() == QMessageBox.StandardButton.Yes:
            self._budgets_repo.delete(budget.id)
            self.refresh()
