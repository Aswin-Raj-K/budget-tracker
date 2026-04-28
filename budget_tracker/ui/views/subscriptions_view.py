from __future__ import annotations

from datetime import date
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from budget_tracker.core import money
from budget_tracker.core.models import Subscription
from budget_tracker.core.repositories.subscriptions import SubscriptionRepository
from budget_tracker.services.subscription_service import (
    SubscriptionService,
    monthly_equivalent,
)
from budget_tracker.ui.dialogs.subscription_dialog import SubscriptionDialog
from budget_tracker.ui.views.base import BaseView

_MONTHS = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _fmt_date(d: date) -> str:
    return f"{d.day:02d} {_MONTHS[d.month]} {d.year}"


class SubscriptionsView(BaseView):
    title = "Subscriptions"
    primary_action_label = "+ Add Subscription"

    def __init__(self, conn, parent=None):
        super().__init__(conn, parent)
        self._repo = SubscriptionRepository(conn)
        self._service = SubscriptionService(conn)
        self._displayed: list[Subscription] = []

        self._build()
        self.refresh()

    # ---------- UI ----------

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 22, 28, 24)
        outer.setSpacing(12)

        # Hero summary
        hero = QHBoxLayout()
        hero.setSpacing(14)

        self._total_lbl = QLabel("—")
        self._total_lbl.setProperty("class", "kpi-value")

        total_caption = QLabel("Estimated monthly cost".upper())
        total_caption.setProperty("class", "kpi-label")

        sub_total_box = QVBoxLayout()
        sub_total_box.setSpacing(2)
        sub_total_box.addWidget(total_caption)
        sub_total_box.addWidget(self._total_lbl)

        self._yearly_lbl = QLabel("")
        self._yearly_lbl.setProperty("class", "muted")

        hero.addLayout(sub_total_box)
        hero.addStretch(1)
        hero.addWidget(self._yearly_lbl, alignment=Qt.AlignmentFlag.AlignBottom)
        outer.addLayout(hero)

        # Table
        self._table = QTableWidget()
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels(
            ["Name", "Amount", "Cycle", "Next billing", "Monthly equivalent", "Active"]
        )
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setShowGrid(False)
        self._table.setAlternatingRowColors(True)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._open_context_menu)
        self._table.doubleClicked.connect(lambda _i: self._edit_selected())

        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        outer.addWidget(self._table, 1)

        self._empty = QLabel(
            'No subscriptions tracked yet.\nClick “+ Add Subscription” to start.'
        )
        self._empty.setProperty("class", "muted")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setVisible(False)
        outer.addWidget(self._empty, 1)

    # ---------- data binding ----------

    def refresh(self) -> None:
        summary = self._service.summary(active_only=False)
        active_summary = self._service.summary(active_only=True)
        self._displayed = summary.items

        self._total_lbl.setText(money.format_amount(active_summary.total_monthly))
        self._yearly_lbl.setText(
            f"That's about {money.format_amount(active_summary.total_monthly * 12)} per year"
            if active_summary.total_monthly > 0 else ""
        )

        self._table.setVisible(bool(self._displayed))
        self._empty.setVisible(not self._displayed)

        self._table.setRowCount(len(self._displayed))
        for row, sub in enumerate(self._displayed):
            name = QTableWidgetItem(sub.name)
            if not sub.active:
                name.setForeground(QBrush(QColor("#6B6B7A")))
            self._table.setItem(row, 0, name)

            amt = QTableWidgetItem(money.format_amount(sub.amount))
            amt.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._table.setItem(row, 1, amt)

            self._table.setItem(row, 2, QTableWidgetItem(sub.cycle.capitalize()))
            self._table.setItem(row, 3, QTableWidgetItem(_fmt_date(sub.next_billing_date)))

            month_eq = monthly_equivalent(sub)
            me_item = QTableWidgetItem(money.format_amount(month_eq))
            me_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._table.setItem(row, 4, me_item)

            active_item = QTableWidgetItem("Yes" if sub.active else "No")
            active_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if not sub.active:
                active_item.setForeground(QBrush(QColor("#6B6B7A")))
            self._table.setItem(row, 5, active_item)

    # ---------- actions ----------

    def on_primary_action(self) -> None:
        self._open_dialog(None)

    def _open_dialog(self, sub: Optional[Subscription]) -> None:
        dlg = SubscriptionDialog(self.conn, subscription=sub, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _selected(self) -> Optional[Subscription]:
        row = self._table.currentRow()
        if row < 0 or row >= len(self._displayed):
            return None
        return self._displayed[row]

    def _edit_selected(self) -> None:
        s = self._selected()
        if s is not None:
            self._open_dialog(s)

    def _delete_selected(self) -> None:
        s = self._selected()
        if s is None or s.id is None:
            return
        msg = QMessageBox(self)
        msg.setWindowTitle("Delete subscription")
        msg.setText(f"Delete the subscription “{s.name}”?")
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        msg.setDefaultButton(QMessageBox.StandardButton.Cancel)
        if msg.exec() == QMessageBox.StandardButton.Yes:
            self._repo.delete(s.id)
            self.refresh()

    def _toggle_selected_active(self) -> None:
        s = self._selected()
        if s is None or s.id is None:
            return
        s.active = not s.active
        self._repo.update(s)
        self.refresh()

    def _open_context_menu(self, pos) -> None:
        s = self._selected()
        if s is None:
            return
        menu = QMenu(self)
        edit = QAction("Edit", self)
        edit.triggered.connect(self._edit_selected)
        toggle = QAction("Mark inactive" if s.active else "Mark active", self)
        toggle.triggered.connect(self._toggle_selected_active)
        delete = QAction("Delete", self)
        delete.triggered.connect(self._delete_selected)
        menu.addAction(edit)
        menu.addAction(toggle)
        menu.addSeparator()
        menu.addAction(delete)
        menu.exec(self._table.viewport().mapToGlobal(pos))

    def keyPressEvent(self, ev) -> None:  # noqa: N802 (Qt naming)
        if ev.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            if self._selected() is not None:
                self._delete_selected()
                return
        super().keyPressEvent(ev)
