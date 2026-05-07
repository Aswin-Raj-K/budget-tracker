from __future__ import annotations

from datetime import date
from typing import Iterable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from budget_tracker.core import money
from budget_tracker.core.models import Account, Transaction
from budget_tracker.core.repositories.accounts import AccountRepository
from budget_tracker.core.repositories.categories import CategoryRepository
from budget_tracker.core.repositories.goals import GoalRepository
from budget_tracker.core.repositories.transactions import TransactionRepository
from budget_tracker.services.goal_service import GoalProgress, GoalService
from budget_tracker.ui.dialogs.contribution_dialog import ContributionDialog
from budget_tracker.ui.dialogs.goal_dialog import GoalDialog
from budget_tracker.ui.views.base import BaseView


_MONTHS = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _fmt_date(d: date) -> str:
    return f"{d.day:02d} {_MONTHS[d.month]} {d.year}"


def _deadline_label(progress: GoalProgress) -> str:
    if progress.is_complete:
        return "Goal complete — great work."
    if progress.days_remaining is None:
        return "No deadline set."
    days = progress.days_remaining
    if days < 0:
        return f"{abs(days)} days past deadline"
    if days == 0:
        return "Due today"
    if days < 14:
        return f"{days} day{'s' if days != 1 else ''} left"
    if days < 60:
        weeks = days // 7
        return f"~{weeks} weeks left"
    months = days // 30
    return f"~{months} months left"


class _GoalCard(QFrame):
    edit_requested = Signal()
    delete_requested = Signal()
    contribute_requested = Signal()
    withdraw_requested = Signal()

    def __init__(
        self,
        progress: GoalProgress,
        transactions: list[Transaction],
        accounts_by_id: dict[int, Account],
        parent=None,
    ):
        super().__init__(parent)
        self.setProperty("class", "card")
        self.setMinimumHeight(190)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._open_context)

        self._transactions = transactions
        self._accounts_by_id = accounts_by_id

        goal = progress.goal
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 20)
        layout.setSpacing(10)

        head = QHBoxLayout()
        head.setSpacing(8)
        name = QLabel(goal.name)
        name.setProperty("class", "h2")
        kind_lbl = QLabel("Savings" if goal.kind == "savings" else "Debt payoff")
        kind_lbl.setProperty("class", "chip")
        head.addWidget(name)
        head.addStretch(1)
        head.addWidget(kind_lbl)
        layout.addLayout(head)

        if goal.kind == "savings":
            top_line = (
                f"{money.format_amount(goal.current_amount)} of "
                f"{money.format_amount(goal.target_amount)}"
            )
        else:
            top_line = (
                f"{money.format_amount(goal.current_amount)} paid of "
                f"{money.format_amount(goal.target_amount)} owed"
            )
        amount_lbl = QLabel(top_line)
        amount_lbl.setProperty("class", "h3")
        layout.addWidget(amount_lbl)

        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(int(progress.percent))
        bar.setTextVisible(False)
        bar.setFixedHeight(8)
        if progress.is_complete:
            bar.setProperty("status", "success")
        layout.addWidget(bar)

        meta = QHBoxLayout()
        meta.setSpacing(8)
        percent_lbl = QLabel(f"{progress.percent:.0f}%")
        percent_lbl.setProperty("class", "muted")
        deadline_lbl = QLabel(_deadline_label(progress))
        deadline_lbl.setProperty("class", "subtle")
        meta.addWidget(percent_lbl)
        meta.addStretch(1)
        meta.addWidget(deadline_lbl)
        layout.addLayout(meta)

        # Toggle row — shows / hides the linked transactions panel below.
        self._toggle_btn = QPushButton(self._toggle_label(False))
        self._toggle_btn.setProperty("class", "ghost")
        self._toggle_btn.setCheckable(True)
        self._toggle_btn.toggled.connect(self._on_toggle)

        toggle_row = QHBoxLayout()
        toggle_row.addWidget(self._toggle_btn)
        toggle_row.addStretch(1)
        layout.addLayout(toggle_row)

        # The transactions panel itself — built once, hidden by default.
        self._tx_panel = self._build_tx_panel()
        self._tx_panel.setVisible(False)
        layout.addWidget(self._tx_panel)

        layout.addStretch(1)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        contribute_label = "+ Make Payment" if goal.kind == "debt" else "+ Contribute"
        contribute = QPushButton(contribute_label)
        contribute.setProperty("class", "primary")
        contribute.clicked.connect(self.contribute_requested.emit)
        actions.addWidget(contribute)

        if goal.kind == "savings":
            withdraw = QPushButton("Withdraw")
            withdraw.setProperty("class", "secondary")
            withdraw.clicked.connect(self.withdraw_requested.emit)
            actions.addWidget(withdraw)
        actions.addStretch(1)

        edit_btn = QPushButton("Edit")
        edit_btn.setProperty("class", "ghost")
        edit_btn.setToolTip("Edit goal (double-click the card or right-click for more)")
        edit_btn.clicked.connect(self.edit_requested.emit)
        actions.addWidget(edit_btn)

        delete_btn = QPushButton("Delete")
        delete_btn.setProperty("class", "ghost")
        delete_btn.setToolTip("Delete goal — linked transactions are kept and unlinked.")
        delete_btn.clicked.connect(self.delete_requested.emit)
        actions.addWidget(delete_btn)

        layout.addLayout(actions)

    def _toggle_label(self, expanded: bool) -> str:
        n = len(self._transactions)
        word = "transaction" if n == 1 else "transactions"
        arrow = "▴" if expanded else "▾"
        return f"{arrow}  {n} linked {word}"

    def _on_toggle(self, expanded: bool) -> None:
        self._tx_panel.setVisible(expanded)
        self._toggle_btn.setText(self._toggle_label(expanded))

    def _build_tx_panel(self) -> QWidget:
        wrap = QFrame()
        wrap.setProperty("class", "card-flush")
        layout = QVBoxLayout(wrap)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(4)

        if not self._transactions:
            empty = QLabel(
                "No real transactions linked yet. Tick "
                "“Also record this as a transfer” when contributing "
                "to track them here."
            )
            empty.setProperty("class", "subtle")
            empty.setWordWrap(True)
            layout.addWidget(empty)
            return wrap

        for tx in self._transactions[:8]:                     # cap so the card doesn't explode
            row = QHBoxLayout()
            row.setSpacing(8)
            date_lbl = QLabel(_fmt_date(tx.occurred_on))
            date_lbl.setProperty("class", "subtle")
            date_lbl.setFixedWidth(82)
            row.addWidget(date_lbl)

            account_lbl = QLabel(self._account_label(tx))
            account_lbl.setProperty("class", "muted")
            row.addWidget(account_lbl, 1)

            amount_lbl = QLabel(money.format_amount(tx.amount))
            amount_lbl.setProperty("class", "h3")
            amount_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            row.addWidget(amount_lbl)

            container = QFrame()
            container.setLayout(row)
            layout.addWidget(container)

        if len(self._transactions) > 8:
            more = QLabel(f"… and {len(self._transactions) - 8} more")
            more.setProperty("class", "subtle")
            layout.addWidget(more)

        return wrap

    def _account_label(self, tx: Transaction) -> str:
        src = self._accounts_by_id.get(tx.account_id)
        dst = (
            self._accounts_by_id.get(tx.transfer_account_id)
            if tx.transfer_account_id is not None else None
        )
        if dst is not None:
            return f"{src.name if src else '—'}  →  {dst.name}"
        return src.name if src else "—"

    def mouseDoubleClickEvent(self, ev) -> None:  # noqa: N802 (Qt naming)
        # Double-click anywhere on the card edits — matches Budgets / Transactions.
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


class GoalsView(BaseView):
    title = "Goals"
    primary_action_label = "+ Add Goal"

    COLUMNS = 2

    def __init__(self, conn, parent=None):
        super().__init__(conn, parent)
        self._service = GoalService(conn)
        self._repo = GoalRepository(conn)
        self._account_repo = AccountRepository(conn)
        self._category_repo = CategoryRepository(conn)
        self._tx_repo = TransactionRepository(conn)
        self._build()
        self.refresh()

    # ---------- UI ----------

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 22, 28, 24)
        outer.setSpacing(20)

        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._host = QWidget(self._scroll)
        self._host_layout = QVBoxLayout(self._host)
        self._host_layout.setContentsMargins(0, 0, 0, 0)
        self._host_layout.setSpacing(22)
        self._scroll.setWidget(self._host)
        outer.addWidget(self._scroll, 1)

        self._empty = QLabel(
            'No goals yet.\nClick “+ Add Goal” to set a savings target or debt to pay off.'
        )
        self._empty.setProperty("class", "muted")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setVisible(False)
        outer.addWidget(self._empty, 1)

    # ---------- data binding ----------

    def refresh(self) -> None:
        self._clear_host()

        savings = self._service.list_with_progress(kind="savings")
        debts = self._service.list_with_progress(kind="debt")

        if not savings and not debts:
            self._scroll.setVisible(False)
            self._empty.setVisible(True)
            return

        self._scroll.setVisible(True)
        self._empty.setVisible(False)

        # Snapshot the maps once per refresh — both grids use them.
        accounts_by_id = {
            a.id: a for a in self._account_repo.list(include_archived=True)
        }

        if savings:
            self._host_layout.addWidget(self._section_label("Savings goals"))
            self._host_layout.addLayout(self._grid(savings, accounts_by_id))
        if debts:
            self._host_layout.addWidget(self._section_label("Debt payoff"))
            self._host_layout.addLayout(self._grid(debts, accounts_by_id))
        self._host_layout.addStretch(1)

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setProperty("class", "section")
        return lbl

    def _grid(
        self,
        items: Iterable[GoalProgress],
        accounts_by_id: dict[int, Account],
    ) -> QGridLayout:
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(14)
        for i, p in enumerate(items):
            txs = (
                self._tx_repo.list(goal_id=p.goal.id) if p.goal.id is not None else []
            )
            card = _GoalCard(p, txs, accounts_by_id, parent=self._host)
            card.edit_requested.connect(lambda gp=p: self._edit(gp))
            card.delete_requested.connect(lambda gp=p: self._delete(gp))
            card.contribute_requested.connect(lambda gp=p: self._contribute(gp))
            card.withdraw_requested.connect(lambda gp=p: self._withdraw(gp))
            grid.addWidget(card, i // self.COLUMNS, i % self.COLUMNS)
        return grid

    def _clear_host(self) -> None:
        while self._host_layout.count():
            item = self._host_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
                continue
            sub = item.layout()
            if sub is not None:
                self._clear_layout(sub)

    def _clear_layout(self, layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    # ---------- actions ----------

    def on_primary_action(self) -> None:
        dlg = GoalDialog(self.conn, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _edit(self, progress: GoalProgress) -> None:
        dlg = GoalDialog(self.conn, goal=progress.goal, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _delete(self, progress: GoalProgress) -> None:
        goal = progress.goal
        if goal.id is None:
            return
        linked_count = len(self._tx_repo.list(goal_id=goal.id))
        body = f"Delete goal “{goal.name}”?"
        if linked_count > 0:
            body += (
                f"\n\nThe {linked_count} transaction"
                f"{'s' if linked_count != 1 else ''} linked to this goal "
                "will stay on the Transactions tab — only the link is removed."
            )
        msg = QMessageBox(self)
        msg.setWindowTitle("Delete goal")
        msg.setText(body)
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        msg.setDefaultButton(QMessageBox.StandardButton.Cancel)
        if msg.exec() == QMessageBox.StandardButton.Yes:
            self._repo.delete(goal.id)
            self.refresh()

    def _contribute(self, progress: GoalProgress) -> None:
        goal = progress.goal
        if goal.id is None:
            return
        title = (
            f"Make payment toward {goal.name}"
            if goal.kind == "debt"
            else f"Contribute to {goal.name}"
        )
        action = "Pay" if goal.kind == "debt" else "Contribute"
        max_value = goal.target_amount - goal.current_amount  # don't overshoot
        accounts = self._account_repo.list()
        categories = self._category_repo.list()
        # Debt goals usually go out to an external payee → default to
        # Expense. Savings contributions typically move between two
        # tracked accounts → default to Transfer.
        default_mode = "expense" if goal.kind == "debt" else "transfer"
        dlg = ContributionDialog(
            title, action,
            max_value=max_value,
            accounts=accounts,
            categories=categories,
            default_mode=default_mode,
            parent=self,
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            amt = dlg.amount_minor()
            if not amt:
                return
            linked = dlg.linked_transaction()
            self._service.contribute(
                goal.id, amt,
                from_account_id=linked.from_account_id if linked else None,
                to_account_id=linked.to_account_id if linked else None,
                category_id=linked.category_id if linked else None,
            )
            self.refresh()

    def _withdraw(self, progress: GoalProgress) -> None:
        goal = progress.goal
        if goal.id is None:
            return
        title = f"Withdraw from {goal.name}"
        max_value = goal.current_amount
        if max_value <= 0:
            QMessageBox.information(self, "Nothing to withdraw", "This goal has no funds yet.")
            return
        accounts = self._account_repo.list()
        categories = self._category_repo.list()
        # Withdrawing from a savings goal almost always means moving
        # money back to a spending account → default Transfer.
        dlg = ContributionDialog(
            title, "Withdraw",
            max_value=max_value,
            accounts=accounts,
            categories=categories,
            default_mode="transfer",
            parent=self,
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            amt = dlg.amount_minor()
            if not amt:
                return
            linked = dlg.linked_transaction()
            self._service.contribute(
                goal.id, -amt,
                from_account_id=linked.from_account_id if linked else None,
                to_account_id=linked.to_account_id if linked else None,
                category_id=linked.category_id if linked else None,
            )
            self.refresh()
