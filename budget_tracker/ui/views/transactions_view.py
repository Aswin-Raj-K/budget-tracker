from __future__ import annotations

from datetime import date
from typing import Optional

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QAction, QBrush, QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDateEdit,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from budget_tracker.core import money
from budget_tracker.core.models import Account, Category, Transaction
from budget_tracker.core.repositories.accounts import AccountRepository
from budget_tracker.core.repositories.categories import CategoryRepository
from budget_tracker.core.repositories.transactions import TransactionRepository
from budget_tracker.services.selection_summary import SelectionSummary, summarize
from budget_tracker.ui.dialogs.transaction_dialog import TransactionDialog
from budget_tracker.ui.views.base import BaseView

_MONTHS = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# A sane sentinel for "no filter" — Qt's default minimumDate is 1752-09-14
# (the British Gregorian-calendar switch), where the popup opens in a
# month that's missing 11 days. Use 1990-01-01 instead so the calendar is
# always sensible if anything else falls back to the minimum.
_FILTER_MIN = QDate(1990, 1, 1)


class _FilterDateEdit(QDateEdit):
    """QDateEdit used as an optional date filter.

    The minimum date doubles as a "no filter" sentinel and the
    setSpecialValueText placeholder ("From"/"To") shows in the field
    until the user picks a real date. The first time the user clicks
    the field to open the calendar, jump to today so the popup lands
    on the current month rather than on the 1990-01 sentinel.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumDate(_FILTER_MIN)
        self.setCalendarPopup(True)
        self.setDate(_FILTER_MIN)

    def mousePressEvent(self, ev) -> None:  # noqa: N802 (Qt naming)
        if self.date() == self.minimumDate():
            self.setDate(QDate.currentDate())
        super().mousePressEvent(ev)

ALL = -1  # sentinel value for "no filter"


def _fmt_date(d: date) -> str:
    return f"{d.day:02d} {_MONTHS[d.month]} {d.year}"


def _render_status_label(total_count: int, summary: SelectionSummary) -> str:
    """Compose the status line above the Transactions table.

    Layout:
      - "23 transactions" when nothing's selected.
      - "23 transactions  ·  N selected  ·  <details>" otherwise, where
        <details> is per-kind for homogeneous selections, "Net ±X (income · expense)"
        for mixed income+expense, and an extra "· N transfer" tail
        whenever transfers are mixed in.

    Pure string composition — kept separate from the view so it can be
    unit-tested without a QApplication.
    """
    base = f"{total_count} transaction{'s' if total_count != 1 else ''}"
    if summary.count == 0:
        return base

    parts = [base, f"{summary.count} selected"]
    parts.extend(_summary_fragments(summary))
    return "  ·  ".join(parts)


def _summary_fragments(summary: SelectionSummary) -> list[str]:
    """The trailing ' · '-separated chunks describing the selection."""
    has_income = summary.has_income
    has_expense = summary.has_expense
    has_transfer = summary.has_transfer

    fragments: list[str] = []
    if has_income and not has_expense:
        fragments.append(f"{money.format_amount(summary.income_total)} income")
    elif has_expense and not has_income:
        fragments.append(f"{money.format_amount(summary.expense_total)} expense")
    elif has_income and has_expense:
        sign = "−" if summary.net < 0 else "+" if summary.net > 0 else ""
        net_str = money.format_amount(abs(summary.net))
        fragments.append(f"Net {sign}{net_str}")
        fragments.append(
            f"{money.format_amount(summary.income_total)} income  ·  "
            f"{money.format_amount(summary.expense_total)} expense"
        )
    elif has_transfer and not has_income and not has_expense:
        fragments.append(f"{money.format_amount(summary.transfer_total)} transfer")
        return fragments  # transfers-only — already covered

    if has_transfer and (has_income or has_expense):
        fragments.append(f"{money.format_amount(summary.transfer_total)} transfer")
    return fragments


class TransactionsView(BaseView):
    title = "Transactions"
    primary_action_label = "+ Add Transaction"

    def __init__(self, conn, parent=None):
        super().__init__(conn, parent)
        self._tx_repo = TransactionRepository(conn)
        self._account_repo = AccountRepository(conn)
        self._category_repo = CategoryRepository(conn)

        self._cached_accounts: list[Account] = []
        self._cached_categories: list[Category] = []
        self._displayed: list[Transaction] = []

        self._build()
        self.refresh()

        # Ctrl+F focuses the note search box (only fires while this view
        # has the focus chain, thanks to WidgetWithChildrenShortcut).
        sc = QShortcut(QKeySequence("Ctrl+F"), self)
        sc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        sc.activated.connect(lambda: (self._search.setFocus(), self._search.selectAll()))

    # ---------- UI ----------

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 22, 28, 24)
        outer.setSpacing(14)

        # Filter bar
        bar = QHBoxLayout()
        bar.setSpacing(8)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search note…")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self.refresh)
        bar.addWidget(self._search, 2)

        self._account_filter = QComboBox()
        self._account_filter.currentIndexChanged.connect(self.refresh)
        bar.addWidget(self._account_filter, 1)

        self._category_filter = QComboBox()
        self._category_filter.currentIndexChanged.connect(self.refresh)
        bar.addWidget(self._category_filter, 1)

        self._kind_filter = QComboBox()
        self._kind_filter.addItem("All types", ALL)
        self._kind_filter.addItem("Expense", "expense")
        self._kind_filter.addItem("Income", "income")
        self._kind_filter.addItem("Transfer", "transfer")
        self._kind_filter.currentIndexChanged.connect(self.refresh)
        bar.addWidget(self._kind_filter)

        self._from_date = _FilterDateEdit()
        self._from_date.setDisplayFormat("dd MMM yy")
        self._from_date.setSpecialValueText("From")
        self._from_date.dateChanged.connect(self.refresh)
        bar.addWidget(self._from_date)

        self._to_date = _FilterDateEdit()
        self._to_date.setDisplayFormat("dd MMM yy")
        self._to_date.setSpecialValueText("To")
        self._to_date.dateChanged.connect(self.refresh)
        bar.addWidget(self._to_date)

        reset = QPushButton("Reset")
        reset.setProperty("class", "ghost")
        reset.clicked.connect(self._reset_filters)
        bar.addWidget(reset)

        outer.addLayout(bar)

        # Count label
        self._count_label = QLabel("")
        self._count_label.setProperty("class", "subtle")
        outer.addWidget(self._count_label)

        # Table
        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(["Date", "Account", "Category", "Note", "Amount"])
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        # Multi-select with Ctrl-click / Shift-click / drag / Ctrl+A. The
        # status label above the table aggregates the selected rows.
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._table.itemSelectionChanged.connect(self._on_selection_changed)
        self._table.setShowGrid(False)
        self._table.setAlternatingRowColors(True)
        self._table.setSortingEnabled(False)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._open_context_menu)
        self._table.doubleClicked.connect(lambda _idx: self._edit_selected())

        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)

        outer.addWidget(self._table, 1)

        # Empty state placeholder (we hide table when used)
        self._empty = QLabel(
            "No transactions match these filters.\nAdd one with “+ Add Transaction”."
        )
        self._empty.setProperty("class", "muted")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setVisible(False)
        outer.addWidget(self._empty, 1)

    # ---------- filters ----------

    def _reset_filters(self) -> None:
        self._search.blockSignals(True)
        self._account_filter.blockSignals(True)
        self._category_filter.blockSignals(True)
        self._kind_filter.blockSignals(True)
        self._from_date.blockSignals(True)
        self._to_date.blockSignals(True)

        self._search.clear()
        self._account_filter.setCurrentIndex(0)
        self._category_filter.setCurrentIndex(0)
        self._kind_filter.setCurrentIndex(0)
        self._from_date.setDate(self._from_date.minimumDate())
        self._to_date.setDate(self._to_date.minimumDate())

        for w in (self._search, self._account_filter, self._category_filter,
                  self._kind_filter, self._from_date, self._to_date):
            w.blockSignals(False)
        self.refresh()

    def _reload_filter_options(self) -> None:
        # Accounts
        prev_acc = self._account_filter.currentData() if self._account_filter.count() else ALL
        self._account_filter.blockSignals(True)
        self._account_filter.clear()
        self._account_filter.addItem("All accounts", ALL)
        self._cached_accounts = self._account_repo.list()
        for a in self._cached_accounts:
            self._account_filter.addItem(a.name, a.id)
        idx = self._account_filter.findData(prev_acc)
        self._account_filter.setCurrentIndex(idx if idx >= 0 else 0)
        self._account_filter.blockSignals(False)

        # Categories — hierarchical: each parent followed by its
        # subcategories, indented with a thin vertical guide.
        prev_cat = self._category_filter.currentData() if self._category_filter.count() else ALL
        self._category_filter.blockSignals(True)
        self._category_filter.clear()
        self._category_filter.addItem("All categories", ALL)
        self._cached_categories = self._category_repo.list()

        children_by_parent: dict[int, list[Category]] = {}
        top_level: list[Category] = []
        for c in self._cached_categories:
            if c.parent_id is None:
                top_level.append(c)
            else:
                children_by_parent.setdefault(c.parent_id, []).append(c)
        top_level.sort(key=lambda c: (c.kind, c.name.lower()))
        rendered: set[int] = set()
        for top in top_level:
            self._category_filter.addItem(top.name, top.id)
            rendered.add(top.id)
            for kid in sorted(children_by_parent.get(top.id, []), key=lambda c: c.name.lower()):
                self._category_filter.addItem(f"   │  {kid.name}", kid.id)
                rendered.add(kid.id)
        # Orphan subcategories (parent missing/archived).
        for c in self._cached_categories:
            if c.id not in rendered:
                self._category_filter.addItem(c.name, c.id)

        idx = self._category_filter.findData(prev_cat)
        self._category_filter.setCurrentIndex(idx if idx >= 0 else 0)
        self._category_filter.blockSignals(False)

    def _current_filters(self) -> dict:
        kwargs: dict = {}
        text = (self._search.text() or "").strip()
        if text:
            kwargs["text"] = text
        acc = self._account_filter.currentData()
        if acc not in (None, ALL):
            kwargs["account_id"] = acc
        cat = self._category_filter.currentData()
        if cat not in (None, ALL):
            kwargs["category_id"] = cat
        kind = self._kind_filter.currentData()
        if kind not in (None, ALL):
            kwargs["kind"] = kind

        if self._from_date.date() != self._from_date.minimumDate():
            qd = self._from_date.date()
            kwargs["start"] = date(qd.year(), qd.month(), qd.day())
        if self._to_date.date() != self._to_date.minimumDate():
            qd = self._to_date.date()
            kwargs["end"] = date(qd.year(), qd.month(), qd.day())

        return kwargs

    # ---------- data binding ----------

    def refresh(self) -> None:
        self._reload_filter_options()
        kwargs = self._current_filters()
        self._displayed = self._tx_repo.list(**kwargs)

        self._table.setVisible(bool(self._displayed))
        self._empty.setVisible(not self._displayed)

        # refresh() rebuilds the rows so any prior selection is moot. Update
        # the label using an empty summary; if the user then selects rows,
        # _on_selection_changed will recompute.
        self._update_status_label(SelectionSummary(0, 0, 0, 0))

        accounts_by_id = {a.id: a for a in self._cached_accounts}
        cats_by_id = {c.id: c for c in self._cached_categories}

        self._table.setRowCount(len(self._displayed))
        for row, tx in enumerate(self._displayed):
            self._table.setItem(row, 0, QTableWidgetItem(_fmt_date(tx.occurred_on)))

            acc = accounts_by_id.get(tx.account_id)
            self._table.setItem(row, 1, QTableWidgetItem(acc.name if acc else "—"))

            cat = cats_by_id.get(tx.category_id) if tx.category_id else None
            if cat is None:
                label = "Transfer" if tx.kind == "transfer" else "Uncategorised"
            elif cat.parent_id is not None:
                # Subcategory — render with its parent for context, e.g.
                # "Groceries / Chicken".
                parent = cats_by_id.get(cat.parent_id)
                label = f"{parent.name} / {cat.name}" if parent else cat.name
            else:
                label = cat.name
            cat_item = QTableWidgetItem(label)
            if cat is not None:
                cat_item.setForeground(QBrush(QColor(cat.color)))
            self._table.setItem(row, 2, cat_item)

            self._table.setItem(row, 3, QTableWidgetItem(tx.note or ""))

            sign = "-" if tx.kind == "expense" else "+" if tx.kind == "income" else ""
            amt_item = QTableWidgetItem(f"{sign}{money.format_amount(tx.amount)}")
            amt_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if tx.kind == "expense":
                amt_item.setForeground(QBrush(QColor("#F87171")))
            elif tx.kind == "income":
                amt_item.setForeground(QBrush(QColor("#34D399")))
            self._table.setItem(row, 4, amt_item)

    # ---------- actions ----------

    def on_primary_action(self) -> None:
        self._open_dialog(None)

    def _open_dialog(self, transaction: Optional[Transaction]) -> None:
        dlg = TransactionDialog(self.conn, transaction=transaction, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _selected_transaction(self) -> Optional[Transaction]:
        row = self._table.currentRow()
        if row < 0 or row >= len(self._displayed):
            return None
        return self._displayed[row]

    def _selected_transactions(self) -> list[Transaction]:
        rows = self._table.selectionModel().selectedRows()
        out: list[Transaction] = []
        for idx in rows:
            r = idx.row()
            if 0 <= r < len(self._displayed):
                out.append(self._displayed[r])
        return out

    def _on_selection_changed(self) -> None:
        self._update_status_label(summarize(self._selected_transactions()))

    def _update_status_label(self, summary: SelectionSummary) -> None:
        self._count_label.setText(_render_status_label(len(self._displayed), summary))

    def _edit_selected(self) -> None:
        tx = self._selected_transaction()
        if tx is not None:
            self._open_dialog(tx)

    def _delete_selected(self) -> None:
        tx = self._selected_transaction()
        if tx is None or tx.id is None:
            return
        msg = QMessageBox(self)
        msg.setWindowTitle("Delete transaction")
        msg.setText(
            f"Delete this {tx.kind} of "
            f"{money.format_amount(tx.amount)} on {_fmt_date(tx.occurred_on)}?"
        )
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        msg.setDefaultButton(QMessageBox.StandardButton.Cancel)
        if msg.exec() == QMessageBox.StandardButton.Yes:
            self._tx_repo.delete(tx.id)
            self.refresh()

    def _open_context_menu(self, pos) -> None:
        if self._selected_transaction() is None:
            return
        menu = QMenu(self)
        edit = QAction("Edit", self)
        edit.triggered.connect(self._edit_selected)
        delete = QAction("Delete", self)
        delete.triggered.connect(self._delete_selected)
        menu.addAction(edit)
        menu.addSeparator()
        menu.addAction(delete)
        menu.exec(self._table.viewport().mapToGlobal(pos))

    def keyPressEvent(self, ev) -> None:  # noqa: N802 (Qt naming)
        if ev.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            if self._selected_transaction() is not None:
                self._delete_selected()
                return
        super().keyPressEvent(ev)
