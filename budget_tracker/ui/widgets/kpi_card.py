from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


class KpiCard(QFrame):
    """A small dashboard card with an uppercase label and a big value."""

    def __init__(self, label: str, value: str = "—", subtitle: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setProperty("class", "card")
        self.setMinimumHeight(110)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(8)

        self._label = QLabel(label)
        self._label.setProperty("class", "kpi-label")

        self._value = QLabel(value)
        self._value.setProperty("class", "kpi-value")
        self._value.setWordWrap(False)

        self._subtitle = QLabel(subtitle)
        self._subtitle.setProperty("class", "subtle")
        self._subtitle.setVisible(bool(subtitle))

        layout.addWidget(self._label)
        layout.addWidget(self._value)
        layout.addWidget(self._subtitle)
        layout.addStretch(1)

    def set_value(self, text: str, subtitle: str = "") -> None:
        self._value.setText(text)
        self._subtitle.setText(subtitle)
        self._subtitle.setVisible(bool(subtitle))
