from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from budget_tracker.core import money
from budget_tracker.core.repositories.categories import CategoryRepository
from budget_tracker.services._month import current_month, human_month, shift_month
from budget_tracker.services.budget_service import BudgetService
from budget_tracker.services.summary_service import SummaryService
from budget_tracker.ui.dialogs.transaction_dialog import TransactionDialog
from budget_tracker.ui.views.base import BaseView
from budget_tracker.ui.widgets.kpi_card import KpiCard
from budget_tracker.ui.widgets.progress_row import ProgressRow
from budget_tracker.ui.widgets.section_card import SectionCard
from budget_tracker.ui.widgets.transaction_row import TransactionRow


def _muted_message(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setProperty("class", "muted")
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setContentsMargins(0, 24, 0, 24)
    lbl.setWordWrap(True)
    return lbl


class HomeView(BaseView):
    title = "Home"
    primary_action_label = "+ Add Transaction"

    def __init__(self, conn, parent=None):
        super().__init__(conn, parent)
        self.summary = SummaryService(conn)
        self.budgets_svc = BudgetService(conn)
        self.categories = CategoryRepository(conn)

        self._month = current_month()
        self._build()
        self.refresh()

    # ---------- UI assembly ----------

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 22, 28, 24)
        outer.setSpacing(16)

        # Month switcher row — same pattern as Budgets view.
        switch_row = QHBoxLayout()
        switch_row.setSpacing(6)

        self._prev_btn = QPushButton("‹")
        self._prev_btn.setProperty("class", "icon")
        self._prev_btn.setFixedWidth(36)
        self._prev_btn.setToolTip("Previous month")
        self._prev_btn.clicked.connect(lambda: self._shift(-1))

        self._month_lbl = QLabel("")
        self._month_lbl.setProperty("class", "h2")

        self._next_btn = QPushButton("›")
        self._next_btn.setProperty("class", "icon")
        self._next_btn.setFixedWidth(36)
        self._next_btn.setToolTip("Next month")
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

        # KPI row
        self._kpi_spent = KpiCard("Spent")
        self._kpi_income = KpiCard("Income")
        self._kpi_savings = KpiCard("Savings rate")
        self._kpi_top = KpiCard("Top category")

        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(14)
        for c in (self._kpi_spent, self._kpi_income, self._kpi_savings, self._kpi_top):
            kpi_row.addWidget(c)
        outer.addLayout(kpi_row)

        # Two-column body
        self._tx_card = SectionCard("Recent transactions")
        self._budget_card = SectionCard("Budgets at a glance")

        cols = QHBoxLayout()
        cols.setSpacing(14)
        cols.addWidget(self._tx_card, 3)
        cols.addWidget(self._budget_card, 2)
        outer.addLayout(cols, 1)

    # ---------- behaviour ----------

    def _shift(self, delta: int) -> None:
        self._month = shift_month(self._month, delta)
        self.refresh()

    def _jump_to_current(self) -> None:
        self._month = current_month()
        self.refresh()

    # ---------- data binding ----------

    def refresh(self) -> None:
        self._month_lbl.setText(human_month(self._month))

        kpis = self.summary.kpis_for_month(self._month)
        self._kpi_spent.set_value(money.format_amount(kpis.spent))
        self._kpi_income.set_value(money.format_amount(kpis.income))
        self._kpi_savings.set_value(f"{kpis.savings_rate:.0f}%")
        if kpis.top_category:
            self._kpi_top.set_value(
                kpis.top_category.name,
                money.format_amount(kpis.top_category_amount),
            )
        else:
            self._kpi_top.set_value("—")

        self._populate_transactions()
        self._populate_budgets()

    def _populate_transactions(self) -> None:
        self._tx_card.clear_body()
        recent = self.summary.recent_transactions(limit=8, month=self._month)
        if not recent:
            self._tx_card.body_layout().addWidget(
                _muted_message(
                    "No transactions in this month. "
                    "Add one with “+ Add Transaction” or flip back to a previous month."
                )
            )
            return
        cats_by_id = {c.id: c for c in self.categories.list(include_archived=True)}
        for tx in recent:
            cat = cats_by_id.get(tx.category_id) if tx.category_id else None
            self._tx_card.body_layout().addWidget(TransactionRow(tx, cat))
        self._tx_card.body_layout().addStretch(1)

    def _populate_budgets(self) -> None:
        self._budget_card.clear_body()
        usages = self.budgets_svc.usage_for_month(self._month)
        if not usages:
            self._budget_card.body_layout().addWidget(
                _muted_message("Set monthly budgets on the Budgets page to see them here.")
            )
            return
        for u in usages[:6]:
            amount_label = (
                f"{money.format_amount(u.spent_amount, with_symbol=False)}"
                f" / {money.format_amount(u.budget_amount)}"
            )
            self._budget_card.body_layout().addWidget(
                ProgressRow(
                    u.category.name,
                    amount_label,
                    u.percent,
                    status=u.status,
                    color=u.category.color,
                )
            )
        self._budget_card.body_layout().addStretch(1)

    # ---------- actions ----------

    def on_primary_action(self) -> None:
        dlg = TransactionDialog(self.conn, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.refresh()
