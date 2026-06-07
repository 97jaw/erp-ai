"""Tool definitions for the Visualize agent (Claude tool use)."""

VISUALIZE_TOOLS = [
    {
        "name": "inspect_data",
        "description": (
            "Inspect dropped data structure. Returns metadata about data type, "
            "size, dimensions, date range, and completeness."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "dropped_items": {
                    "type": "array",
                    "description": "Optional override; defaults to session dropped items.",
                },
            },
        },
    },
    {
        "name": "analyze_patterns",
        "description": (
            "Detect trends, outliers, concentrations, variances, and "
            "business threshold breaches in the data."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "inspection": {"type": "object"},
            },
        },
    },
    {
        "name": "recommend_format",
        "description": (
            "Recommend best format, layout, theme, and sections based on "
            "inspection and pattern analysis."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "inspection": {"type": "object"},
                "analysis": {"type": "object"},
            },
        },
    },
    {
        "name": "generate_pdf",
        "description": (
            "Generate a downloadable PDF report from the dropped chat context. "
            "Build a full sections array (cover, summary, tables, charts) from CONTEXT."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "subtitle": {"type": "string"},
                "date_range": {"type": "string"},
                "language": {"type": "string", "enum": ["en", "ar"]},
                "theme": {
                    "type": "string",
                    "enum": [
                        "corporate_blue",
                        "elegant_gold",
                        "modern_dark",
                        "minimalist",
                        "light",
                        "dark",
                    ],
                },
                "layout": {
                    "type": "string",
                    "enum": ["executive", "detailed", "comparative", "presentation"],
                },
                "include_logo": {"type": "boolean"},
                "page_numbers": {"type": "boolean"},
                "watermark": {
                    "type": "string",
                    "enum": ["none", "confidential", "draft"],
                },
                "logo_url": {"type": "string"},
                "sections": {
                    "type": "array",
                    "items": {"type": "object"},
                },
            },
            "required": ["title", "sections"],
        },
    },
    {
        "name": "generate_excel",
        "description": (
            "Generate a downloadable Excel workbook from the dropped chat context."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "structure": {
                    "type": "string",
                    "enum": ["single_sheet", "multi_sheet", "pivot_ready"],
                },
                "columns": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "rows": {
                    "type": "array",
                    "items": {"type": "object"},
                },
                "formatting": {
                    "type": "object",
                    "properties": {
                        "currency_format": {"type": "boolean"},
                        "highlight_negatives": {"type": "boolean"},
                        "add_totals": {"type": "boolean"},
                    },
                },
            },
            "required": ["title"],
        },
    },
    {
        "name": "refine_output",
        "description": "Note a refinement request for the last generated output (theme change, section removal, etc.).",
        "input_schema": {
            "type": "object",
            "properties": {
                "refinement_request": {"type": "string"},
            },
            "required": ["refinement_request"],
        },
    },
]

TOOL_STATUS_LABELS = {
    "inspect_data": "Inspecting data structure...",
    "analyze_patterns": "Analyzing patterns and insights...",
    "recommend_format": "Forming recommendation...",
    "generate_pdf": "Generating PDF report...",
    "generate_excel": "Building Excel workbook...",
    "refine_output": "Applying refinement...",
}
