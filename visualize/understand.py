"""Step 2 — UNDERSTAND: pattern detection and insights (Layer 1 brain)."""

from __future__ import annotations

from typing import Any


class PatternAnalyzer:
    """Detects meaningful patterns — trends, outliers, concentration, variances."""

    def analyze(
        self,
        data: dict[str, Any],
        inspection: dict[str, Any],
    ) -> dict[str, Any]:
        raw = self._merged_data(data, inspection)
        return {
            "trends": self.detect_trends(raw, inspection),
            "outliers": self.detect_outliers(raw, inspection),
            "concentrations": self.detect_concentration(raw, inspection),
            "variances": self.detect_variances(raw, inspection),
            "correlations": self.detect_correlations(raw, inspection),
            "thresholds": self.check_business_thresholds(raw, inspection),
            "completeness": self.assess_completeness(raw, inspection),
            "findings": [],
        }

    def build_findings(self, analysis: dict[str, Any]) -> list[dict[str, Any]]:
        """Flatten analysis into UI-ready finding cards."""
        findings: list[dict[str, Any]] = []

        for trend in analysis.get("trends", []):
            direction = trend.get("direction", "up")
            findings.append({
                "icon": "trend_up" if direction == "up" else "trend_down",
                "text": trend.get("insight", ""),
                "color": "green" if direction == "up" else "amber",
                "category": "trend",
            })

        for item in analysis.get("outliers", []):
            findings.append({
                "icon": "outlier",
                "text": item.get("insight", ""),
                "color": "blue",
                "category": "outlier",
            })

        for item in analysis.get("concentrations", []):
            findings.append({
                "icon": "concentration",
                "text": item.get("insight", ""),
                "color": "blue",
                "category": "concentration",
            })

        for item in analysis.get("variances", []):
            color = "green" if item.get("direction") == "favorable" else "amber"
            findings.append({
                "icon": "warning" if color == "amber" else "trend_up",
                "text": item.get("insight", ""),
                "color": color,
                "category": "variance",
            })

        for item in analysis.get("thresholds", []):
            severity = item.get("severity", "info")
            color = {"critical": "red", "warning": "amber", "info": "blue"}.get(
                severity, "amber"
            )
            findings.append({
                "icon": "warning" if severity != "info" else "info",
                "text": item.get("insight", ""),
                "color": color,
                "category": "threshold",
            })

        return findings[:8]

    def detect_trends(self, data: dict, ins: dict) -> list[dict]:
        if not ins.get("has_time_series"):
            return []

        time_data = self.extract_time_series(data)
        if len(time_data) < 2:
            return []

        first = time_data[0].get("value") or 0
        last = time_data[-1].get("value") or 0
        if not first:
            return []

        change_pct = ((last - first) / abs(first)) * 100
        if abs(change_pct) < 10:
            return []

        metric = time_data[0].get("metric", "Value")
        direction = "up" if change_pct > 0 else "down"
        return [{
            "type": "directional",
            "metric": metric,
            "direction": direction,
            "magnitude": abs(change_pct),
            "from_period": time_data[0].get("period"),
            "to_period": time_data[-1].get("period"),
            "insight": (
                f"{metric} {'grew' if change_pct > 0 else 'declined'} "
                f"{abs(change_pct):.1f}% from {time_data[0].get('period', 'start')} "
                f"to {time_data[-1].get('period', 'end')}"
            ),
        }]

    def detect_outliers(self, data: dict, ins: dict) -> list[dict]:
        rows = self._iter_rows(data)
        if len(rows) < 5:
            return []

        values: list[tuple[float, dict]] = []
        for row in rows:
            val = self.numeric_value(row)
            if val is not None:
                values.append((val, row))

        if not values:
            return []

        nums = [v[0] for v in values]
        mean = sum(nums) / len(nums)
        variance = sum((x - mean) ** 2 for x in nums) / len(nums)
        stddev = variance ** 0.5
        if stddev < 1e-9:
            return []

        outliers = []
        for val, row in values:
            z = (val - mean) / stddev
            if abs(z) > 2:
                outliers.append({
                    "value": val,
                    "row": row,
                    "deviation": z,
                    "is_high": val > mean,
                    "insight": (
                        f"{self.label_row(row)}: {ins.get('currency', 'AED')} "
                        f"{val:,.0f} is {abs(z):.1f}σ from the mean"
                    ),
                })

        outliers.sort(key=lambda x: abs(x["deviation"]), reverse=True)
        return outliers[:3]

    def detect_concentration(self, data: dict, ins: dict) -> list[dict]:
        rows = self._iter_rows(data)
        if len(rows) < 5:
            return []

        values = sorted(
            [
                (self.label_row(row), self.numeric_value(row))
                for row in rows
                if self.numeric_value(row) is not None
            ],
            key=lambda x: x[1],
            reverse=True,
        )
        if not values:
            return []

        total = sum(v[1] for v in values)
        if total == 0:
            return []

        cumulative = 0.0
        for index, (label, val) in enumerate(values):
            cumulative += val
            pct = cumulative / total * 100
            if pct >= 80:
                top_n = index + 1
                top_pct = (top_n / len(values)) * 100
                return [{
                    "type": "concentration",
                    "top_count": top_n,
                    "total_count": len(values),
                    "top_share": pct,
                    "top_items": [v[0] for v in values[:top_n]],
                    "insight": (
                        f"Top {top_n} of {len(values)} items "
                        f"({top_pct:.0f}% of categories) account for "
                        f"{pct:.0f}% of value"
                    ),
                }]
        return []

    def detect_variances(self, data: dict, ins: dict) -> list[dict]:
        if not ins.get("has_comparison"):
            return []

        variances = []
        comparison = data.get("compare_with") or data.get("comparison") or {}
        metrics = data.get("metrics") or {}

        if isinstance(comparison, dict) and isinstance(metrics, dict):
            for metric, current in metrics.items():
                prior = comparison.get(metric)
                if prior is None or prior == 0 or not isinstance(current, (int, float)):
                    continue
                variance_pct = (current - prior) / abs(prior) * 100
                if abs(variance_pct) > 5:
                    variances.append({
                        "metric": metric,
                        "current": current,
                        "prior": prior,
                        "variance_pct": variance_pct,
                        "direction": (
                            "favorable"
                            if self.is_favorable(metric, variance_pct)
                            else "unfavorable"
                        ),
                        "insight": (
                            f"{metric.replace('_', ' ').title()} "
                            f"{self.direction_word(metric, variance_pct)} "
                            f"{abs(variance_pct):.1f}% vs prior period"
                        ),
                    })

        kpis = data.get("kpis") or {}
        if isinstance(kpis, dict):
            for key, val in kpis.items():
                if not isinstance(val, dict):
                    continue
                change = val.get("change_pct") or val.get("variance_pct")
                if change is not None and abs(float(change)) > 5:
                    variances.append({
                        "metric": key,
                        "variance_pct": float(change),
                        "direction": (
                            "favorable"
                            if self.is_favorable(key, float(change))
                            else "unfavorable"
                        ),
                        "insight": (
                            f"{val.get('label') or key}: "
                            f"{self.direction_word(key, float(change))} "
                            f"{abs(float(change)):.1f}% vs prior period"
                        ),
                    })

        return variances[:5]

    def detect_correlations(self, data: dict, ins: dict) -> list[dict]:
        """Lightweight correlation hints when multiple metrics move together."""
        kpis = data.get("kpis") or {}
        if not isinstance(kpis, dict) or len(kpis) < 2:
            return []

        trends = []
        for key, val in kpis.items():
            if isinstance(val, dict) and val.get("trend"):
                trends.append((key, val["trend"]))

        if len(trends) >= 2:
            up = sum(1 for _, t in trends if str(t).lower() in ("up", "increase", "positive"))
            down = len(trends) - up
            if up >= 2 and down == 0:
                return [{
                    "type": "correlation",
                    "insight": "Multiple KPIs are trending upward together",
                }]
            if down >= 2 and up == 0:
                return [{
                    "type": "correlation",
                    "insight": "Multiple KPIs are trending downward together",
                }]
        return []

    def check_business_thresholds(self, data: dict, ins: dict) -> list[dict]:
        flags: list[dict] = []
        kpis = data.get("kpis") or {}

        margin = None
        for key in ("margin_pct", "gross_margin", "margin", "net_margin"):
            raw = kpis.get(key)
            if isinstance(raw, dict):
                margin = raw.get("value")
            elif raw is not None:
                margin = raw
            if margin is not None:
                break

        if margin is not None:
            try:
                margin = float(margin)
            except (TypeError, ValueError):
                margin = None

        if margin is not None:
            if margin < 0:
                flags.append({
                    "severity": "critical",
                    "metric": "margin",
                    "value": margin,
                    "insight": "Operating at a loss — immediate attention required",
                })
            elif margin < 10:
                flags.append({
                    "severity": "warning",
                    "metric": "margin",
                    "value": margin,
                    "insight": "Margin below construction industry norm (10–20%)",
                })
            elif margin > 35:
                flags.append({
                    "severity": "info",
                    "metric": "margin",
                    "value": margin,
                    "insight": "Margin notably higher than industry average — verify",
                })

        dso = kpis.get("days_sales_outstanding")
        if isinstance(dso, dict):
            dso = dso.get("value")
        if dso and float(dso) > 90:
            flags.append({
                "severity": "warning",
                "metric": "dso",
                "value": dso,
                "insight": f"DSO {float(dso):.0f} days — collection cycle longer than ideal",
            })

        budget_var = data.get("budget_variance_pct")
        if budget_var is not None and float(budget_var) > 10:
            flags.append({
                "severity": "warning",
                "metric": "budget",
                "value": budget_var,
                "insight": f"Over budget by {float(budget_var):.0f}%",
            })

        if ins.get("has_negatives") and ins.get("primary_data_type", "").startswith("financial"):
            flags.append({
                "severity": "warning",
                "metric": "negatives",
                "insight": "Includes negative values — losses or credits worth highlighting",
            })

        return flags

    def assess_completeness(self, data: dict, ins: dict) -> dict:
        score = ins.get("data_completeness", 0)
        notes = []
        if score < 0.5:
            notes.append("Limited structured data — report will lean on narrative summary")
        if ins.get("row_count", 0) == 0 and not ins.get("metrics"):
            notes.append("No tabular rows detected — KPI-level output recommended")
        return {"score": score, "notes": notes}

    def extract_time_series(self, data: dict) -> list[dict]:
        series: list[dict] = []

        monthly = data.get("monthly_data") or data.get("quarterly_data")
        if isinstance(monthly, list):
            for point in monthly:
                if isinstance(point, dict):
                    series.append({
                        "period": point.get("period") or point.get("month") or point.get("label"),
                        "value": point.get("value") or point.get("amount"),
                        "metric": point.get("metric", "Value"),
                    })

        rows = data.get("rows") or data.get("all_rows") or []
        for row in rows:
            if not isinstance(row, dict):
                continue
            period = row.get("month") or row.get("period") or row.get("date")
            val = self.numeric_value(row)
            if period and val is not None:
                series.append({
                    "period": str(period),
                    "value": val,
                    "metric": row.get("metric", "Value"),
                })

        chart_rows = data.get("rows")
        if isinstance(chart_rows, list) and data.get("labels"):
            labels = data["labels"]
            values = data.get("values") or []
            for label, val in zip(labels, values):
                if isinstance(val, (int, float)):
                    series.append({"period": str(label), "value": val, "metric": "Value"})

        return series

    def label_row(self, row: Any) -> str:
        if isinstance(row, dict):
            for key in ("name", "label", "account_name", "partner", "project", "category"):
                if row.get(key):
                    return str(row[key])
            for val in row.values():
                if isinstance(val, str) and val.strip():
                    return val.strip()[:80]
        if isinstance(row, (list, tuple)) and row:
            return str(row[0])
        return "Item"

    def numeric_value(self, row: Any) -> float | None:
        if isinstance(row, dict):
            for key in ("value", "amount", "balance", "total", "debit", "credit", "net"):
                if key in row and isinstance(row[key], (int, float)):
                    return float(row[key])
            for val in row.values():
                if isinstance(val, (int, float)) and not isinstance(val, bool):
                    return float(val)
        if isinstance(row, (list, tuple)):
            for cell in row[1:]:
                if isinstance(cell, (int, float)):
                    return float(cell)
        return None

    def is_favorable(self, metric: str, variance_pct: float) -> bool:
        metric_l = metric.lower()
        if any(x in metric_l for x in ("expense", "cost", "loss", "debit")):
            return variance_pct < 0
        return variance_pct > 0

    def direction_word(self, metric: str, variance_pct: float) -> str:
        if self.is_favorable(metric, variance_pct):
            return "improved"
        return "worsened"

    def _merged_data(self, data: dict, inspection: dict) -> dict:
        merged = dict(data) if data else {}
        if inspection.get("metrics") and "kpis" not in merged:
            merged["kpis"] = {
                m["name"]: {
                    "value": m.get("value"),
                    "label": m.get("label"),
                    "trend": m.get("trend"),
                    "unit": m.get("unit"),
                }
                for m in inspection["metrics"]
            }
        return merged

    def _iter_rows(self, data: dict) -> list:
        rows = list(data.get("rows") or data.get("all_rows") or [])
        if rows:
            return rows
        for group in data.get("groups") or data.get("all_groups") or []:
            if isinstance(group, dict):
                rows.extend(group.get("rows") or [])
        return rows
