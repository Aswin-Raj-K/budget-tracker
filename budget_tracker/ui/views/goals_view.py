from __future__ import annotations

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
from budget_tracker.core.repositories.goals import GoalRepository
from budget_tracker.services.goal_service import GoalProgress, GoalService
from budget_tracker.ui.dialogs.contribution_dialog import ContributionDialog
from budget_tracker.ui.dialogs.goal_dialog import GoalDialog
from budget_tracker.ui.views.base import BaseView


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

    def __init__(self, progress: GoalProgress, parent=None):
        super().__init__(parent)
        self.setProperty("class", "card")
        self.setMinimumHeight(190)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._open_context)

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

        layout.addLayout(actions)

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

        if savings:
            self._host_layout.addWidget(self._section_label("Savings goals"))
            self._host_layout.addLayout(self._grid(savings))
        if debts:
            self._host_layout.addWidget(self._section_label("Debt payoff"))
            self._host_layout.addLayout(self._grid(debts))
        self._host_layout.addStretch(1)

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setProperty("class", "section")
        return lbl

    def _grid(self, items: Iterable[GoalProgress]) -> QGridLayout:
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(14)
        for i, p in enumerate(items):
            card = _GoalCard(p, parent=self._host)
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
        msg = QMessageBox(self)
        msg.setWindowTitle("Delete goal")
        msg.setText(f"Delete goal “{goal.name}”?")
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
        dlg = ContributionDialog(title, action, max_value=max_value, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            amt = dlg.amount_minor()
            if amt:
                self._service.contribute(goal.id, amt)
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
        dlg = ContributionDialog(title, "Withdraw", max_value=max_value, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            amt = dlg.amount_minor()
            if amt:
                self._service.contribute(goal.id, -amt)
                self.refresh()
