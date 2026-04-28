from __future__ import annotations

from budget_tracker.ui.theme import DARK, LIGHT, render_stylesheet, resolve_theme


def test_render_stylesheet_substitutes_tokens():
    css = render_stylesheet(DARK)
    # All ${...} placeholders should be substituted; spot-check a few colors.
    assert "${" not in css
    assert DARK.bg in css
    assert DARK.accent in css


def test_render_stylesheet_differs_per_theme():
    assert render_stylesheet(DARK) != render_stylesheet(LIGHT)


def test_resolve_theme_by_name():
    assert resolve_theme("dark") is DARK
    assert resolve_theme("light") is LIGHT
    # unknown falls through to dark
    assert resolve_theme("anything-else").name == "dark"
