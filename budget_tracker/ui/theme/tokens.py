from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Theme:
    name: str
    # Surfaces
    bg: str
    surface: str
    surface_alt: str
    surface_hover: str
    surface_pressed: str
    border: str
    border_strong: str
    sidebar_bg: str
    # Text
    text: str
    text_muted: str
    text_subtle: str
    # Accent
    accent: str
    accent_hover: str
    accent_pressed: str
    accent_text: str          # text/icon color on top of accent fills
    # Status
    success: str
    warning: str
    danger: str
    # Categories — chip backgrounds (10% alpha for soft backgrounds)
    chip_bg: str


DARK = Theme(
    name="dark",
    bg="#0B1220",
    surface="#111827",
    surface_alt="#0F1A2E",
    surface_hover="#1F2A3E",
    surface_pressed="#26324A",
    border="#1F2A3E",
    border_strong="#334155",
    sidebar_bg="#0A101D",
    text="#E2E8F0",
    text_muted="#94A3B8",
    text_subtle="#64748B",
    accent="#6366F1",
    accent_hover="#7C7FF7",
    accent_pressed="#4F52D9",
    accent_text="#FFFFFF",
    success="#10B981",
    warning="#F59E0B",
    danger="#EF4444",
    chip_bg="#1F2A3E",
)

LIGHT = Theme(
    name="light",
    bg="#F6F8FB",
    surface="#FFFFFF",
    surface_alt="#F1F5F9",
    surface_hover="#EEF2F7",
    surface_pressed="#E2E8F0",
    border="#E2E8F0",
    border_strong="#CBD5E1",
    sidebar_bg="#FFFFFF",
    text="#0F172A",
    text_muted="#475569",
    text_subtle="#64748B",
    accent="#6366F1",
    accent_hover="#5559E0",
    accent_pressed="#4346BC",
    accent_text="#FFFFFF",
    success="#10B981",
    warning="#D97706",
    danger="#DC2626",
    chip_bg="#EEF2F7",
)


def by_name(name: str) -> Theme:
    if name == "light":
        return LIGHT
    return DARK
