from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Optional

PACKAGE_DIR = Path(__file__).resolve().parent
THEMES_DIR = PACKAGE_DIR / "themes"


@dataclass(frozen=True)
class Theme:
    """All tokens needed to render the global stylesheet for one theme.

    Loaded from JSON; the JSON `colors` object's keys must match the field
    names below (other than id / name / description).
    """

    id: str
    name: str
    description: str = ""

    # Surfaces
    bg: str = ""
    surface: str = ""
    surface_alt: str = ""
    surface_hover: str = ""
    surface_pressed: str = ""
    border: str = ""
    border_strong: str = ""
    sidebar_bg: str = ""

    # Text
    text: str = ""
    text_muted: str = ""
    text_subtle: str = ""

    # Accent
    accent: str = ""
    accent_hover: str = ""
    accent_pressed: str = ""
    accent_text: str = ""
    accent_soft: str = ""        # very low-saturation tint of accent (used for active nav row)

    # Status
    success: str = ""
    warning: str = ""
    danger: str = ""

    # Chips
    chip_bg: str = ""


def _color_keys() -> set[str]:
    return {f.name for f in fields(Theme)} - {"id", "name", "description"}


def load_theme_file(path: Path) -> Theme:
    """Parse a single theme JSON file. Raises ValueError on missing keys."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if "id" not in data or "name" not in data:
        raise ValueError(f"Theme file {path.name} must define 'id' and 'name'")
    colors = data.get("colors") or {}
    missing = _color_keys() - colors.keys()
    if missing:
        raise ValueError(
            f"Theme {data.get('id')!r} ({path.name}) missing colors: {sorted(missing)}"
        )
    return Theme(
        id=data["id"],
        name=data["name"],
        description=data.get("description", ""),
        **{k: colors[k] for k in _color_keys()},
    )


def available_themes(themes_dir: Path = THEMES_DIR) -> list[Theme]:
    """Scan themes/ for *.json and return parsed themes, skipping invalid ones.

    Sorted by name for stable display in dropdowns.
    """
    out: list[Theme] = []
    if not themes_dir.exists():
        return out
    for path in sorted(themes_dir.glob("*.json")):
        try:
            out.append(load_theme_file(path))
        except (ValueError, json.JSONDecodeError):
            # Silently skip invalid theme files — keeps the app robust to
            # user-edited or partial JSON.
            continue
    out.sort(key=lambda t: t.name.lower())
    return out


def get_theme(theme_id: str, themes_dir: Path = THEMES_DIR) -> Optional[Theme]:
    for t in available_themes(themes_dir):
        if t.id == theme_id:
            return t
    return None


def resolve_theme(theme_id: str, themes_dir: Path = THEMES_DIR) -> Theme:
    """Look up a theme by id, falling back to 'dark' then to the first
    available theme. Raises only if no themes are bundled at all."""
    found = get_theme(theme_id, themes_dir)
    if found is not None:
        return found
    fallback = get_theme("dark", themes_dir)
    if fallback is not None:
        return fallback
    others = available_themes(themes_dir)
    if not others:
        raise RuntimeError(f"No theme files found in {themes_dir}")
    return others[0]


def to_qss_tokens(theme: Theme) -> dict[str, str]:
    """Flatten a Theme into the dict consumed by string.Template substitution."""
    d = asdict(theme)
    d.pop("description", None)
    return {k: v for k, v in d.items() if isinstance(v, str)}
