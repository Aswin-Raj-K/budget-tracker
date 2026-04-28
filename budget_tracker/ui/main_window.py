from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from budget_tracker.config import APP_DISPLAY_NAME
from budget_tracker.services.settings_service import SettingsService
from budget_tracker.ui.theme import apply_theme
from budget_tracker.ui.views.base import BaseView
from budget_tracker.ui.views.budgets_view import BudgetsView
from budget_tracker.ui.views.goals_view import GoalsView
from budget_tracker.ui.views.home_view import HomeView
from budget_tracker.ui.views.settings_view import SettingsView
from budget_tracker.ui.views.subscriptions_view import SubscriptionsView
from budget_tracker.ui.views.transactions_view import TransactionsView


@dataclass(frozen=True)
class NavItem:
    icon: str
    label: str


# Order matters — sidebar position + Ctrl+1..6 shortcut.
NAV_ITEMS: tuple[NavItem, ...] = (
    NavItem("\U0001F3E0", "Home"),
    NavItem("\U0001F4B8", "Transactions"),
    NavItem("\U0001F3AF", "Budgets"),
    NavItem("\U0001F3C6", "Goals"),
    NavItem("\U0001F501", "Subscriptions"),
    NavItem("⚙️", "Settings"),
)


class Sidebar(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(220)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 22, 16, 18)
        layout.setSpacing(4)

        brand = QLabel(APP_DISPLAY_NAME)
        brand.setProperty("class", "h2")
        layout.addWidget(brand)
        layout.addSpacing(18)

        self._buttons: list[QPushButton] = []
        for i, item in enumerate(NAV_ITEMS):
            if item.label == "Settings":
                layout.addStretch(1)
            btn = QPushButton(f"  {item.icon}   {item.label}")
            btn.setProperty("class", "nav")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self._buttons.append(btn)
            layout.addWidget(btn)

    def buttons(self) -> list[QPushButton]:
        return self._buttons

    def set_active(self, index: int) -> None:
        for i, b in enumerate(self._buttons):
            active = i == index
            b.setChecked(active)
            b.setProperty("active", "true" if active else "false")
            # Force re-polish so the [active="true"] selector updates.
            b.style().unpolish(b)
            b.style().polish(b)


class TopBar(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("TopBar")
        self.setFixedHeight(60)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(28, 0, 28, 0)
        layout.setSpacing(10)

        self.title = QLabel("")
        self.title.setObjectName("PageTitle")
        layout.addWidget(self.title)
        layout.addStretch(1)

        self.theme_btn = QPushButton("☾")  # ☾
        self.theme_btn.setProperty("class", "ghost")
        self.theme_btn.setToolTip("Toggle theme")
        self.theme_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(self.theme_btn)

        self.add_btn = QPushButton("+ Add")
        self.add_btn.setProperty("class", "primary")
        self.add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(self.add_btn)


class MainWindow(QMainWindow):
    def __init__(self, conn: sqlite3.Connection, settings: SettingsService) -> None:
        super().__init__()
        self.conn = conn
        self.settings = settings
        self.setWindowTitle(APP_DISPLAY_NAME)
        self.resize(1240, 780)

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

        # Compose root layout
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
            btn.clicked.connect(lambda _checked=False, idx=i: self.set_active(idx))
        self.topbar.add_btn.clicked.connect(self._fire_primary_action)
        self.topbar.theme_btn.clicked.connect(self._toggle_theme)

        # Keyboard: Ctrl+1..6 jump to view
        for i in range(len(self._views)):
            sc = QShortcut(QKeySequence(f"Ctrl+{i+1}"), self)
            sc.activated.connect(lambda idx=i: self.set_active(idx))

        # Initial state
        self.set_active(0)

    # --- behaviour ---

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
        new_theme = "light" if self.settings.get_theme() == "dark" else "dark"
        self.settings.set_theme(new_theme)
        apply_theme(QApplication.instance(), new_theme)  # type: ignore[arg-type]
        self.topbar.theme_btn.setText("☀" if new_theme == "dark" else "☾")
