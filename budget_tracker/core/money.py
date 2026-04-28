from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

# Single-currency app: store the user's choice in `settings` and read it
# at startup. We expose the currently-active currency via `Currency.active`.

_SUPPORTED = {
    "INR": ("₹", "INR"),
    "USD": ("$", "USD"),
    "EUR": ("€", "EUR"),
    "GBP": ("£", "GBP"),
}


@dataclass(frozen=True)
class Currency:
    code: str
    symbol: str

    @classmethod
    def from_code(cls, code: str) -> "Currency":
        code = code.upper()
        if code not in _SUPPORTED:
            raise ValueError(f"Unsupported currency: {code!r}")
        symbol, _ = _SUPPORTED[code]
        return cls(code=code, symbol=symbol)


# Mutable module-level active currency (set once at app startup from settings).
# Tests and the settings dialog can override via set_active().
_active: Currency = Currency.from_code("INR")


def set_active(currency: Currency | str) -> None:
    """Set the currently active currency for the running session."""
    global _active
    _active = currency if isinstance(currency, Currency) else Currency.from_code(currency)


def active() -> Currency:
    return _active


def supported_codes() -> list[str]:
    return list(_SUPPORTED.keys())


# --- Conversions ----------------------------------------------------------

def to_minor(amount: str | int | float | Decimal) -> int:
    """Convert a human amount (e.g. "1234.50", 1234.5) to integer minor units.

    Always 2 decimal places. Rejects negatives — store sign via transaction kind.
    Rounding: HALF_UP, so "0.005" → 1 minor unit.
    """
    if isinstance(amount, int):
        if amount < 0:
            raise ValueError("Amount must be non-negative")
        return amount * 100
    try:
        d = Decimal(str(amount))
    except InvalidOperation as e:
        raise ValueError(f"Invalid amount: {amount!r}") from e
    if d < 0:
        raise ValueError("Amount must be non-negative")
    quantized = d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return int((quantized * 100).to_integral_value())


def to_major(minor: int) -> Decimal:
    """Convert integer minor units back to a Decimal in major units."""
    return (Decimal(minor) / Decimal(100)).quantize(Decimal("0.01"))


def format_amount(minor: int, *, with_symbol: bool = True, currency: Currency | None = None) -> str:
    """Format an integer minor-unit amount as a human string.

    Uses Indian-style grouping for INR (e.g. ₹1,23,45,678.00) and Western
    grouping for USD/EUR/GBP. No locale lib required.
    """
    cur = currency or _active
    sign = "-" if minor < 0 else ""
    abs_minor = abs(minor)
    rupees, paise = divmod(abs_minor, 100)
    if cur.code == "INR":
        grouped = _indian_group(rupees)
    else:
        grouped = f"{rupees:,}"
    body = f"{grouped}.{paise:02d}"
    return f"{sign}{cur.symbol}{body}" if with_symbol else f"{sign}{body}"


def _indian_group(n: int) -> str:
    s = str(n)
    if len(s) <= 3:
        return s
    head, tail = s[:-3], s[-3:]
    # group head in pairs from the right
    pairs = []
    while len(head) > 2:
        pairs.append(head[-2:])
        head = head[:-2]
    if head:
        pairs.append(head)
    return ",".join(reversed(pairs)) + "," + tail
