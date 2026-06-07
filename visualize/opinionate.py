"""Step 3 — OPINIONATE: format, layout, and visualization recommendations."""

from __future__ import annotations

from typing import Any

_LAYOUT_DISPLAY = {
    "executive_summary": "Executive Summary",
    "detailed_analytical": "Detailed Analytical",
    "comparative": "Comparative Report",
    "standard_report": "Standard Report",
    "pivot_ready": "Pivot-Ready Workbook",
    "multi_sheet": "Multi-Sheet Workbook",
    "single_sheet": "Single Sheet",
    "boardroom": "Boardroom Deck",
}

_THEME_DISPLAY = {
    "elegant_gold": "Elegant Gold",
    "corporate_blue": "Corporate Blue",
    "modern_dark": "Modern Dark",
    "minimalist": "Minimalist",
}


class FormatRecommender:
    """Forms opinions about the best report approach for inspected data."""

    def recommend(
        self,
        inspection: dict[str, Any],
        analysis: dict[str, Any],
    ) -> dict[str, Any]:
        fmt = self.choose_format(inspection, analysis)
        layout = self.choose_layout(inspection, analysis, fmt)
        visualizations = self.choose_visualizations(inspection, analysis)
        theme = self.choose_theme(inspection)
        sections = self.build_sections(inspection, analysis, visualizations)

        findings = analysis.get("findings") or []
        reasoning_parts = [self.format_reason(fmt, inspection)]
        if findings:
            reasoning_parts.append(
                f"Your data surfaced {len(findings)} meaningful finding(s). "
                f"{_LAYOUT_DISPLAY.get(layout, layout)} highlights what matters "
                "without overwhelming detail."
            )

        return {
            "format": fmt,
            "format_display": fmt.upper(),
            "format_reasoning": " ".join(reasoning_parts),
            "layout": layout,
            "layout_display": _LAYOUT_DISPLAY.get(layout, layout.replace("_", " ").title()),
            "theme": theme,
            "theme_display": _THEME_DISPLAY.get(theme, theme.replace("_", " ").title()),
            "visualizations": visualizations,
            "sections": sections,
            "section_labels": [s.get("label") or s.get("type", "") for s in sections],
            "estimated_pages": self.estimate_pages(sections),
            "language": inspection.get("language", "en"),
            "alternatives": self.suggest_alternatives(fmt, inspection, analysis),
            "reasoning": " ".join(reasoning_parts),
        }

    def choose_format(self, ins: dict, analysis: dict) -> str:
        row_count = ins.get("row_count", 0)
        has_lots_of_detail = row_count > 50
        has_calculations = ins.get("has_formulas", False)
        is_executive = ins.get("is_summary_or_detailed") in ("summary", "kpi_only")
        finding_count = len(analysis.get("findings") or [])

        if has_lots_of_detail or has_calculations:
            return "excel"
        if is_executive and finding_count >= 2 and row_count < 30:
            return "ppt"
        return "pdf"

    def choose_layout(self, ins: dict, analysis: dict, fmt: str) -> str:
        row_count = ins.get("row_count", 0)
        findings = analysis.get("findings") or []
        has_findings = len(findings) > 2

        if fmt == "pdf":
            if row_count < 20 and has_findings:
                return "executive_summary"
            if row_count > 100:
                return "detailed_analytical"
            if ins.get("has_comparison"):
                return "comparative"
            return "standard_report"

        if fmt == "excel":
            if row_count > 200:
                return "pivot_ready"
            if len(ins.get("dimensions", [])) > 2:
                return "multi_sheet"
            return "single_sheet"

        if fmt == "ppt":
            return "boardroom"

        return "standard_report"

    def choose_visualizations(self, ins: dict, analysis: dict) -> list[dict]:
        viz_list: list[dict] = []

        if ins.get("metrics"):
            viz_list.append({
                "type": "kpi_grid",
                "priority": 1,
                "reason": "Surface key metrics upfront",
            })

        if ins.get("has_time_series"):
            viz_list.append({
                "type": "line_chart",
                "priority": 2,
                "reason": "Show trend over time",
            })

        if analysis.get("concentrations"):
            viz_list.append({
                "type": "donut_chart",
                "priority": 2,
                "reason": "Visualize concentration pattern",
            })

        row_count = ins.get("row_count", 0)
        if 5 <= row_count <= 20:
            viz_list.append({
                "type": "horizontal_bar",
                "priority": 3,
                "reason": "Compare categories",
            })

        if ins.get("has_comparison"):
            viz_list.append({
                "type": "grouped_bar",
                "priority": 2,
                "reason": "Side-by-side period comparison",
            })

        if row_count > 0:
            viz_list.append({
                "type": "data_table",
                "priority": 4,
                "reason": "Detailed breakdown",
            })

        if analysis.get("outliers"):
            viz_list.append({
                "type": "outlier_callout",
                "priority": 3,
                "reason": "Highlight unusual values",
            })

        return sorted(viz_list, key=lambda x: x["priority"])

    def choose_theme(self, ins: dict) -> str:
        data_type = ins.get("primary_data_type", "")
        if "financial" in data_type:
            return "elegant_gold"
        if "project" in data_type:
            return "corporate_blue"
        return "elegant_gold"

    def build_sections(
        self,
        ins: dict,
        analysis: dict,
        vizs: list[dict],
    ) -> list[dict]:
        sections: list[dict] = []

        sections.append({
            "type": "cover",
            "order": 1,
            "label": "Cover page with company logo",
            "config": {
                "title": ins.get("report_subject") or ins.get("display_type"),
                "period": ins.get("date_range"),
                "company": "Elrace Cos. & Gen. Cont. CO.",
            },
        })

        findings = analysis.get("findings") or []
        if findings or analysis.get("trends") or analysis.get("variances"):
            sections.append({
                "type": "executive_summary",
                "order": 2,
                "label": f"Executive summary ({min(3, len(findings))} findings)",
                "config": {"findings": self.top_findings(analysis, count=3)},
            })

        if ins.get("metrics"):
            count = ins.get("metric_count", len(ins.get("metrics", [])))
            sections.append({
                "type": "kpi_dashboard",
                "order": 3,
                "label": f"KPI dashboard ({count} metrics)",
                "config": {"metrics": ins.get("metrics", [])},
            })

        chart_viz = next((v for v in vizs if v["priority"] <= 2), None)
        if chart_viz:
            label_map = {
                "line_chart": "Trend chart",
                "donut_chart": "Category breakdown chart",
                "grouped_bar": "Period comparison chart",
                "horizontal_bar": "Category comparison chart",
                "kpi_grid": "KPI overview",
            }
            sections.append({
                "type": "primary_chart",
                "order": 4,
                "label": label_map.get(chart_viz["type"], "Primary chart"),
                "config": chart_viz,
            })

        insight_count = (
            len(analysis.get("concentrations") or [])
            + len(analysis.get("outliers") or [])
            + len(analysis.get("thresholds") or [])
        )
        if insight_count:
            sections.append({
                "type": "insights",
                "order": 5,
                "label": "Insight callouts",
                "config": {
                    "concentrations": analysis.get("concentrations"),
                    "outliers": analysis.get("outliers"),
                    "thresholds": analysis.get("thresholds"),
                },
            })

        row_count = ins.get("row_count", 0)
        if row_count > 0:
            top_n = 20 if row_count > 50 else None
            label = f"Detail table (top {top_n})" if top_n else "Detail table"
            sections.append({
                "type": "data_table",
                "order": 6,
                "label": label,
                "config": {"show_top_n": top_n},
            })

        if analysis.get("thresholds") or analysis.get("variances"):
            sections.append({
                "type": "recommendations",
                "order": 7,
                "label": "Recommendations section",
                "config": {"items": self.generate_recommendations(analysis)},
            })

        return sections

    def format_reason(self, fmt: str, ins: dict) -> str:
        reasons = {
            "pdf": (
                "PDF is best for sharing this kind of report formally — "
                "preserves formatting and is print-ready."
            ),
            "excel": (
                f"Excel suits your {ins.get('row_count', 0)} records — "
                "easy to filter, sort, and analyze further."
            ),
            "ppt": (
                "PowerPoint format fits an executive summary — "
                "ready for a board or leadership presentation."
            ),
        }
        return reasons.get(fmt, "This format fits your data shape and audience.")

    def suggest_alternatives(
        self,
        primary: str,
        ins: dict,
        analysis: dict,
    ) -> list[dict]:
        options = []
        row_count = ins.get("row_count", 0)

        if primary != "excel" and row_count > 20:
            options.append({
                "format": "excel",
                "label": "Detailed Excel",
                "description": (
                    f"All {row_count} records with pivot-ready tables "
                    "and charts. Best for further analysis."
                ),
            })

        if primary != "ppt":
            options.append({
                "format": "ppt",
                "label": "Board Presentation",
                "description": (
                    "8-slide deck ready for executive meeting "
                    "with key findings upfront."
                ),
            })

        if primary != "pdf":
            options.append({
                "format": "pdf",
                "label": "Formal PDF Report",
                "description": "Print-ready report with cover, charts, and detail tables.",
            })

        if ins.get("has_comparison") and primary != "pdf":
            options.append({
                "format": "pdf",
                "layout": "comparative",
                "label": "Comparative Report",
                "description": "Side-by-side periods with variance analysis.",
            })

        return options[:3]

    def estimate_pages(self, sections: list[dict]) -> int:
        return max(2, min(12, len(sections) + 1))

    def top_findings(self, analysis: dict, count: int = 3) -> list[str]:
        findings = analysis.get("findings") or []
        return [f.get("text", "") for f in findings[:count] if f.get("text")]

    def generate_recommendations(self, analysis: dict) -> list[str]:
        items: list[str] = []
        for flag in analysis.get("thresholds") or []:
            if flag.get("severity") in ("critical", "warning"):
                items.append(flag.get("insight", ""))
        for var in analysis.get("variances") or []:
            if var.get("direction") == "unfavorable":
                items.append(var.get("insight", ""))
        if not items and analysis.get("trends"):
            trend = analysis["trends"][0]
            items.append(
                f"Monitor {trend.get('metric', 'performance')} — "
                f"{trend.get('direction', 'change')} trend detected"
            )
        return [i for i in items if i][:4]
