from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from budget_tracker.config import APP_DISPLAY_NAME
from budget_tracker.services.settings_service import SettingsService
from budget_tracker.ui.dialogs.transaction_dialog import TransactionDialog
from budget_tracker.ui.styles import apply_theme, available_themes
from budget_tracker.ui.views.base import BaseView
from budget_tracker.ui.views.budgets_view import BudgetsView
from budget_tracker.ui.views.goals_view import GoalsView
from budget_tracker.ui.views.home_view import HomeView
from budget_tracker.ui.views.settings_view import SettingsView
from budget_tracker.ui.views.subscriptions_view import SubscriptionsView
from budget_tracker.ui.views.transactions_view import TransactionsView
from budget_tracker.ui.widgets.nav_button import NavButton


@dataclass(frozen=True)
class NavSpec:
    icon: str
    label: str
    section: str  # "menu" | "more"


# Order matters — sidebar position + Ctrl+1..6 shortcut.
NAV: tuple[NavSpec, ...] = (
    NavSpec("\U0001F3E0", "Home",          "menu"),
    NavSpec("\U0001F4B8", "Transactions",  "menu"),
    NavSpec("\U0001F3AF", "Budgets",       "menu"),
    NavSpec("\U0001F3C6", "Goals",         "menu"),
    NavSpec("\U0001F501", "Subscriptions", "menu"),
    NavSpec("⚙",     "Settings",      "more"),
)


# ------------------------------------------------------------------
#  Sidebar
# ------------------------------------------------------------------

class Sidebar(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(232)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 22, 16, 18)
        root.setSpacing(0)

        root.addWidget(self._brand())
        root.addSpacing(28)

        self._buttons: list[NavButton] = []

        # Menu section
        root.addWidget(self._section_label("Menu"))
        root.addSpacing(6)
        for i, item in enumerate(NAV):
            if item.section != "menu":
                continue
            btn = NavButton(item.icon, item.label)
            self._buttons.append(btn)
            root.addWidget(btn)
            root.addSpacing(2)

        root.addStretch(1)

        # More section (Settings, future items)
        root.addWidget(self._section_label("More"))
        root.addSpacing(6)
        for item in NAV:
            if item.section != "more":
                continue
            btn = NavButton(item.icon, item.label)
            self._buttons.append(btn)
            root.addWidget(btn)
            root.addSpacing(2)

    @staticmethod
    def _brand() -> QFrame:
        wrap = QFrame()
        wrap.setObjectName("SidebarBrand")
        layout = QHBoxLayout(wrap)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(10)

        mark = QLabel("BT")
        mark.setObjectName("SidebarBrandMark")
        mark.setFixedSize(30, 30)

        text = QLabel(APP_DISPLAY_NAME)
        text.setObjectName("SidebarBrandText")

        layout.addWidget(mark)
        layout.addWidget(text, 1)
        return wrap

    @staticmethod
    def _section_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setProperty("class", "section")
        lbl.setContentsMargins(8, 0, 0, 0)
        return lbl

    def buttons(self) -> list[NavButton]:
        return self._buttons

    def set_active(self, index: int) -> None:
        for i, b in enumerate(self._buttons):
            b.set_active(i == index)


# ------------------------------------------------------------------
#  Top bar
# ------------------------------------------------------------------

class TopBar(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("TopBar")
        self.setFixedHeight(70)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(32, 0, 28, 0)
        layout.setSpacing(10)

        self.title = QLabel("")
        self.title.setObjectName("PageTitle")
        layout.addWidget(self.title)
        layout.addStretch(1)

        self.theme_btn = QPushButton("☾")  # ☾
        self.theme_btn.setProperty("class", "icon")
        self.theme_btn.setToolTip("Cycle theme")
        self.theme_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(self.theme_btn)

        self.add_btn = QPushButton("+ Add")
        self.add_btn.setProperty("class", "primary")
        self.add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_btn.setToolTip("Add (context-aware for the current view)")
        layout.addWidget(self.add_btn)


# ------------------------------------------------------------------
#  Main window
# ------------------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self, conn: sqlite3.Connection, settings: SettingsService) -> None:
        super().__init__()
        self.conn = conn
        self.settings = settings
        self.setWindowTitle(APP_DISPLAY_NAME)
        self.resize(1280, 820)
        self.setMinimumSize(960, 640)

        self.sidebar = Sidebar()
        self.topbar = TopBar()
        self.stack = QStackedWidget()

        self._views: list[BaseView] = [
            HomeView(conn),
            TransactionsView(conn),
            BudgetsView(conn),
            GoalsView(conn),
            SubscriptionsView(conn),
            SettingsView(conn),
        ]
        for v in self._views:
            self.stack.addWidget(v)

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        body_layout.addWidget(self.sidebar)

        right = QFrame()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        right_layout.addWidget(self.topbar)
        right_layout.addWidget(self.stack, 1)
        body_layout.addWidget(right, 1)

        self.setCentralWidget(body)

        # Wire up
        for i, btn in enumerate(self.sidebar.buttons()):
            btn.clicked.connect(lambda idx=i: self.set_active(idx))
        self.topbar.add_btn.clicked.connect(self._fire_primary_action)
        self.topbar.theme_btn.clicked.connect(self._toggle_theme)

        # Keyboard: Ctrl+1..N jump to view
        for i in range(len(self._views)):
            sc = QShortcut(QKeySequence(f"Ctrl+{i+1}"), self)
            sc.activated.connect(lambda idx=i: self.set_active(idx))

        # Global shortcuts
        QShortcut(QKeySequence("Ctrl+N"), self, activated=self._open_quick_add_transaction)
        QShortcut(QKeySequence("Ctrl+T"), self, activated=self._toggle_theme)
        QShortcut(QKeySequence("Ctrl+,"), self,
                  activated=lambda: self.set_active(len(self._views) - 1))

        # Tooltips on the sidebar buttons (with the matching shortcut hint)
        for i, btn in enumerate(self.sidebar.buttons()):
            view = self._views[i]
            btn.setToolTip(f"{view.title}  (Ctrl+{i+1})")

        self._restore_window_state()
        self.set_active(0)
        self._update_theme_icon()

    # ----- behaviour -----

    def set_active(self, index: int) -> None:
        index = max(0, min(index, len(self._views) - 1))
        self.stack.setCurrentIndex(index)
        self.sidebar.set_active(index)
        view = self._views[index]
        self.topbar.title.setText(view.title)
        self._sync_primary_button(view)
        view.refresh()

    def _sync_primary_button(self, view: BaseView) -> None:
        label: Optional[str] = view.primary_action_label
        self.topbar.add_btn.setVisible(bool(label))
        if label:
            self.topbar.add_btn.setText(label)

    def _fire_primary_action(self) -> None:
        idx = self.stack.currentIndex()
        view = self._views[idx]
        if view.primary_action_label:
            view.on_primary_action()

    def _toggle_theme(self) -> None:
        """Cycle through the available themes."""
        themes = available_themes()
        if not themes:
            return
        ids = [t.id for t in themes]
        current_id = self.settings.get_theme()
        idx = ids.index(current_id) if current_id in ids else 0
        new_id = ids[(idx + 1) % len(ids)]
        self.settings.set_theme(new_id)
        apply_theme(QApplication.instance(), new_id)  # type: ignore[arg-type]
        self._update_theme_icon()

    def _update_theme_icon(self) -> None:
        # Use sun glyph when on a dark theme (clicking moves toward light) and
        # moon when on a light theme.
        current_id = self.settings.get_theme()
        is_lightish = current_id == "light"
        self.topbar.theme_btn.setText("☾" if is_lightish else "☀")

    # ---- global add ----

    def _open_quick_add_transaction(self) -> None:
        dlg = TransactionDialog(self.conn, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            # Refresh whichever view is currently visible so the new
            # transaction shows up immediately.
            self._views[self.stack.currentIndex()].refresh()

    # ---- window state ----

    def _qsettings(self) -> QSettings:
        return QSettings()  # uses ApplicationName/OrgName set in main.py

    def _restore_window_state(self) -> None:
        s = self._qsettings()
        geo = s.value("window/geometry")
        if geo:
            self.restoreGeometry(geo)

    def closeEvent(self, ev) -> None:  # noqa: N802 (Qt naming)
        s = self._qsettings()
        s.setValue("window/geometry", self.saveGeometry())
        super().closeEvent(ev)
