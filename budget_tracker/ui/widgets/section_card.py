from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class SectionCard(QFrame):
    """A card with a heading row (title + optional action) and a body area
    that consumers fill via `body_layout()`."""

    def __init__(
        self,
        title: str,
        action_label: Optional[str] = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setProperty("class", "card")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(22, 18, 22, 22)
        outer.setSpacing(14)

        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(8)
        title_lbl = QLabel(title)
        title_lbl.setProperty("class", "h2")
        head.addWidget(title_lbl)
        head.addStretch(1)

        self.action: Optional[QPushButton] = None
        if action_label:
            self.action = QPushButton(action_label)
            self.action.setProperty("class", "ghost")
            head.addWidget(self.action)
        outer.addLayout(head)

        body = QWidget(self)
        self._body_layout = QVBoxLayout(body)
        self._body_layout.setContentsMargins(0, 0, 0, 0)
        self._body_layout.setSpacing(10)
        outer.addWidget(body, 1)

    def body_layout(self) -> QVBoxLayout:
        return self._body_layout

    def clear_body(self) -> None:
        while self._body_layout.count():
            item = self._body_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
