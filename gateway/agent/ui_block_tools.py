"""UI interaction tools — Claude uses these to control the frontend."""

from __future__ import annotations

from typing import Any

show_ui_block_tool: dict[str, Any] = {
    "name": "show_ui_block",
    "description": (
        "Show an interactive UI element to the user. Use when you need to ask "
        "the user a question and want them to click rather than type. ALWAYS "
        "prefer this over plain-text questions when there are predictable options."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "block_type": {
                "type": "string",
                "enum": [
                    "pill_select",
                    "multi_check",
                    "date_picker",
                    "date_quick",
                    "search_picker",
                    "format_select",
                    "toggle",
                    "text_input",
                ],
                "description": "UI block type (alias: type).",
            },
            "type": {
                "type": "string",
                "description": "Alias for block_type.",
            },
            "prompt": {
                "type": "string",
                "description": "Question or label shown above the block.",
            },
            "label": {
                "type": "string",
                "description": "Alias for prompt.",
            },
            "options": {
                "type": "array",
                "description": "Options for pill_select / multi_check.",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "label": {"type": "string"},
                        "icon": {"type": "string"},
                    },
                },
            },
            "mode": {
                "type": "string",
                "enum": ["single", "multi"],
                "description": "Selection mode for pill_select.",
            },
            "allow_typed_input": {
                "type": "boolean",
                "description": "Allow free-text input alongside pills.",
                "default": True,
            },
        },
        "required": [],
    },
}

add_suggestions_tool: dict[str, Any] = {
    "name": "add_suggestions",
    "description": (
        "Add 2-3 contextual follow-up suggestions to the response. These appear "
        "as clickable chips. MUST be relevant to what was just discussed."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "suggestions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "label": {"type": "string"},
                        "query": {
                            "type": "string",
                            "description": "Query to run when the chip is clicked",
                        },
                    },
                    "required": ["label", "query"],
                },
                "minItems": 1,
                "maxItems": 3,
            },
        },
        "required": ["suggestions"],
    },
}

render_visualization_tool: dict[str, Any] = {
    "name": "render_visualization",
    "description": (
        "Render a visualization (KPI card, chart, table) alongside the text. "
        "Use when data is better shown visually than as prose."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "type": {
                "type": "string",
                "enum": [
                    "kpi_card",
                    "bar_chart",
                    "line_chart",
                    "pie_chart",
                    "table",
                    "timeline",
                ],
            },
            "data": {"type": "object"},
            "title": {"type": "string"},
        },
        "required": ["type", "data"],
    },
}

UI_INTERACTION_TOOLS: list[dict[str, Any]] = [
    show_ui_block_tool,
    add_suggestions_tool,
    render_visualization_tool,
]

UI_TOOL_NAMES = frozenset({"show_ui_block", "add_suggestions", "render_visualization"})
