from __future__ import annotations

from pathlib import Path

from gateway.pdf_reports import REPORTS_DIR
from visualize.pdf_generator import PDFGenerator, generate_visualize_pdf
from visualize.pdf_options import normalize_watermark, parse_pdf_options


def test_pdf_generator_class_produces_pdf_with_charts() -> None:
    generator = PDFGenerator("corporate_blue")
    result = generator.generate({
        "title": "Phase 4 Chart Test",
        "theme": "corporate_blue",
        "layout": "detailed",
        "include_logo": True,
        "page_numbers": True,
        "watermark": "confidential",
        "sections": [
            {
                "type": "bar_chart",
                "title": "Revenue by Client",
                "data": {"labels": ["A", "B", "C"], "values": [1200, 3400, 2100]},
            },
            {
                "type": "table",
                "title": "Totals",
                "data": {
                    "headers": ["Metric", "Value"],
                    "rows": [["Revenue", "6.7M"], ["Profit", "1.2M"]],
                },
            },
        ],
    })

    assert "error" not in result
    assert result["include_logo"] is True
    assert result["page_numbers"] is True
    assert result["watermark"] == "CONFIDENTIAL"
    assert result["size_bytes"] > 1500

    pdf_path = REPORTS_DIR / Path(result["pdf_url"]).name
    assert pdf_path.exists()


def test_generate_visualize_pdf_respects_logo_and_watermark_flags() -> None:
    with_logo = generate_visualize_pdf({
        "title": "With Logo",
        "theme": "elegant_gold",
        "include_logo": True,
        "page_numbers": False,
        "watermark": "draft",
        "sections": [{"type": "executive_summary", "content": "Summary text."}],
    })
    without_logo = generate_visualize_pdf({
        "title": "Without Logo",
        "theme": "elegant_gold",
        "include_logo": False,
        "page_numbers": True,
        "watermark": "none",
        "sections": [{"type": "executive_summary", "content": "Summary text."}],
    })

    assert "error" not in with_logo
    assert "error" not in without_logo
    assert with_logo["watermark"] == "DRAFT"
    assert without_logo["watermark"] is None
    assert with_logo["include_logo"] is True
    assert without_logo["include_logo"] is False


def test_parse_pdf_options_defaults() -> None:
    options = parse_pdf_options({})
    assert options.include_logo is True
    assert options.page_numbers is True
    assert options.watermark is None
    assert normalize_watermark("confidential") == "CONFIDENTIAL"
