from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy


class NavButton(QFrame):
    """Sidebar navigation row.

    Visual structure:
        [accent-stripe] [icon] [label] ............................

    The stripe and the row both react to the dynamic property
    `active="true"` so the QSS file owns all colours.
    """

    clicked = Signal()

    def __init__(self, icon: str, label: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("NavButton")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(38)

        self._stripe = QFrame(self)
        self._stripe.setObjectName("NavActiveStripe")
        self._stripe.setFixedWidth(3)

        self._icon = QLabel(icon, self)
        self._icon.setObjectName("NavIcon")
        self._icon.setFixedWidth(22)
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._label = QLabel(label, self)
        self._label.setObjectName("NavLabel")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 12, 0)
        layout.setSpacing(10)
        layout.addWidget(self._stripe)
        layout.addWidget(self._icon)
        layout.addWidget(self._label, 1)

        self.set_active(False)

    def set_active(self, active: bool) -> None:
        flag = "true" if active else "false"
        self.setProperty("active", flag)
        self._stripe.setProperty("active", flag)
        for w in (self, self._stripe):
            s = w.style()
            s.unpolish(w)
            s.polish(w)
        # Repolish children too so descendant selectors update.
        for w in (self._icon, self._label):
            s = w.style()
            s.unpolish(w)
            s.polish(w)

    def mousePressEvent(self, ev) -> None:  # noqa: N802 (Qt naming)
        if ev.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(ev)


def make_nav(icon: str, label: str, on_click: Optional[Callable[[], None]] = None) -> NavButton:
    btn = NavButton(icon, label)
    if on_click:
        btn.clicked.connect(on_click)
    return btn
