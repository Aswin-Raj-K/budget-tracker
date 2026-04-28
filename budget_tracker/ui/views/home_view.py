from __future__ import annotations

import calendar

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout

from budget_tracker.core import money
from budget_tracker.core.repositories.categories import CategoryRepository
from budget_tracker.services._month import current_month
from budget_tracker.services.budget_service import BudgetService
from budget_tracker.services.summary_service import SummaryService
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

    add_transaction_requested = Signal()

    def __init__(self, conn, parent=None):
        super().__init__(conn, parent)
        self.summary = SummaryService(conn)
        self.budgets_svc = BudgetService(conn)
        self.categories = CategoryRepository(conn)

        self._build()
        self.refresh()

    # ---------- UI assembly ----------

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 22, 28, 24)
        outer.setSpacing(16)

        self._month_lbl = QLabel("")
        self._month_lbl.setProperty("class", "section")
        outer.addWidget(self._month_lbl)

        # KPI row
        self._kpi_spent = KpiCard("Spent this month")
        self._kpi_income = KpiCard("Income this month")
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

    # ---------- data binding ----------

    def refresh(self) -> None:
        month = current_month()
        y, m = month.split("-")
        self._month_lbl.setText(
            f"This month  ·  {calendar.month_name[int(m)]} {y}".upper()
        )

        kpis = self.summary.kpis_for_month(month)
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
        self._populate_budgets(month)

    def _populate_transactions(self) -> None:
        self._tx_card.clear_body()
        recent = self.summary.recent_transactions(limit=8)
        if not recent:
            self._tx_card.body_layout().addWidget(
                _muted_message("No transactions yet. Add one to see it here.")
            )
            return
        cats_by_id = {c.id: c for c in self.categories.list(include_archived=True)}
        for tx in recent:
            cat = cats_by_id.get(tx.category_id) if tx.category_id else None
            self._tx_card.body_layout().addWidget(TransactionRow(tx, cat))
        self._tx_card.body_layout().addStretch(1)

    def _populate_budgets(self, month: str) -> None:
        self._budget_card.clear_body()
        usages = self.budgets_svc.usage_for_month(month)
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
        # Real dialog wiring lands in Phase 8; the signal is exposed now so
        # the main window can connect once it exists.
        self.add_transaction_requested.emit()
