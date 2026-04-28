from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from typing import Optional

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from budget_tracker.core import money
from budget_tracker.core.models import Goal, GoalKind
from budget_tracker.core.repositories.goals import GoalRepository

KIND_LABELS: list[tuple[GoalKind, str]] = [
    ("savings", "Savings goal"),
    ("debt",    "Debt payoff"),
]


class GoalDialog(QDialog):
    def __init__(
        self,
        conn: sqlite3.Connection,
        goal: Optional[Goal] = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._editing = goal
        self._repo = GoalRepository(conn)
        self._saved: Optional[Goal] = None

        self.setWindowTitle("Edit goal" if goal else "Add goal")
        self.setMinimumWidth(420)
        self.setModal(True)

        self._build()
        if goal is not None:
            self._prefill(goal)
        self._name.setFocus()

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 22, 24, 20)
        outer.setSpacing(14)

        title = QLabel("Edit goal" if self._editing else "Add goal")
        title.setProperty("class", "h2")
        outer.addWidget(title)

        form = QFormLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self._name = QLineEdit()
        self._name.setPlaceholderText("e.g. Emergency fund")
        form.addRow("Name", self._name)

        self._kind = QComboBox()
        for value, label in KIND_LABELS:
            self._kind.addItem(label, value)
        form.addRow("Kind", self._kind)

        self._target = QDoubleSpinBox()
        self._target.setDecimals(2)
        self._target.setRange(0.0, 99_99_99_999.99)
        self._target.setSingleStep(1000.0)
        self._target.setPrefix(f"{money.active().symbol} ")
        self._target.setAlignment(Qt.AlignmentFlag.AlignRight)
        form.addRow("Target", self._target)

        self._current = QDoubleSpinBox()
        self._current.setDecimals(2)
        self._current.setRange(0.0, 99_99_99_999.99)
        self._current.setSingleStep(1000.0)
        self._current.setPrefix(f"{money.active().symbol} ")
        self._current.setAlignment(Qt.AlignmentFlag.AlignRight)
        form.addRow("Starting amount", self._current)

        deadline_row = QHBoxLayout()
        deadline_row.setSpacing(8)
        self._has_deadline = QCheckBox("Has deadline")
        self._deadline = QDateEdit()
        self._deadline.setCalendarPopup(True)
        self._deadline.setDisplayFormat("dd MMM yyyy")
        self._deadline.setDate(QDate.currentDate().addMonths(6))
        self._deadline.setEnabled(False)
        self._has_deadline.toggled.connect(self._deadline.setEnabled)
        deadline_row.addWidget(self._has_deadline)
        deadline_row.addWidget(self._deadline, 1)
        form.addRow("Deadline", deadline_row)

        outer.addLayout(form)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.setProperty("class", "secondary")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Save")
        save.setProperty("class", "primary")
        save.setDefault(True)
        save.clicked.connect(self._on_save)
        button_row.addWidget(cancel)
        button_row.addWidget(save)
        outer.addLayout(button_row)

    def _prefill(self, goal: Goal) -> None:
        self._name.setText(goal.name)
        idx = next(i for i, (v, _) in enumerate(KIND_LABELS) if v == goal.kind)
        self._kind.setCurrentIndex(idx)
        self._target.setValue(float(money.to_major(goal.target_amount)))
        self._current.setValue(float(money.to_major(goal.current_amount)))
        if goal.deadline:
            self._has_deadline.setChecked(True)
            self._deadline.setDate(QDate(goal.deadline.year, goal.deadline.month, goal.deadline.day))

    def _on_save(self) -> None:
        name = self._name.text().strip()
        if not name:
            QMessageBox.warning(self, "Cannot save", "Goal needs a name.")
            return
        target_minor = money.to_minor(self._target.value())
        if target_minor <= 0:
            QMessageBox.warning(self, "Cannot save", "Target must be greater than zero.")
            return
        current_minor = money.to_minor(self._current.value())

        deadline: Optional[date] = None
        if self._has_deadline.isChecked():
            qd = self._deadline.date()
            deadline = date(qd.year(), qd.month(), qd.day())

        goal = Goal(
            id=self._editing.id if self._editing else None,
            name=name,
            kind=self._kind.currentData(),
            target_amount=target_minor,
            current_amount=current_minor,
            deadline=deadline,
        )
        if self._editing:
            self._saved = self._repo.update(goal)
        else:
            self._saved = self._repo.add(goal)
        self.accept()

    def saved(self) -> Optional[Goal]:
        return self._saved
