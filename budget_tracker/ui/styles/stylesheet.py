from __future__ import annotations

from string import Template

from PySide6.QtWidgets import QApplication

from budget_tracker.ui.styles.theme import (
    PACKAGE_DIR,
    Theme,
    resolve_theme,
    to_qss_tokens,
)

QSS_TEMPLATE_PATH = PACKAGE_DIR / "app.qss.template"

_current: Theme | None = None


def render_stylesheet(theme: Theme) -> str:
    template = Template(QSS_TEMPLATE_PATH.read_text(encoding="utf-8"))
    return template.safe_substitute(to_qss_tokens(theme))


def apply_theme(app: QApplication, theme_id: str) -> Theme:
    """Resolve and apply the named theme to the application. Returns the
    Theme actually applied (after fallbacks)."""
    global _current
    theme = resolve_theme(theme_id)
    app.setStyleSheet(render_stylesheet(theme))
    _current = theme
    return theme


def current() -> Theme | None:
    return _current
