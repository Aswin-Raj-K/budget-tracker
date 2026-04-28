from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from budget_tracker.core import money


class WelcomeDialog(QDialog):
    """Shown once on first launch to capture the user's preferred currency.

    There's no Cancel — the only way out is to click Continue. If the user
    closes the dialog via the title bar, `currency_code()` falls back to
    the dropdown's current value so the app still has a sane default.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Welcome to Budget Tracker")
        self.setMinimumWidth(440)
        self.setModal(True)
        # Hide the OS context-help question mark on Windows.
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 26, 28, 22)
        outer.setSpacing(14)

        title = QLabel("Welcome to Budget Tracker")
        title.setProperty("class", "h1")
        outer.addWidget(title)

        intro = QLabel(
            "Pick your currency to get started. Everything stays on your device — "
            "your data never leaves this computer."
        )
        intro.setProperty("class", "muted")
        intro.setWordWrap(True)
        outer.addWidget(intro)

        outer.addSpacing(6)

        currency_label = QLabel("Currency")
        currency_label.setProperty("class", "h3")
        outer.addWidget(currency_label)

        self._currency = QComboBox()
        for code in money.supported_codes():
            sym = money.Currency.from_code(code).symbol
            self._currency.addItem(f"{code}  ·  {sym}", code)
        outer.addWidget(self._currency)

        note = QLabel(
            "You can change this later in Settings — it only affects how amounts "
            "are displayed, never how they're stored."
        )
        note.setProperty("class", "subtle")
        note.setWordWrap(True)
        outer.addWidget(note)

        outer.addStretch(1)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        cont = QPushButton("Continue")
        cont.setProperty("class", "primary")
        cont.setDefault(True)
        cont.clicked.connect(self.accept)
        button_row.addWidget(cont)
        outer.addLayout(button_row)

    def currency_code(self) -> str:
        return self._currency.currentData() or "INR"
