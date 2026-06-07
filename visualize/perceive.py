"""Step 1 — PERCEIVE: inspect dropped data structure (Layer 1 brain)."""

from __future__ import annotations

import re
from typing import Any

_ARABIC_RE = re.compile(r"[\u0600-\u06FF]")

_DATA_TYPE_LABELS = {
    "financial_pandl": "P&L Statement",
    "financial_balance_sheet": "Balance Sheet",
    "financial_cash_flow": "Cash Flow",
    "financial_trial_balance": "Trial Balance",
    "partner_ageing": "Partner Ageing",
    "general_ledger": "General Ledger",
    "project_costs": "Project Costs",
    "expense_breakdown": "Expense Breakdown",
    "revenue_analysis": "Revenue Analysis",
    "client_portfolio": "Client Portfolio",
    "vendor_analysis": "Vendor Analysis",
    "kpi_dashboard": "KPI Dashboard",
    "chart_analysis": "Chart Analysis",
    "tabular_data": "Data Table",
    "general_data": "Business Data",
}


class DataInspector:
    """Inspects dropped chat items and extracts structural metadata."""

    def inspect(self, dropped_items: list[dict]) -> dict[str, Any]:
        if not dropped_items:
            return self._empty_inspection()
        if len(dropped_items) == 1:
            result = self.inspect_single(dropped_items[0])
            result["display_type"] = _DATA_TYPE_LABELS.get(
                result.get("primary_data_type", "general_data"),
                "Business Data",
            )
            return result
        return self.inspect_multiple(dropped_items)

    def inspect_single(self, item: dict) -> dict[str, Any]:
        viz = self._normalize_viz(item.get("visualization") or {})
        text = (item.get("text") or "").strip()
        question = (item.get("question") or "").strip()

        primary_type = self.detect_data_type(viz, text, question)
        row_count = self.count_rows(viz)
        metrics = self.extract_metrics(viz)
        dimensions = self.extract_dimensions(viz)

        return {
            "item_count": 1,
            "primary_data_type": primary_type,
            "display_type": _DATA_TYPE_LABELS.get(primary_type, "Business Data"),
            "visual_type": viz.get("visual_type", "TEXT_ONLY"),
            "report_subject": self.extract_subject(viz, text, question),
            "date_range": self.extract_date_range(viz, text),
            "currency": self.extract_currency(viz, metrics),
            "language": self.detect_language(text or question),
            "metrics": metrics,
            "metric_count": len(metrics),
            "dimensions": dimensions,
            "dimension_count": len(dimensions),
            "row_count": row_count,
            "has_comparison": self.has_comparison(viz),
            "has_time_series": self.has_time_series(viz),
            "has_negatives": self.has_negative_values(viz),
            "data_completeness": self.check_completeness(viz),
            "is_summary_or_detailed": self.classify_depth(viz),
            "has_formulas": bool(viz.get("data", {}).get("formulas")),
            "question_preview": question[:120] if question else None,
        }

    def inspect_multiple(self, items: list[dict]) -> dict[str, Any]:
        singles = [self.inspect_single(item) for item in items]
        primary = singles[0]
        types = {s["primary_data_type"] for s in singles}
        return {
            "item_count": len(items),
            "items": singles,
            "primary_data_type": primary["primary_data_type"]
            if len(types) == 1
            else "mixed_bundle",
            "display_type": primary["display_type"]
            if len(types) == 1
            else f"{len(items)} related datasets",
            "visual_type": primary["visual_type"],
            "report_subject": primary.get("report_subject"),
            "date_range": next((s["date_range"] for s in singles if s.get("date_range")), None),
            "currency": primary.get("currency", "AED"),
            "language": primary.get("language", "en"),
            "metrics": [m for s in singles for m in s.get("metrics", [])],
            "metric_count": sum(s.get("metric_count", 0) for s in singles),
            "dimensions": list({d for s in singles for d in s.get("dimensions", [])}),
            "dimension_count": len({d for s in singles for d in s.get("dimensions", [])}),
            "row_count": sum(s.get("row_count", 0) for s in singles),
            "has_comparison": any(s.get("has_comparison") for s in singles),
            "has_time_series": any(s.get("has_time_series") for s in singles),
            "has_negatives": any(s.get("has_negatives") for s in singles),
            "data_completeness": min(
                (s.get("data_completeness", 1.0) for s in singles),
                default=1.0,
            ),
            "is_summary_or_detailed": max(
                singles,
                key=lambda s: _depth_rank(s.get("is_summary_or_detailed", "summary")),
            ).get("is_summary_or_detailed", "summary"),
            "has_formulas": any(s.get("has_formulas") for s in singles),
        }

    def detect_data_type(
        self,
        viz: dict,
        text: str = "",
        question: str = "",
    ) -> str:
        visual_type = (viz.get("visual_type") or "").upper()
        label = " ".join(
            filter(
                None,
                [
                    (viz.get("label") or ""),
                    (viz.get("title") or ""),
                    (viz.get("data") or {}).get("report_name", "")
                    if isinstance(viz.get("data"), dict)
                    else "",
                    question,
                    text[:200],
                ],
            )
        ).lower()

        if visual_type == "KPI_CARD":
            return "kpi_dashboard"

        if any(x in label for x in ("p&l", "profit and loss", "profit & loss", "pnl")):
            return "financial_pandl"
        if "balance sheet" in label or "balance_sheet" in label:
            return "financial_balance_sheet"
        if "cash flow" in label or "cashflow" in label:
            return "financial_cash_flow"
        if "trial balance" in label:
            return "financial_trial_balance"
        if "ageing" in label or "aging" in label:
            return "partner_ageing"
        if "ledger" in label:
            return "general_ledger"
        if "project" in label:
            return "project_costs"
        if "expense" in label:
            return "expense_breakdown"
        if "revenue" in label or "sales" in label:
            return "revenue_analysis"
        if "client" in label or "customer" in label:
            return "client_portfolio"
        if "vendor" in label or "supplier" in label:
            return "vendor_analysis"
        if visual_type == "DATA_TABLE":
            return "tabular_data"
        if visual_type == "FINANCIAL_REPORT":
            return "financial_pandl"
        if visual_type == "GROUPED_TABLE":
            return "expense_breakdown"
        if visual_type in ("BAR_CHART", "LINE_CHART"):
            return "chart_analysis"
        if visual_type == "PDF_REPORT":
            return "general_data"

        return "general_data"

    def extract_metrics(self, viz: dict) -> list[dict]:
        metrics: list[dict] = []
        kpis = viz.get("kpis") or {}
        if isinstance(kpis, dict):
            for key, val in kpis.items():
                if isinstance(val, dict):
                    metrics.append({
                        "name": key,
                        "value": val.get("value"),
                        "label": val.get("label") or key.replace("_", " ").title(),
                        "trend": val.get("trend"),
                        "unit": val.get("unit", "AED"),
                    })
                elif val is not None:
                    metrics.append({
                        "name": key,
                        "value": val,
                        "label": key.replace("_", " ").title(),
                        "trend": None,
                        "unit": "AED",
                    })
        data = viz.get("data") or {}
        if isinstance(data, dict) and isinstance(data.get("kpis"), dict):
            for key, val in data["kpis"].items():
                if not any(m["name"] == key for m in metrics):
                    if isinstance(val, dict):
                        metrics.append({
                            "name": key,
                            "value": val.get("value"),
                            "label": val.get("label") or key,
                            "trend": val.get("trend"),
                            "unit": val.get("unit", "AED"),
                        })
                    else:
                        metrics.append({
                            "name": key,
                            "value": val,
                            "label": key.replace("_", " ").title(),
                            "unit": "AED",
                        })
        return metrics

    def extract_dimensions(self, viz: dict) -> list[str]:
        dimensions: list[str] = []
        data = viz.get("data") or {}
        if not isinstance(data, dict):
            return dimensions

        visual_type = viz.get("visual_type", "")
        if visual_type == "GROUPED_TABLE":
            group_by = data.get("group_by") or []
            if isinstance(group_by, list):
                dimensions.extend(str(g) for g in group_by if g)
            groups = data.get("groups") or data.get("all_groups") or []
            if groups and not dimensions:
                sample = groups[0] if isinstance(groups[0], dict) else {}
                if sample.get("name"):
                    dimensions.append("group")
        elif visual_type == "PIVOT_TABLE":
            for key in ("rows_dim", "cols_dim"):
                if data.get(key):
                    dimensions.append(str(data[key]))
        elif data.get("group_by"):
            gb = data["group_by"]
            if isinstance(gb, list):
                dimensions.extend(str(g) for g in gb)

        return [d for d in dimensions if d]

    def count_rows(self, viz: dict) -> int:
        data = viz.get("data") or {}
        if not isinstance(data, dict):
            return 0

        if isinstance(data.get("rows"), list):
            return len(data["rows"])
        if isinstance(data.get("all_rows"), list):
            return len(data["all_rows"])
        groups = data.get("groups") or data.get("all_groups")
        if isinstance(groups, list):
            total = 0
            for group in groups:
                if isinstance(group, dict):
                    rows = group.get("rows") or []
                    total += len(rows) if isinstance(rows, list) else 1
                else:
                    total += 1
            return total or len(groups)
        if viz.get("total_records") is not None:
            return int(viz["total_records"])
        if data.get("total_records") is not None:
            return int(data["total_records"])
        if isinstance(data.get("labels"), list):
            return len(data["labels"])
        if isinstance(data.get("values"), list):
            return len(data["values"])
        return 0

    def has_comparison(self, viz: dict) -> bool:
        data = viz.get("data") or {}
        if not isinstance(data, dict):
            return False
        return bool(
            data.get("compare_with")
            or data.get("periods")
            or data.get("prior_period")
            or data.get("comparison"),
        )

    def has_time_series(self, viz: dict) -> bool:
        data = viz.get("data") or {}
        if not isinstance(data, dict):
            return False
        group_by = data.get("group_by") or []
        group_str = " ".join(str(g).lower() for g in group_by) if isinstance(group_by, list) else ""
        return bool(
            data.get("monthly_data")
            or data.get("quarterly_data")
            or "month" in group_str
            or "period" in group_str
            or viz.get("visual_type") == "LINE_CHART",
        )

    def has_negative_values(self, viz: dict) -> bool:
        return self._scan_numeric(viz, negative_only=True)

    def classify_depth(self, viz: dict) -> str:
        row_count = self.count_rows(viz)
        visual_type = viz.get("visual_type", "")
        if visual_type == "KPI_CARD" and row_count == 0:
            return "kpi_only"
        if row_count == 0:
            metrics = self.extract_metrics(viz)
            return "kpi_only" if metrics else "summary"
        if row_count < 10:
            return "summary"
        if row_count < 50:
            return "standard"
        return "detailed"

    def extract_subject(self, viz: dict, text: str, question: str = "") -> str | None:
        for candidate in (
            viz.get("label"),
            viz.get("title"),
            (viz.get("data") or {}).get("report_name") if isinstance(viz.get("data"), dict) else None,
            question,
        ):
            if candidate and str(candidate).strip():
                return str(candidate).strip()[:200]
        if text:
            first_line = text.split("\n", 1)[0].strip()
            if first_line:
                return first_line[:200]
        return None

    def extract_date_range(self, viz: dict, text: str) -> str | None:
        data = viz.get("data") if isinstance(viz.get("data"), dict) else {}
        date_from = viz.get("date_from") or data.get("date_from")
        date_to = viz.get("date_to") or data.get("date_to")
        if date_from and date_to:
            return self._format_range(date_from, date_to)
        if date_from:
            return f"From {self._format_date(date_from)}"
        if date_to:
            return f"Through {self._format_date(date_to)}"

        match = re.search(
            r"(\d{4}-\d{2}-\d{2})\s*(?:to|–|-|through)\s*(\d{4}-\d{2}-\d{2})",
            text,
            re.I,
        )
        if match:
            return self._format_range(match.group(1), match.group(2))
        return None

    def extract_currency(self, viz: dict, metrics: list[dict] | None = None) -> str:
        metrics = metrics or self.extract_metrics(viz)
        for metric in metrics:
            unit = metric.get("unit")
            if unit and str(unit).upper() not in ("", "NONE", "N/A"):
                return str(unit).upper()
        return "AED"

    def detect_language(self, text: str) -> str:
        if not text:
            return "en"
        arabic_chars = len(_ARABIC_RE.findall(text))
        if arabic_chars > max(8, len(text) * 0.15):
            return "ar"
        return "en"

    def check_completeness(self, viz: dict) -> float:
        """0.0–1.0 score for how complete the dropped payload is."""
        score = 0.0
        checks = 0
        visual_type = viz.get("visual_type")
        if visual_type:
            score += 1
        checks += 1
        data = viz.get("data")
        if isinstance(data, dict) and data:
            score += 1
        checks += 1
        if self.count_rows(viz) > 0 or self.extract_metrics(viz):
            score += 1
        checks += 1
        if viz.get("label") or viz.get("title"):
            score += 1
        checks += 1
        return round(score / checks, 2) if checks else 0.0

    def _normalize_viz(self, viz: dict) -> dict:
        if not viz:
            return {}
        normalized = dict(viz)
        data = normalized.get("data")
        if isinstance(data, dict):
            if not normalized.get("kpis") and isinstance(data.get("kpis"), dict):
                normalized["kpis"] = data["kpis"]
            for key in ("date_from", "date_to", "report_name", "label", "total_records"):
                if normalized.get(key) is None and data.get(key) is not None:
                    normalized[key] = data[key]
        return normalized

    def _empty_inspection(self) -> dict[str, Any]:
        return {
            "item_count": 0,
            "primary_data_type": "general_data",
            "display_type": "No data",
            "visual_type": "TEXT_ONLY",
            "report_subject": None,
            "date_range": None,
            "currency": "AED",
            "language": "en",
            "metrics": [],
            "metric_count": 0,
            "dimensions": [],
            "dimension_count": 0,
            "row_count": 0,
            "has_comparison": False,
            "has_time_series": False,
            "has_negatives": False,
            "data_completeness": 0.0,
            "is_summary_or_detailed": "summary",
            "has_formulas": False,
        }

    def _scan_numeric(self, viz: dict, negative_only: bool = False) -> bool:
        data = viz.get("data") or {}

        def check_value(val: Any) -> bool:
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                return val < 0 if negative_only else True
            return False

        if isinstance(data, dict):
            for row in data.get("rows") or data.get("all_rows") or []:
                if isinstance(row, dict):
                    for cell in row.values():
                        if check_value(cell):
                            return True
                elif isinstance(row, (list, tuple)):
                    for cell in row:
                        if check_value(cell):
                            return True
            for group in data.get("groups") or data.get("all_groups") or []:
                if isinstance(group, dict):
                    for row in group.get("rows") or []:
                        if isinstance(row, dict):
                            for cell in row.values():
                                if check_value(cell):
                                    return True
        kpis = viz.get("kpis") or {}
        if isinstance(kpis, dict):
            for val in kpis.values():
                v = val.get("value") if isinstance(val, dict) else val
                if check_value(v):
                    return True
        return False

    @staticmethod
    def _format_date(value: str) -> str:
        if not value:
            return ""
        try:
            parts = str(value)[:10].split("-")
            if len(parts) == 3:
                year, month, day = parts
                months = (
                    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
                    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
                )
                m = int(month)
                return f"{months[m - 1]} {int(day)}, {year}"
        except (ValueError, IndexError):
            pass
        return str(value)[:10]

    def _format_range(self, date_from: str, date_to: str) -> str:
        return f"{self._format_date(date_from)} – {self._format_date(date_to)}"


def _depth_rank(depth: str) -> int:
    return {"kpi_only": 0, "summary": 1, "standard": 2, "detailed": 3}.get(depth, 1)
