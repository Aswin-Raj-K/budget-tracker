from __future__ import annotations

from typing import Literal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar, QVBoxLayout

Status = Literal["under", "warning", "over", "success"]


class ColorDot(QLabel):
    """Tiny circular swatch used to mark a category."""

    def __init__(self, color: str, size: int = 10, parent=None) -> None:
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.setStyleSheet(
            f"background-color: {color}; border-radius: {size // 2}px;"
        )


class ProgressRow(QFrame):
    """One row used in the 'Budgets at a glance' section.

    Layout:
        [● Food]          [₹4.5k / ₹10k]
        [progress bar    ]
    """

    def __init__(
        self,
        name: str,
        amount_label: str,
        percent: float,
        status: Status = "under",
        color: str = "#7C5CFF",
        parent=None,
    ) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(8)

        dot = ColorDot(color)
        name_lbl = QLabel(name)
        name_lbl.setProperty("class", "h3")

        amount_lbl = QLabel(amount_label)
        amount_lbl.setProperty("class", "muted")
        amount_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        head.addWidget(dot)
        head.addWidget(name_lbl)
        head.addStretch(1)
        head.addWidget(amount_lbl)

        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(int(min(100, max(0, percent))))
        bar.setProperty("status", status)
        bar.setTextVisible(False)
        bar.setFixedHeight(8)

        layout.addLayout(head)
        layout.addWidget(bar)
