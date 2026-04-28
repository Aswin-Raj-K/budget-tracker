from __future__ import annotations

from decimal import Decimal

import pytest

from budget_tracker.core.money import (
    Currency,
    format_amount,
    set_active,
    supported_codes,
    to_major,
    to_minor,
)


def test_to_minor_handles_strings_and_decimals():
    assert to_minor("100") == 10000
    assert to_minor("100.50") == 10050
    assert to_minor("0.01") == 1
    assert to_minor(Decimal("1234.56")) == 123456


def test_to_minor_rounds_half_up():
    assert to_minor("0.005") == 1
    assert to_minor("0.004") == 0


def test_to_minor_rejects_negative():
    with pytest.raises(ValueError):
        to_minor("-1.00")
    with pytest.raises(ValueError):
        to_minor(-100)


def test_to_minor_rejects_garbage():
    with pytest.raises(ValueError):
        to_minor("abc")


def test_to_major_round_trip():
    for n in (0, 1, 99, 100, 12345, 9999999):
        assert to_minor(str(to_major(n))) == n


def test_format_amount_inr_indian_grouping():
    set_active("INR")
    assert format_amount(0) == "₹0.00"
    assert format_amount(99) == "₹0.99"
    assert format_amount(10000) == "₹100.00"
    assert format_amount(123456) == "₹1,234.56"
    assert format_amount(12345678) == "₹1,23,456.78"
    assert format_amount(123456789012) == "₹1,23,45,67,890.12"


def test_format_amount_usd_western_grouping():
    set_active("USD")
    assert format_amount(0) == "$0.00"
    assert format_amount(123456) == "$1,234.56"
    assert format_amount(123456789012) == "$1,234,567,890.12"
    set_active("INR")  # restore default


def test_format_amount_negative():
    set_active("INR")
    assert format_amount(-12345) == "-₹123.45"


def test_format_amount_without_symbol():
    set_active("INR")
    assert format_amount(12345, with_symbol=False) == "123.45"


def test_currency_from_code_rejects_unknown():
    with pytest.raises(ValueError):
        Currency.from_code("XYZ")


def test_supported_codes():
    codes = supported_codes()
    assert {"INR", "USD", "EUR", "GBP"}.issubset(codes)
