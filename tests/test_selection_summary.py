"""Tests for the multi-select summary helper used by the Transactions view.

Exercises both the pure aggregator (`summarize`) and the view-layer
status-label formatter (`_render_status_label`). The formatter test
imports from a Qt-using module — that's fine, PySide6 is a hard dep.
"""
from __future__ import annotations

from datetime import date

import pytest

from budget_tracker.core import money
from budget_tracker.core.models import Transaction
from budget_tracker.services.selection_summary import (
    SelectionSummary,
    summarize,
)


# ---------- summarize() ----------

def _tx(kind: str, amount: int) -> Transaction:
    return Transaction(
        id=None,
        occurred_on=date(2026, 5, 1),
        kind=kind,            # type: ignore[arg-type]
        amount=amount,
        account_id=1,
    )


def test_summarize_empty_returns_zeroed_summary():
    s = summarize([])
    assert s.count == 0
    assert s.income_total == 0
    assert s.expense_total == 0
    assert s.transfer_total == 0
    assert s.net == 0
    assert s.has_income is False
    assert s.has_expense is False
    assert s.has_transfer is False


def test_summarize_only_expenses():
    s = summarize([_tx("expense", 1000), _tx("expense", 580), _tx("expense", 3000)])
    assert s.count == 3
    assert s.expense_total == 4580
    assert s.income_total == 0
    assert s.transfer_total == 0
    assert s.net == -4580


def test_summarize_only_income():
    s = summarize([_tx("income", 1500), _tx("income", 500)])
    assert s.count == 2
    assert s.income_total == 2000
    assert s.expense_total == 0
    assert s.net == 2000


def test_summarize_only_transfers():
    s = summarize([_tx("transfer", 1000), _tx("transfer", 200)])
    assert s.count == 2
    assert s.transfer_total == 1200
    assert s.income_total == 0
    assert s.expense_total == 0
    assert s.net == 0


def test_summarize_mixed_income_and_expense():
    s = summarize([_tx("income", 2000), _tx("expense", 4580), _tx("expense", 200)])
    assert s.count == 3
    assert s.income_total == 2000
    assert s.expense_total == 4780
    assert s.net == 2000 - 4780


def test_summarize_mixed_with_transfer():
    s = summarize([_tx("income", 1000), _tx("expense", 400), _tx("transfer", 250)])
    assert s.count == 3
    assert s.income_total == 1000
    assert s.expense_total == 400
    assert s.transfer_total == 250
    # Transfers don't move the net.
    assert s.net == 600


# ---------- _render_status_label() ----------

# Imported here (not at top) so test discovery for the pure helper above
# isn't slowed down by Qt initialisation costs.
from budget_tracker.ui.views.transactions_view import _render_status_label  # noqa: E402


@pytest.fixture(autouse=True)
def _force_currency():
    """Pin the currency so format_amount output is predictable across machines."""
    prev = money.active()
    money.set_active("USD")
    yield
    money.set_active(prev)


def test_render_label_no_selection():
    assert _render_status_label(23, SelectionSummary(0, 0, 0, 0)) == "23 transactions"


def test_render_label_singular_count():
    assert _render_status_label(1, SelectionSummary(0, 0, 0, 0)) == "1 transaction"


def test_render_label_only_expenses():
    s = SelectionSummary(count=5, income_total=0, expense_total=4580_00, transfer_total=0)
    out = _render_status_label(23, s)
    assert "5 selected" in out
    assert "expense" in out
    assert "$4,580.00" in out
    assert "Net" not in out


def test_render_label_only_income():
    s = SelectionSummary(count=3, income_total=2000_00, expense_total=0, transfer_total=0)
    out = _render_status_label(23, s)
    assert "3 selected" in out
    assert "income" in out
    assert "$2,000.00" in out


def test_render_label_only_transfers():
    s = SelectionSummary(count=2, income_total=0, expense_total=0, transfer_total=1000_00)
    out = _render_status_label(23, s)
    assert "transfer" in out
    assert "$1,000.00" in out


def test_render_label_mixed_income_and_expense():
    s = SelectionSummary(count=4, income_total=2000_00, expense_total=4580_00, transfer_total=0)
    out = _render_status_label(23, s)
    assert "4 selected" in out
    assert "Net" in out
    assert "−" in out                 # negative net
    assert "$2,580.00" in out         # |net|
    assert "$2,000.00 income" in out
    assert "$4,580.00 expense" in out


def test_render_label_mixed_with_transfer_appends_transfer_chunk():
    s = SelectionSummary(count=5, income_total=1000_00, expense_total=400_00, transfer_total=250_00)
    out = _render_status_label(23, s)
    assert "Net" in out
    assert "$250.00 transfer" in out
