from __future__ import annotations

import json

import pytest

from budget_tracker.ui.styles import (
    available_themes,
    get_theme,
    load_theme_file,
    render_stylesheet,
    resolve_theme,
)
from budget_tracker.ui.styles.theme import THEMES_DIR


def test_bundled_themes_present():
    ids = {t.id for t in available_themes()}
    assert {"dark", "light", "midnight"}.issubset(ids)


def test_render_stylesheet_substitutes_all_tokens():
    dark = get_theme("dark")
    assert dark is not None
    css = render_stylesheet(dark)
    assert "${" not in css
    # spot-check a couple of tokens are present
    assert dark.bg in css
    assert dark.accent in css


def test_render_stylesheet_differs_per_theme():
    dark = get_theme("dark")
    light = get_theme("light")
    assert dark is not None and light is not None
    assert render_stylesheet(dark) != render_stylesheet(light)


def test_resolve_theme_falls_back_to_dark():
    t = resolve_theme("nonexistent-theme-id")
    assert t.id == "dark"


def test_resolve_known_theme():
    assert resolve_theme("midnight").id == "midnight"


def test_load_theme_file_rejects_missing_keys(tmp_path):
    bad = tmp_path / "broken.json"
    bad.write_text(
        json.dumps({"id": "broken", "name": "Broken", "colors": {"bg": "#000"}}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="missing colors"):
        load_theme_file(bad)


def test_available_themes_skips_invalid_files(tmp_path):
    # Valid file — preserve UTF-8 explicitly (default write_text uses the
    # system encoding on Windows, which mangles non-ASCII characters).
    (tmp_path / "good.json").write_text(
        (THEMES_DIR / "dark.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    # Invalid JSON file
    (tmp_path / "broken.json").write_text("{ not json", encoding="utf-8")
    # Should still return the good one and not crash on the broken one
    themes = available_themes(tmp_path)
    assert any(t.id == "dark" for t in themes)
