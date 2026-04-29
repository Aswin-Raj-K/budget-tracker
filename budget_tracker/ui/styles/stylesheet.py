from __future__ import annotations

from string import Template

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from budget_tracker.config import ICONS_DIR
from budget_tracker.ui.styles.theme import (
    PACKAGE_DIR,
    Theme,
    resolve_theme,
    to_qss_tokens,
)

QSS_TEMPLATE_PATH = PACKAGE_DIR / "app.qss.template"
CHEVRON_DOWN_PATH = ICONS_DIR / "chevron-down.svg"

_current: Theme | None = None


def render_stylesheet(theme: Theme) -> str:
    """Render the global QSS, substituting theme tokens *and* a few global
    asset paths (icons) that QSS needs as URLs."""
    template = Template(QSS_TEMPLATE_PATH.read_text(encoding="utf-8"))
    tokens = to_qss_tokens(theme)
    # Qt QSS expects forward-slash paths inside url(...). as_posix() works
    # on both Windows and POSIX without producing backslashes.
    tokens["chevron_down_url"] = CHEVRON_DOWN_PATH.as_posix()
    return template.safe_substitute(tokens)


def _build_palette(theme: Theme) -> QPalette:
    """Push theme colors into a QPalette so widgets that paint via the
    palette (most notably QCalendarWidget cells) read correctly. QSS
    alone can't reach those cells.
    """
    p = QPalette()
    bg = QColor(theme.bg)
    surface = QColor(theme.surface)
    surface_alt = QColor(theme.surface_alt)
    text = QColor(theme.text)
    text_muted = QColor(theme.text_muted)
    text_subtle = QColor(theme.text_subtle)
    accent = QColor(theme.accent)
    accent_text = QColor(theme.accent_text)

    # Window / general background
    p.setColor(QPalette.ColorRole.Window, bg)
    p.setColor(QPalette.ColorRole.WindowText, text)

    # Input / item-view background (Base) and zebra (AlternateBase)
    p.setColor(QPalette.ColorRole.Base, surface)
    p.setColor(QPalette.ColorRole.AlternateBase, surface_alt)

    # Plain text on Base
    p.setColor(QPalette.ColorRole.Text, text)
    p.setColor(QPalette.ColorRole.BrightText, text)

    # Buttons (the calendar nav arrows are QToolButtons)
    p.setColor(QPalette.ColorRole.Button, surface)
    p.setColor(QPalette.ColorRole.ButtonText, text)

    # Tooltips
    p.setColor(QPalette.ColorRole.ToolTipBase, surface)
    p.setColor(QPalette.ColorRole.ToolTipText, text)

    # Selection (calendar uses Highlight to render the selected date)
    p.setColor(QPalette.ColorRole.Highlight, accent)
    p.setColor(QPalette.ColorRole.HighlightedText, accent_text)

    # Disabled group: applies to days outside the current month in the
    # calendar grid. Use text_subtle so they read as secondary instead
    # of being invisible.
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, text_subtle)
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, text_subtle)
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, text_subtle)
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.HighlightedText, text_muted)
    return p


def apply_theme(app: QApplication, theme_id: str) -> Theme:
    """Resolve and apply the named theme. Sets both the global QSS and
    the application palette (the palette feeds widgets like
    QCalendarWidget that don't honour QSS for individual cells)."""
    global _current
    theme = resolve_theme(theme_id)
    app.setPalette(_build_palette(theme))
    app.setStyleSheet(render_stylesheet(theme))
    _current = theme
    return theme


def current() -> Theme | None:
    return _current
