from __future__ import annotations

import sqlite3

from budget_tracker.core import money
from budget_tracker.core.repositories.settings import SettingsRepository

KEY_THEME = "theme"
KEY_CURRENCY = "currency"


class SettingsService:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.repo = SettingsRepository(conn)

    # --- theme ---

    def get_theme(self) -> str:
        return self.repo.get(KEY_THEME) or "dark"

    def set_theme(self, theme: str) -> None:
        """Persist the chosen theme id. The UI layer resolves unknown ids to
        a fallback at apply time, so we don't validate against the on-disk
        theme files here (keeps services free of any UI dependency)."""
        if not theme or not isinstance(theme, str):
            raise ValueError(f"Theme id must be a non-empty string, got {theme!r}")
        self.repo.set(KEY_THEME, theme)

    # --- currency ---

    def has_currency(self) -> bool:
        return self.repo.get(KEY_CURRENCY) is not None

    def get_currency_code(self) -> str:
        return self.repo.get(KEY_CURRENCY) or "INR"

    def set_currency(self, code: str) -> None:
        cur = money.Currency.from_code(code)        # validate
        self.repo.set(KEY_CURRENCY, cur.code)
        money.set_active(cur)

    def apply_to_session(self) -> None:
        """Sync the in-memory active currency from saved settings."""
        if self.has_currency():
            money.set_active(self.get_currency_code())
