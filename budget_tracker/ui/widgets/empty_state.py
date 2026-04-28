from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout


class EmptyState(QFrame):
    """Friendly empty-state card with optional CTA button."""

    def __init__(
        self,
        title: str,
        message: str = "",
        cta_label: Optional[str] = None,
        on_cta: Optional[Callable[[], None]] = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setProperty("class", "card")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 48, 40, 48)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        h = QLabel(title)
        h.setProperty("class", "h2")
        h.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(h)

        if message:
            m = QLabel(message)
            m.setProperty("class", "muted")
            m.setAlignment(Qt.AlignmentFlag.AlignCenter)
            m.setWordWrap(True)
            layout.addWidget(m)

        if cta_label and on_cta:
            cta = QPushButton(cta_label)
            cta.setProperty("class", "primary")
            cta.setCursor(Qt.CursorShape.PointingHandCursor)
            cta.clicked.connect(on_cta)
            layout.addSpacing(8)
            layout.addWidget(cta, alignment=Qt.AlignmentFlag.AlignCenter)
