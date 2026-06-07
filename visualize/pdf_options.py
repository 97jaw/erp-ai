"""PDF render options for Visualize exports (Phase 4)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PdfRenderOptions:
    include_logo: bool = True
    page_numbers: bool = True
    watermark: str | None = None
    logo_url: str | None = None


_WATERMARK_ALIASES = {
    "none": None,
    "": None,
    "confidential": "CONFIDENTIAL",
    "draft": "DRAFT",
}


def normalize_watermark(value: Any) -> str | None:
    if value is None or value is False:
        return None
    text = str(value).strip()
    if not text:
        return None
    lowered = text.lower()
    if lowered in _WATERMARK_ALIASES:
        return _WATERMARK_ALIASES[lowered]
    return text.upper()


def parse_pdf_options(spec: dict[str, Any]) -> PdfRenderOptions:
    include_logo = spec.get("include_logo")
    if include_logo is None:
        include_logo = True

    page_numbers = spec.get("page_numbers")
    if page_numbers is None:
        page_numbers = True

    return PdfRenderOptions(
        include_logo=bool(include_logo),
        page_numbers=bool(page_numbers),
        watermark=normalize_watermark(spec.get("watermark")),
        logo_url=(str(spec["logo_url"]).strip() if spec.get("logo_url") else None),
    )
