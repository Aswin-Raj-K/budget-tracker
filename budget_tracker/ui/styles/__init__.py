"""Style/theme infrastructure.

Public API — keep imports going through this module:

    from budget_tracker.ui.styles import apply_theme, available_themes, current
"""
from __future__ import annotations

from budget_tracker.ui.styles.stylesheet import (
    QSS_TEMPLATE_PATH,
    apply_theme,
    current,
    render_stylesheet,
)
from budget_tracker.ui.styles.theme import (
    THEMES_DIR,
    Theme,
    available_themes,
    get_theme,
    load_theme_file,
    resolve_theme,
    to_qss_tokens,
)

__all__ = [
    "QSS_TEMPLATE_PATH",
    "THEMES_DIR",
    "Theme",
    "apply_theme",
    "available_themes",
    "current",
    "get_theme",
    "load_theme_file",
    "render_stylesheet",
    "resolve_theme",
    "to_qss_tokens",
]
