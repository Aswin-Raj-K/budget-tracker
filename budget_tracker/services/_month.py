from __future__ import annotations

import calendar
from calendar import monthrange
from datetime import date


def parse_month(month: str) -> tuple[int, int]:
    """Parse a 'YYYY-MM' string into (year, month) ints."""
    parts = month.split("-")
    if len(parts) != 2:
        raise ValueError(f"Expected YYYY-MM, got {month!r}")
    y, m = int(parts[0]), int(parts[1])
    if not 1 <= m <= 12:
        raise ValueError(f"Bad month value: {m}")
    return y, m


def month_bounds(month: str) -> tuple[date, date]:
    """Return (first_day, last_day) for a 'YYYY-MM' string."""
    y, m = parse_month(month)
    last = monthrange(y, m)[1]
    return date(y, m, 1), date(y, m, last)


def current_month() -> str:
    today = date.today()
    return f"{today.year:04d}-{today.month:02d}"


def to_month_key(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def shift_month(month: str, delta: int) -> str:
    """Return a 'YYYY-MM' string offset by `delta` months (positive or negative)."""
    y, m = parse_month(month)
    total = (y * 12 + (m - 1)) + delta
    new_y, new_m = divmod(total, 12)
    return f"{new_y:04d}-{new_m + 1:02d}"


def human_month(month: str) -> str:
    """Render 'YYYY-MM' as 'Month YYYY' (e.g. 'April 2026')."""
    y, m = parse_month(month)
    return f"{calendar.month_name[m]} {y}"
