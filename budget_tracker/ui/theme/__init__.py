from __future__ import annotations

from dataclasses import asdict
from string import Template

from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication

from budget_tracker.config import THEME_DIR
from budget_tracker.ui.theme.tokens import DARK, LIGHT, Theme, by_name

_TEMPLATE_FILE = THEME_DIR / "app.qss.template"

_current: Theme = DARK


def render_stylesheet(theme: Theme) -> str:
    template = Template(_TEMPLATE_FILE.read_text(encoding="utf-8"))
    return template.safe_substitute(asdict(theme))


def detect_system_theme() -> str:
    """Return 'dark' or 'light' based on the platform palette."""
    app = QApplication.instance()
    if app is None:
        return "dark"
    bg = app.palette().color(QPalette.ColorRole.Window)
    return "dark" if bg.lightness() < 128 else "light"


def resolve_theme(name: str) -> Theme:
    if name == "system":
        return by_name(detect_system_theme())
    return by_name(name)


def apply_theme(app: QApplication, theme_name: str) -> Theme:
    """Render and apply the stylesheet for the given theme name.

    Returns the resolved Theme so callers can use its tokens.
    """
    global _current
    theme = resolve_theme(theme_name)
    app.setStyleSheet(render_stylesheet(theme))
    _current = theme
    return theme


def current() -> Theme:
    return _current


__all__ = [
    "DARK",
    "LIGHT",
    "Theme",
    "apply_theme",
    "current",
    "detect_system_theme",
    "render_stylesheet",
    "resolve_theme",
]
