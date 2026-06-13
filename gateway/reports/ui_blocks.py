"""UI block dataclasses for the Reports adaptive UI."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PillOption:
    id: str
    label: str

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "label": self.label}


@dataclass
class PillSelectBlock:
    options: list[PillOption]
    mode: str = "single"  # "single" | "multi"
    allow_typed_input: bool = False
    prompt: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "pill_select",
            "options": [o.to_dict() for o in self.options],
            "mode": self.mode,
            "allow_typed_input": self.allow_typed_input,
            "prompt": self.prompt,
        }


@dataclass
class DatePreset:
    id: str
    label: str
    from_date: str
    to_date: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "from_date": self.from_date,
            "to_date": self.to_date,
        }


@dataclass
class DateQuickBlock:
    presets: list[DatePreset] = field(default_factory=list)
    prompt: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "date_quick",
            "presets": [p.to_dict() for p in self.presets],
            "prompt": self.prompt,
        }


@dataclass
class FormatSelectBlock:
    options: list[str] = field(default_factory=lambda: ["pdf", "excel", "both"])
    prompt: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "format_select",
            "options": self.options,
            "prompt": self.prompt,
        }


@dataclass
class FileReadyBlock:
    report_id: str
    filename: str
    format: str  # "pdf" | "excel" | "both"
    url: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "file_ready",
            "report_id": self.report_id,
            "filename": self.filename,
            "format": self.format,
            "url": self.url,
        }
