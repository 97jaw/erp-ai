"""Visualize PDF theme library (Phase 3)."""

from __future__ import annotations

from typing import Any


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    value = hex_color.lstrip("#")
    return tuple(int(value[index : index + 2], 16) for index in (0, 2, 4))


VISUALIZE_THEMES: dict[str, dict[str, Any]] = {
    "corporate_blue": {
        "id": "corporate_blue",
        "name": "Corporate Blue",
        "description": "Formal, conservative — boards and investors",
        "colors": {
            "primary": "#1a5490",
            "secondary": "#4a90c2",
            "accent": "#fbbf24",
            "text_primary": "#1f2937",
            "text_secondary": "#6b7280",
            "background": "#ffffff",
            "table_header_bg": "#1a5490",
            "table_header_fg": "#ffffff",
            "table_row_alt": "#f3f4f6",
            "positive": "#059669",
            "negative": "#dc2626",
        },
        "fonts": {
            "header": "Georgia, serif",
            "body": "Calibri, Arial, sans-serif",
        },
        "chart_colors": ["#1a5490", "#4a90c2", "#fbbf24", "#059669"],
    },
    "elegant_gold": {
        "id": "elegant_gold",
        "name": "Elegant Gold",
        "description": "Premium executive — high-end presentations",
        "colors": {
            "primary": "#1a2744",
            "secondary": "#c9a84c",
            "accent": "#a8873d",
            "text_primary": "#1a2744",
            "text_secondary": "#5a6378",
            "background": "#fefdfb",
            "table_header_bg": "#1a2744",
            "table_header_fg": "#c9a84c",
            "table_row_alt": "#faf7f0",
            "positive": "#10b981",
            "negative": "#ef4444",
        },
        "fonts": {
            "header": "Georgia, serif",
            "body": "Inter, Calibri, Arial, sans-serif",
        },
        "chart_colors": ["#c9a84c", "#1a2744", "#10b981", "#4ecdc4"],
    },
    "modern_dark": {
        "id": "modern_dark",
        "name": "Modern Dark",
        "description": "Sleek, tech — digital-first audiences",
        "colors": {
            "primary": "#0a0f1e",
            "secondary": "#4ecdc4",
            "accent": "#c9a84c",
            "text_primary": "#e8eaf6",
            "text_secondary": "#9ca3af",
            "background": "#0d1428",
            "table_header_bg": "#1a2744",
            "table_header_fg": "#4ecdc4",
            "table_row_alt": "#141b2e",
            "positive": "#4ecdc4",
            "negative": "#ff6b6b",
        },
        "fonts": {
            "header": "Inter, Arial, sans-serif",
            "body": "Inter, Arial, sans-serif",
        },
        "chart_colors": ["#4ecdc4", "#c9a84c", "#8b5cf6", "#ff6b6b"],
    },
    "minimalist": {
        "id": "minimalist",
        "name": "Minimalist",
        "description": "Clean and simple — data-first",
        "colors": {
            "primary": "#000000",
            "secondary": "#525252",
            "accent": "#000000",
            "text_primary": "#000000",
            "text_secondary": "#737373",
            "background": "#ffffff",
            "table_header_bg": "#ffffff",
            "table_header_fg": "#000000",
            "table_row_alt": "#fafafa",
            "positive": "#000000",
            "negative": "#000000",
        },
        "fonts": {
            "header": "Helvetica, Arial, sans-serif",
            "body": "Helvetica, Arial, sans-serif",
        },
        "chart_colors": ["#525252", "#737373", "#000000", "#a3a3a3"],
    },
}


def list_themes() -> list[dict[str, Any]]:
    return [
        {
            "id": theme["id"],
            "name": theme["name"],
            "description": theme["description"],
            "preview": {
                "primary": theme["colors"]["primary"],
                "secondary": theme["colors"]["secondary"],
                "accent": theme["colors"]["accent"],
                "background": theme["colors"]["background"],
            },
        }
        for theme in VISUALIZE_THEMES.values()
    ]


def resolve_theme(theme_id: str | None) -> dict[str, Any]:
    if not theme_id:
        return VISUALIZE_THEMES["elegant_gold"]
    normalized = theme_id.strip().lower().replace(" ", "_")
    if normalized in VISUALIZE_THEMES:
        return VISUALIZE_THEMES[normalized]
    if normalized in ("light", "dark"):
        return VISUALIZE_THEMES["elegant_gold" if normalized == "light" else "modern_dark"]
    return VISUALIZE_THEMES["elegant_gold"]


def theme_fpdf_palette(theme: dict[str, Any]) -> dict[str, Any]:
    colors = theme["colors"]
    return {
        "background": _hex_to_rgb(colors["background"]),
        "text": _hex_to_rgb(colors["text_primary"]),
        "accent": _hex_to_rgb(colors["secondary"]),
        "muted": _hex_to_rgb(colors["text_secondary"]),
        "positive": _hex_to_rgb(colors["positive"]),
        "negative": _hex_to_rgb(colors["negative"]),
    }


def theme_css_bundle(theme: dict[str, Any]) -> dict[str, str]:
    colors = theme["colors"]
    return {
        "background": colors["background"],
        "text": colors["text_primary"],
        "accent": colors["secondary"],
        "muted": colors["text_secondary"],
        "primary": colors["primary"],
        "section_bg": colors["table_row_alt"],
        "table_header_bg": colors["table_header_bg"],
        "table_header_fg": colors["table_header_fg"],
        "table_row_alt": colors["table_row_alt"],
        "positive": colors["positive"],
        "negative": colors["negative"],
        "header_font": theme["fonts"]["header"],
        "body_font": theme["fonts"]["body"],
    }
