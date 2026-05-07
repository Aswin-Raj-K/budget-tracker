from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from budget_tracker.core import money
from budget_tracker.core.repositories.categories import CategoryRepository
from budget_tracker.services._month import current_month, human_month, shift_month
from budget_tracker.services.budget_service import BudgetService
from budget_tracker.services.summary_service import (
    CategorySpend,
    SummaryService,
)
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


def _breakdown_amount(spend: CategorySpend) -> str:
    return (
        f"{money.format_amount(spend.rolled_up_amount)}"
        f"  ·  {spend.percent:.0f}%"
    )


class _ClickableFrame(QFrame):
    """A QFrame that emits ``clicked`` on left mouse-press."""

    clicked = Signal()

    def mousePressEvent(self, ev) -> None:        # noqa: N802 (Qt naming)
        if ev.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(ev)


class _BreakdownGroup(QFrame):
    """One row in the Spending-by-category panel: a parent progress
    row plus, when there are sub-categories, a chevron that expands a
    nested children list. Defaults to collapsed so the panel reads
    cleanly on month switch."""

    def __init__(
        self,
        parent_spend: CategorySpend,
        children: list[CategorySpend],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._has_children = bool(children)
        self._expanded = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)

        head = _ClickableFrame(self)
        head_layout = QHBoxLayout(head)
        head_layout.setContentsMargins(0, 0, 0, 0)
        head_layout.setSpacing(10)

        # Chevron sized for legibility — a 14-pt glyph slightly heavier
        # than the body type, in muted text so it doesn't shout. Reserved
        # width even for childless rows so columns line up.
        self._chevron = QLabel(
            "▸" if self._has_children else "  ",
            head,
        )
        self._chevron.setFixedWidth(20)
        self._chevron.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._chevron.setStyleSheet(
            "font-size: 14px; font-weight: 600; color: #94A3B8;"
        )
        head_layout.addWidget(self._chevron)

        head_layout.addWidget(ProgressRow(
            parent_spend.category.name,
            _breakdown_amount(parent_spend),
            parent_spend.percent,
            status="under",
            color=parent_spend.category.color,
            parent=head,
        ), 1)

        if self._has_children:
            head.setCursor(Qt.CursorShape.PointingHandCursor)
            head.setToolTip("Click to show subcategories")
            head.clicked.connect(self._toggle)
        outer.addWidget(head)

        self._children_panel = QFrame(self)
        # The panel needs a fixed-height policy so the maximum-height
        # animation actually constrains the visible region instead of
        # the layout fighting back with sizeHint.
        self._children_panel.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed,
        )
        children_layout = QVBoxLayout(self._children_panel)
        children_layout.setContentsMargins(28, 4, 0, 4)
        children_layout.setSpacing(8)
        for c in children:
            children_layout.addWidget(ProgressRow(
                c.category.name,
                _breakdown_amount(c),
                c.percent,
                status="under",
                color=c.category.color,
                parent=self._children_panel,
            ))
        # Start collapsed: hidden + zero max height so the parent layout
        # immediately reclaims the space without a paint flash.
        self._children_panel.setVisible(False)
        self._children_panel.setMaximumHeight(0)
        outer.addWidget(self._children_panel)

        # Smooth show/hide via a maximumHeight animation so the
        # surrounding rows ease into place rather than snapping.
        self._anim = QPropertyAnimation(self._children_panel, b"maximumHeight", self)
        self._anim.setDuration(140)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.finished.connect(self._on_anim_finished)

    def _toggle(self) -> None:
        if not self._has_children:
            return
        self._expanded = not self._expanded
        self._chevron.setText("▾" if self._expanded else "▸")

        self._anim.stop()
        if self._expanded:
            # Compute the natural height with the panel transiently shown.
            self._children_panel.setMaximumHeight(16_777_215)   # QWIDGETSIZE_MAX
            self._children_panel.setVisible(True)
            target = self._children_panel.sizeHint().height()
            self._children_panel.setMaximumHeight(0)
            self._anim.setStartValue(0)
            self._anim.setEndValue(target)
        else:
            self._anim.setStartValue(self._children_panel.height())
            self._anim.setEndValue(0)
        self._anim.start()

    def _on_anim_finished(self) -> None:
        if self._expanded:
            # Drop the constraint so the panel can grow with its
            # contents (e.g. on a future re-layout). Visible already.
            self._children_panel.setMaximumHeight(16_777_215)
        else:
            self._children_panel.setVisible(False)


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
        # Outer layout is a flush scroll-area host so the page can grow
        # vertically without clipping the breakdown panel underneath.
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # Reserve the vertical-scrollbar gutter at all times — when a user
        # expands a breakdown row and the page suddenly overflows, an
        # appearing scrollbar would otherwise push every widget left and
        # feel glitchy.
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)

        host = QWidget(scroll)
        body = QVBoxLayout(host)
        body.setContentsMargins(28, 22, 28, 28)
        body.setSpacing(16)
        scroll.setWidget(host)
        outer.addWidget(scroll)

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
        body.addLayout(switch_row)

        # KPI row
        self._kpi_spent = KpiCard("Spent")
        self._kpi_income = KpiCard("Income")
        self._kpi_savings = KpiCard("Savings rate")
        self._kpi_top = KpiCard("Top category")

        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(14)
        for c in (self._kpi_spent, self._kpi_income, self._kpi_savings, self._kpi_top):
            kpi_row.addWidget(c)
        body.addLayout(kpi_row)

        # Two-column body. No vertical stretch so the breakdown panel
        # below sits naturally and the whole thing scrolls together.
        self._tx_card = SectionCard("Recent transactions")
        self._budget_card = SectionCard("Budgets at a glance")

        cols = QHBoxLayout()
        cols.setSpacing(14)
        cols.addWidget(self._tx_card, 3)
        cols.addWidget(self._budget_card, 2)
        body.addLayout(cols)

        # Full-width category-breakdown panel.
        self._breakdown_card = SectionCard("Spending by category")
        body.addWidget(self._breakdown_card)
        body.addStretch(1)

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
        self._populate_category_breakdown()

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

    def _populate_category_breakdown(self) -> None:
        body = self._breakdown_card.body_layout()
        self._breakdown_card.clear_body()
        breakdown = self.summary.category_breakdown_for_month(self._month)
        if breakdown.total <= 0:
            body.addWidget(_muted_message("No spending this month yet."))
            return

        for group in breakdown.groups:
            body.addWidget(
                _BreakdownGroup(group.parent, group.children, parent=self._breakdown_card)
            )

        if breakdown.uncategorised > 0:
            uncat_pct = (
                breakdown.uncategorised / breakdown.total * 100.0
                if breakdown.total else 0.0
            )
            body.addWidget(ProgressRow(
                "Uncategorised",
                f"{money.format_amount(breakdown.uncategorised)}  ·  {uncat_pct:.0f}%",
                uncat_pct,
                status="under",
                color="#6B7280",
            ))

    # ---------- actions ----------

    def on_primary_action(self) -> None:
        dlg = TransactionDialog(self.conn, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.refresh()
