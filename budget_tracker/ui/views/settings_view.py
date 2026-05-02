from __future__ import annotations

import shutil

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QAction, QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
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

from budget_tracker import __version__
from budget_tracker.config import data_dir, db_path
from budget_tracker.core import money
from budget_tracker.core.models import Account, Category
from budget_tracker.core.repositories.accounts import AccountRepository
from budget_tracker.core.repositories.categories import CategoryRepository
from budget_tracker.services.account_service import AccountService
from budget_tracker.services.db_location_service import move_database
from budget_tracker.services.settings_service import SettingsService
from budget_tracker.ui.dialogs.account_dialog import AccountDialog
from budget_tracker.ui.dialogs.category_dialog import CategoryDialog
from budget_tracker.ui.styles import apply_theme, available_themes
from budget_tracker.ui.views.base import BaseView
from budget_tracker.ui.widgets.progress_row import ColorDot
from budget_tracker.ui.widgets.section_card import SectionCard


_TYPE_LABELS = {
    "checking": "Checking",
    "savings":  "Savings",
    "credit":   "Credit card",
    "cash":     "Cash",
    "wallet":   "Wallet",
}


class SettingsView(BaseView):
    title = "Settings"
    primary_action_label = None  # No global "+" — sections own their own buttons.

    def __init__(self, conn, parent=None):
        super().__init__(conn, parent)
        self.settings = SettingsService(conn)
        self.account_repo = AccountRepository(conn)
        self.account_service = AccountService(conn)
        self.category_repo = CategoryRepository(conn)
        self._build()
        self.refresh()

    # ---------- UI ----------

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # IMPORTANT: every widget in this view is created with an explicit
        # parent. A parentless QWidget is a top-level window — even if it's
        # never .show()-ed, the moment it gets reparented its native handle
        # can briefly flash on Windows. Pass a parent at construction.
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        host = QWidget(scroll)
        self._host_layout = QVBoxLayout(host)
        self._host_layout.setContentsMargins(28, 22, 28, 28)
        self._host_layout.setSpacing(20)
        scroll.setWidget(host)
        outer.addWidget(scroll)

        # Sections — created lazily so refresh() can repopulate them.
        self._appearance_card = self._build_appearance_card(host)
        self._money_card = self._build_money_card(host)
        self._accounts_card = SectionCard("Accounts", "+ Add account", parent=host)
        self._accounts_card.action.clicked.connect(self._add_account)
        self._categories_card = SectionCard("Categories", "+ Add category", parent=host)
        self._categories_card.action.clicked.connect(self._add_category)
        self._data_card = self._build_data_card(host)
        self._about_card = self._build_about_card(host)

        for c in (
            self._appearance_card, self._money_card,
            self._accounts_card, self._categories_card,
            self._data_card, self._about_card,
        ):
            self._host_layout.addWidget(c)
        self._host_layout.addStretch(1)

    def _build_appearance_card(self, parent) -> SectionCard:
        card = SectionCard("Appearance", parent=parent)
        body = card.body_layout()

        row = QHBoxLayout()
        row.setSpacing(12)
        lbl = QLabel("Theme")
        lbl.setProperty("class", "h3")
        lbl.setMinimumWidth(140)
        self._theme_combo = QComboBox()
        self._theme_combo.setMinimumWidth(220)
        self._theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        row.addWidget(lbl)
        row.addWidget(self._theme_combo)
        row.addStretch(1)
        body.addLayout(row)

        self._theme_desc = QLabel("")
        self._theme_desc.setProperty("class", "subtle")
        self._theme_desc.setIndent(140 + 12)
        body.addWidget(self._theme_desc)

        return card

    def _build_money_card(self, parent) -> SectionCard:
        card = SectionCard("Money", parent=parent)
        body = card.body_layout()

        row = QHBoxLayout()
        row.setSpacing(12)
        lbl = QLabel("Currency")
        lbl.setProperty("class", "h3")
        lbl.setMinimumWidth(140)
        self._currency_combo = QComboBox()
        for code in money.supported_codes():
            sym = money.Currency.from_code(code).symbol
            self._currency_combo.addItem(f"{code}  ·  {sym}", code)
        self._currency_combo.setMinimumWidth(220)
        self._currency_combo.currentIndexChanged.connect(self._on_currency_changed)
        row.addWidget(lbl)
        row.addWidget(self._currency_combo)
        row.addStretch(1)
        body.addLayout(row)

        note = QLabel(
            "Changes the displayed symbol and grouping. Existing amounts are "
            "not converted — they stay at their stored value."
        )
        note.setProperty("class", "subtle")
        note.setWordWrap(True)
        note.setIndent(140 + 12)
        body.addWidget(note)
        return card

    def _build_data_card(self, parent) -> SectionCard:
        card = SectionCard("Data", parent=parent)
        body = card.body_layout()

        location_label = QLabel("Database location", card)
        location_label.setProperty("class", "h3")
        body.addWidget(location_label)

        # Refreshable path label — set in refresh() so it stays accurate
        # if the user moves the DB without restarting (we still prompt for
        # restart, but this keeps the label honest in the meantime).
        self._db_path_lbl = QLabel(str(db_path()), card)
        self._db_path_lbl.setProperty("class", "subtle")
        self._db_path_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._db_path_lbl.setWordWrap(True)
        body.addWidget(self._db_path_lbl)

        location_row = QHBoxLayout()
        location_row.setSpacing(8)
        move = QPushButton("Move database…", card)
        move.setProperty("class", "secondary")
        move.setToolTip("Choose a new folder to keep your database in (e.g. OneDrive). The app will close after moving.")
        move.clicked.connect(self._move_db)
        open_folder = QPushButton("Open data folder", card)
        open_folder.setProperty("class", "ghost")
        open_folder.clicked.connect(self._open_data_folder)
        location_row.addWidget(move)
        location_row.addWidget(open_folder)
        location_row.addStretch(1)
        body.addLayout(location_row)

        body.addSpacing(6)

        backup_row = QHBoxLayout()
        backup_row.setSpacing(8)
        export = QPushButton("Export database…", card)
        export.setProperty("class", "secondary")
        export.clicked.connect(self._export_db)
        restore = QPushButton("Import / restore…", card)
        restore.setProperty("class", "secondary")
        restore.clicked.connect(self._import_db)
        backup_row.addWidget(export)
        backup_row.addWidget(restore)
        backup_row.addStretch(1)
        body.addLayout(backup_row)
        return card

    def _build_about_card(self, parent) -> SectionCard:
        card = SectionCard("About", parent=parent)
        body = card.body_layout()
        name = QLabel("Budget Tracker")
        name.setProperty("class", "h3")
        ver = QLabel(f"Version {__version__}")
        ver.setProperty("class", "subtle")
        info = QLabel("A modern, locally-stored personal budget tracker built with PySide 6.")
        info.setProperty("class", "muted")
        info.setWordWrap(True)
        body.addWidget(name)
        body.addWidget(ver)
        body.addSpacing(2)
        body.addWidget(info)
        return card

    # ---------- data binding ----------

    def refresh(self) -> None:
        self._populate_themes()
        self._populate_currency()
        self._populate_accounts()
        self._populate_categories()

    def _populate_themes(self) -> None:
        self._theme_combo.blockSignals(True)
        self._theme_combo.clear()
        themes = available_themes()
        current_id = self.settings.get_theme()
        for t in themes:
            self._theme_combo.addItem(t.name, t.id)
        idx = next((i for i, t in enumerate(themes) if t.id == current_id), 0)
        self._theme_combo.setCurrentIndex(idx)
        self._theme_combo.blockSignals(False)
        self._update_theme_description(themes, idx)

    def _update_theme_description(self, themes, idx: int) -> None:
        if 0 <= idx < len(themes):
            self._theme_desc.setText(themes[idx].description or "")
        else:
            self._theme_desc.setText("")

    def _populate_currency(self) -> None:
        self._currency_combo.blockSignals(True)
        current = self.settings.get_currency_code()
        idx = self._currency_combo.findData(current)
        if idx >= 0:
            self._currency_combo.setCurrentIndex(idx)
        self._currency_combo.blockSignals(False)

    def _populate_accounts(self) -> None:
        body = self._accounts_card.body_layout()
        self._accounts_card.clear_body()
        accounts = self.account_repo.list(include_archived=True)
        if not accounts:
            empty = QLabel("No accounts yet. Add one above to start tracking transactions.")
            empty.setProperty("class", "muted")
            empty.setWordWrap(True)
            body.addWidget(empty)
            return
        balances = self.account_service.balances()
        for a in accounts:
            body.addWidget(self._account_row(a, balances.get(a.id, a.opening_balance)))

    def _populate_categories(self) -> None:
        body = self._categories_card.body_layout()
        self._categories_card.clear_body()
        cats = self.category_repo.list(include_archived=True)
        if not cats:
            empty = QLabel("No categories yet. Add expense or income categories above.")
            empty.setProperty("class", "muted")
            empty.setWordWrap(True)
            body.addWidget(empty)
            return

        # Render parents first, then their children indented underneath.
        # Orphan rows (parent_id pointing nowhere usable) fall through to
        # the bottom so they remain visible/editable.
        children_by_parent: dict[int, list[Category]] = {}
        top_level: list[Category] = []
        for c in cats:
            if c.parent_id is None:
                top_level.append(c)
            else:
                children_by_parent.setdefault(c.parent_id, []).append(c)

        top_level.sort(key=lambda c: (c.kind, c.name.lower()))
        rendered: set[int] = set()
        for top in top_level:
            body.addWidget(self._category_row(top, indent=False))
            rendered.add(top.id)
            kids = sorted(children_by_parent.get(top.id, []), key=lambda c: c.name.lower())
            for kid in kids:
                body.addWidget(self._category_row(kid, indent=True))
                rendered.add(kid.id)

        # Orphans (subcategory whose parent is missing or filtered)
        for c in cats:
            if c.id in rendered:
                continue
            body.addWidget(self._category_row(c, indent=False))

    # ---------- row factories ----------

    def _account_row(self, a: Account, running_balance: int) -> QFrame:
        # Parent every widget at construction. A parentless QWidget — even a
        # tiny QLabel or QPushButton — is technically a top-level window
        # until reparented; on some Windows display configurations Qt briefly
        # registers a native HWND for it which flashes a small grey box.
        row = QFrame(self._accounts_card)
        row.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(10)

        name = QLabel(a.name, row)
        name.setProperty("class", "h3")
        if a.archived:
            name.setStyleSheet("color: #6B6B7A;")

        type_lbl = QLabel(_TYPE_LABELS.get(a.type, a.type), row)
        type_lbl.setProperty("class", "chip")

        # Right-aligned balance column: running balance on top, opening
        # balance underneath as a subtle hint (only when non-zero so the
        # row stays compact for fresh accounts).
        balance_box = QFrame(row)
        balance_layout = QVBoxLayout(balance_box)
        balance_layout.setContentsMargins(0, 0, 0, 0)
        balance_layout.setSpacing(0)

        balance = QLabel(money.format_amount(running_balance), balance_box)
        balance.setProperty("class", "h3")
        balance.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        balance_layout.addWidget(balance)

        if a.opening_balance:
            opening_lbl = QLabel(
                f"Opening {money.format_amount(a.opening_balance)}",
                balance_box,
            )
            opening_lbl.setProperty("class", "subtle")
            opening_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            balance_layout.addWidget(opening_lbl)

        archived_chip = QLabel("Archived", row)
        archived_chip.setProperty("class", "chip")
        archived_chip.setVisible(a.archived)

        edit = QPushButton("Edit", row)
        edit.setProperty("class", "ghost")
        edit.clicked.connect(lambda _checked=False, acct=a: self._edit_account(acct))

        archive = QPushButton("Restore" if a.archived else "Archive", row)
        archive.setProperty("class", "ghost")
        archive.clicked.connect(lambda _checked=False, acct=a: self._toggle_account_archive(acct))

        layout.addWidget(name)
        layout.addWidget(type_lbl)
        layout.addWidget(archived_chip)
        layout.addStretch(1)
        layout.addWidget(balance_box)
        layout.addWidget(edit)
        layout.addWidget(archive)
        return row

    def _category_row(self, c: Category, *, indent: bool = False) -> QFrame:
        row = QFrame(self._categories_card)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(28 if indent else 0, 4, 0, 4)
        layout.setSpacing(10)

        if indent:
            tree_glyph = QLabel("│", row)
            tree_glyph.setProperty("class", "subtle")
            tree_glyph.setFixedWidth(10)
            layout.addWidget(tree_glyph)

        layout.addWidget(ColorDot(c.color, size=8 if indent else 10, parent=row))
        icon_lbl = QLabel(c.icon, row)
        icon_lbl.setFixedWidth(20)
        layout.addWidget(icon_lbl)

        name = QLabel(c.name, row)
        name.setProperty("class", "h3" if not indent else "muted")
        if c.archived:
            name.setStyleSheet("color: #6B6B7A;")
        layout.addWidget(name)

        kind_lbl = QLabel(c.kind.capitalize(), row)
        kind_lbl.setProperty("class", "chip")
        kind_lbl.setVisible(not indent)
        layout.addWidget(kind_lbl)

        if c.archived:
            archived_chip = QLabel("Archived", row)
            archived_chip.setProperty("class", "chip")
            layout.addWidget(archived_chip)

        layout.addStretch(1)

        edit = QPushButton("Edit", row)
        edit.setProperty("class", "ghost")
        edit.clicked.connect(lambda _checked=False, cat=c: self._edit_category(cat))

        archive = QPushButton("Restore" if c.archived else "Archive", row)
        archive.setProperty("class", "ghost")
        archive.clicked.connect(lambda _checked=False, cat=c: self._toggle_category_archive(cat))

        layout.addWidget(edit)
        layout.addWidget(archive)
        return row

    # ---------- handlers ----------

    def _on_theme_changed(self, idx: int) -> None:
        theme_id = self._theme_combo.currentData()
        if not theme_id:
            return
        self.settings.set_theme(theme_id)
        apply_theme(QApplication.instance(), theme_id)  # type: ignore[arg-type]
        self._update_theme_description(available_themes(), idx)

    def _on_currency_changed(self, _idx: int) -> None:
        code = self._currency_combo.currentData()
        if not code:
            return
        self.settings.set_currency(code)
        # Other views read money.format_amount on next refresh — Settings's
        # own row labels already render the new symbol on full refresh.
        self.refresh()

    # ---- account actions ----

    def _add_account(self) -> None:
        dlg = AccountDialog(self.conn, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._populate_accounts()

    def _edit_account(self, a: Account) -> None:
        dlg = AccountDialog(self.conn, account=a, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._populate_accounts()

    def _toggle_account_archive(self, a: Account) -> None:
        a.archived = not a.archived
        self.account_repo.update(a)
        self._populate_accounts()

    # ---- category actions ----

    def _add_category(self) -> None:
        dlg = CategoryDialog(self.conn, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._populate_categories()

    def _edit_category(self, c: Category) -> None:
        dlg = CategoryDialog(self.conn, category=c, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._populate_categories()

    def _toggle_category_archive(self, c: Category) -> None:
        c.archived = not c.archived
        self.category_repo.update(c)
        self._populate_categories()

    # ---- data actions ----

    def _move_db(self) -> None:
        target_dir = QFileDialog.getExistingDirectory(
            self,
            "Choose a folder to keep the database in",
            str(db_path().parent),
            QFileDialog.Option.ShowDirsOnly,
        )
        if not target_dir:
            return

        try:
            new_path = move_database(target_dir)
        except (FileExistsError, FileNotFoundError, ValueError) as e:
            QMessageBox.warning(self, "Couldn't move database", str(e))
            return
        except OSError as e:
            QMessageBox.critical(self, "Move failed", str(e))
            return

        # Reflect the new path immediately, even though we ask the user to
        # restart — until restart the live connection still points at the
        # old file.
        self._db_path_lbl.setText(str(new_path))

        info = QMessageBox(self)
        info.setWindowTitle("Database moved")
        info.setIcon(QMessageBox.Icon.Information)
        info.setText(
            f"Your database has been moved to:\n{new_path}\n\n"
            "The app will now close — relaunch to start using the new location."
        )
        info.setStandardButtons(QMessageBox.StandardButton.Ok)
        info.exec()
        QApplication.instance().quit()

    def _export_db(self) -> None:
        target, _ = QFileDialog.getSaveFileName(
            self,
            "Export database",
            str(data_dir() / "budget-tracker-backup.sqlite3"),
            "SQLite (*.sqlite3 *.db);;All files (*.*)",
        )
        if not target:
            return
        try:
            shutil.copy2(db_path(), target)
        except OSError as e:
            QMessageBox.critical(self, "Export failed", str(e))
            return
        QMessageBox.information(self, "Exported", f"Database copied to:\n{target}")

    def _import_db(self) -> None:
        msg = QMessageBox(self)
        msg.setWindowTitle("Replace database?")
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setText(
            "Importing replaces the current database file. Your existing data will be "
            "overwritten and the app will close so the new file can be loaded on next launch.\n\n"
            "Continue?"
        )
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        msg.setDefaultButton(QMessageBox.StandardButton.Cancel)
        if msg.exec() != QMessageBox.StandardButton.Yes:
            return

        source, _ = QFileDialog.getOpenFileName(
            self,
            "Import database",
            str(data_dir()),
            "SQLite (*.sqlite3 *.db);;All files (*.*)",
        )
        if not source:
            return
        try:
            shutil.copy2(source, db_path())
        except OSError as e:
            QMessageBox.critical(self, "Import failed", str(e))
            return
        QMessageBox.information(
            self,
            "Imported",
            "Database replaced. The app will now close — please reopen it.",
        )
        QApplication.quit()

    def _open_data_folder(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(data_dir())))
