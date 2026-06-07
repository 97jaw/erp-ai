# VISUALIZE AGENT — LAYER 1: SMART ANALYSIS BRAIN

> **Goal:** Before asking format questions, the Visualize agent must SEE the data, UNDERSTAND it, FORM OPINIONS about it, and PROACTIVELY recommend the best approach. This layer is the agent's brain — without this, all templates feel mechanical.

> **Layer Scope:** Complete data analysis pipeline + UI feedback showing analysis in real time. After this layer, user sees a thinking, intelligent agent — not a form-filler.

> **Read first:** `VISUALIZE_AGENT_PLAN.md`, `PRODUCT_QUALITY_FRAMEWORK.md`, `MAIN_SCREENS_LAYOUT_PLAN.md`

---

# PART I — THE PHILOSOPHY

## 1. From Form-Filler to Analyst

```
BEFORE (current basic flow):
  User drops data
  Agent: "What format?"
  User: "PDF"
  Agent: "What theme?"
  User: "Corporate"
  Agent: [generates basic PDF]
  
  Feels like: filling out a web form
  Problem: agent has no opinion, no value-add

AFTER (Layer 1 in place):
  User drops data
  Agent: [analyzing for 1-2 seconds, visible in UI]
  Agent: "I see 247 expense records across 12 months 
          with 8 categories. Total: AED 4.2M. 
          Notable: Wages grew 18% while revenue 
          only 12% — worth highlighting.
          
          I recommend a PDF executive summary with:
          • Monthly trend chart
          • Category breakdown (donut)
          • Top 10 expense items
          • Variance callouts
          
          Should I proceed, or do you want something different?"
  
  Feels like: talking to a senior analyst
  Value: insights before user even asks
```

## 2. The Four-Step Brain Process

```
STEP 1: PERCEIVE
  → Inspect raw data structure
  → Identify what was dropped
  → Categorize the data type
  → Extract metadata (size, shape, fields)

STEP 2: UNDERSTAND
  → Analyze patterns
  → Detect anomalies
  → Find relationships
  → Identify the "story" in the data

STEP 3: OPINIONATE
  → Form a recommended approach
  → Choose best visualizations
  → Surface key insights
  → Suggest the right format

STEP 4: PROPOSE
  → Present a complete plan to user
  → Show preview thumbnails of what will be built
  → Accept refinements
  → Lock in choices and build
```

---

# PART II — STEP 1: PERCEIVE

## 3. Data Inspection Engine

```python
# visualize/perceive.py

class DataInspector:
    """
    Inspects dropped data and extracts structural metadata.
    First step of analysis brain.
    """
    
    def inspect(self, dropped_items: list[dict]) -> dict:
        """
        Analyze what was dropped and return rich metadata.
        """
        if len(dropped_items) == 1:
            return self.inspect_single(dropped_items[0])
        return self.inspect_multiple(dropped_items)
    
    def inspect_single(self, item: dict) -> dict:
        """Inspect a single dropped response."""
        viz = item.get("visualization", {})
        text = item.get("text", "")
        
        return {
            "item_count": 1,
            "primary_data_type": self.detect_data_type(viz),
            "visual_type": viz.get("visual_type", "TEXT_ONLY"),
            "report_subject": self.extract_subject(viz, text),
            "date_range": self.extract_date_range(viz, text),
            "currency": self.extract_currency(viz),
            "language": self.detect_language(text),
            "metrics": self.extract_metrics(viz),
            "dimensions": self.extract_dimensions(viz),
            "row_count": self.count_rows(viz),
            "has_comparison": self.has_comparison(viz),
            "has_time_series": self.has_time_series(viz),
            "has_negatives": self.has_negative_values(viz),
            "data_completeness": self.check_completeness(viz),
            "is_summary_or_detailed": self.classify_depth(viz),
        }
    
    def detect_data_type(self, viz: dict) -> str:
        """
        Classify what kind of business data this is.
        """
        visual_type = viz.get("visual_type", "")
        label = (viz.get("label") or "").lower()
        
        if "p&l" in label or "profit" in label or "loss" in label:
            return "financial_pandl"
        if "balance" in label:
            return "financial_balance_sheet"
        if "cash" in label:
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
        
        return "general_data"
    
    def extract_metrics(self, viz: dict) -> list[dict]:
        """Find all numeric metrics in the data."""
        metrics = []
        
        if viz.get("kpis"):
            for k, v in viz["kpis"].items():
                metrics.append({
                    "name": k,
                    "value": v.get("value"),
                    "label": v.get("label"),
                    "trend": v.get("trend"),
                    "unit": v.get("unit", "AED"),
                })
        
        return metrics
    
    def extract_dimensions(self, viz: dict) -> list[str]:
        """Find categorical dimensions (project, client, account, etc.)."""
        dimensions = []
        data = viz.get("data", {})
        
        # Detect from visual_type
        if viz.get("visual_type") == "GROUPED_TABLE":
            dimensions = data.get("group_by", [])
        elif viz.get("visual_type") == "PIVOT_TABLE":
            dimensions = [data.get("rows_dim"), data.get("cols_dim")]
        
        return [d for d in dimensions if d]
    
    def count_rows(self, viz: dict) -> int:
        """Total record count."""
        data = viz.get("data", {})
        if "rows" in data:
            return len(data["rows"])
        if "total_records" in viz:
            return viz["total_records"]
        return 0
    
    def has_comparison(self, viz: dict) -> bool:
        """Detect period-over-period comparison."""
        data = viz.get("data", {})
        return bool(data.get("compare_with") or data.get("periods"))
    
    def has_time_series(self, viz: dict) -> bool:
        """Data spans multiple time periods."""
        data = viz.get("data", {})
        return bool(
            data.get("monthly_data") or
            data.get("quarterly_data") or
            "month" in str(data.get("group_by", []))
        )
    
    def has_negative_values(self, viz: dict) -> bool:
        """Check for losses/negative values."""
        data = viz.get("data", {})
        rows = data.get("rows", [])
        for row in rows:
            for cell in (row.values() if isinstance(row, dict) else row):
                if isinstance(cell, (int, float)) and cell < 0:
                    return True
        return False
    
    def classify_depth(self, viz: dict) -> str:
        """Is this summary-level or detailed?"""
        row_count = self.count_rows(viz)
        if row_count == 0:
            return "kpi_only"
        if row_count < 10:
            return "summary"
        if row_count < 50:
            return "standard"
        return "detailed"
```

## 4. UI: Real-Time Inspection Feedback

```
When user drops an item, IMMEDIATELY show inspection in panel:

┌────────────────────────────────────┐
│  ◊ Visualize                       │
├────────────────────────────────────┤
│                                    │
│  Analyzing your data...            │
│                                    │
│  ● Detected: P&L Statement         │ ← appears immediately
│  ● Range: Jan – Apr 2026 (4 mo)    │ ← Then this
│  ● Records: 247 transactions       │ ← Then this
│  ● 8 expense categories            │ ← Then this
│  ● Includes negative values        │ ← Then this
│                                    │
│  ▓▓▓▓▓▓▓▓▓░ Analyzing patterns... │ ← progress bar
│                                    │
└────────────────────────────────────┘

Each line appears as soon as detected.
Creates feeling of "AI is thinking".
Subtle bullet pulse on appearance.
No spinner, just progressive disclosure.

Timing:
  Each line: 100-150ms apart
  Total perception step: ~1 second
  Feels intelligent without being slow
```

---

# PART III — STEP 2: UNDERSTAND

## 5. Pattern Detection Engine

```python
# visualize/understand.py

class PatternAnalyzer:
    """
    Detects meaningful patterns in the data.
    Goes beyond structure to find STORY.
    """
    
    def analyze(self, data: dict, inspection: dict) -> dict:
        """
        Run all pattern detectors and return findings.
        """
        return {
            "trends": self.detect_trends(data, inspection),
            "outliers": self.detect_outliers(data, inspection),
            "concentrations": self.detect_concentration(data, inspection),
            "variances": self.detect_variances(data, inspection),
            "correlations": self.detect_correlations(data, inspection),
            "thresholds": self.check_business_thresholds(data, inspection),
            "completeness": self.assess_completeness(data, inspection),
        }
    
    def detect_trends(self, data: dict, ins: dict) -> list[dict]:
        """Identify directional trends."""
        if not ins.get("has_time_series"):
            return []
        
        trends = []
        
        # Compare first vs last period
        time_data = self.extract_time_series(data)
        if len(time_data) >= 2:
            first = time_data[0]["value"]
            last = time_data[-1]["value"]
            change_pct = ((last - first) / first * 100) if first else 0
            
            if abs(change_pct) > 10:  # Significant change
                trends.append({
                    "type": "directional",
                    "metric": time_data[0].get("metric", "value"),
                    "direction": "up" if change_pct > 0 else "down",
                    "magnitude": abs(change_pct),
                    "from_period": time_data[0]["period"],
                    "to_period": time_data[-1]["period"],
                    "insight": (
                        f"{time_data[0].get('metric', 'Value')} "
                        f"{'grew' if change_pct > 0 else 'declined'} "
                        f"{abs(change_pct):.1f}% from {time_data[0]['period']} "
                        f"to {time_data[-1]['period']}"
                    ),
                })
        
        return trends
    
    def detect_outliers(self, data: dict, ins: dict) -> list[dict]:
        """Find unusual values that stand out."""
        rows = data.get("rows", [])
        if len(rows) < 5:
            return []
        
        # Extract numeric values
        values = []
        for row in rows:
            for cell in (row.values() if isinstance(row, dict) else row):
                if isinstance(cell, (int, float)):
                    values.append((cell, row))
                    break
        
        if not values:
            return []
        
        # Calculate mean and stddev
        nums = [v[0] for v in values]
        mean = sum(nums) / len(nums)
        stddev = (sum((x - mean) ** 2 for x in nums) / len(nums)) ** 0.5
        
        outliers = []
        for val, row in values:
            if stddev and abs(val - mean) > 2 * stddev:  # 2+ standard deviations
                outliers.append({
                    "value": val,
                    "row": row,
                    "deviation": (val - mean) / stddev,
                    "is_high": val > mean,
                    "insight": (
                        f"{self.label_row(row)}: AED {val:,.0f} is "
                        f"{(val - mean) / stddev:.1f}σ from the mean"
                    ),
                })
        
        return outliers[:3]  # Top 3 outliers
    
    def detect_concentration(self, data: dict, ins: dict) -> list[dict]:
        """Detect Pareto patterns (e.g., 80/20)."""
        rows = data.get("rows", [])
        if len(rows) < 5:
            return []
        
        # Get sorted values
        values = sorted([
            (self.label_row(row), self.numeric_value(row))
            for row in rows
            if self.numeric_value(row) is not None
        ], key=lambda x: x[1], reverse=True)
        
        if not values:
            return []
        
        total = sum(v[1] for v in values)
        if total == 0:
            return []
        
        # Find concentration point (top X = 80%)
        cumulative = 0
        for i, (label, val) in enumerate(values):
            cumulative += val
            pct = cumulative / total * 100
            if pct >= 80:
                top_n = i + 1
                top_pct = (top_n / len(values)) * 100
                return [{
                    "type": "concentration",
                    "top_count": top_n,
                    "total_count": len(values),
                    "top_share": pct,
                    "top_items": [v[0] for v in values[:top_n]],
                    "insight": (
                        f"Top {top_n} of {len(values)} items "
                        f"({top_pct:.0f}% of total) account for "
                        f"{pct:.0f}% of value"
                    ),
                }]
        
        return []
    
    def detect_variances(self, data: dict, ins: dict) -> list[dict]:
        """Compare against budget/forecast/prior period."""
        if not ins.get("has_comparison"):
            return []
        
        variances = []
        # Extract comparison metrics and calculate variance
        # (Simplified — actual logic depends on data structure)
        
        comparison = data.get("compare_with", {})
        for metric, current in data.get("metrics", {}).items():
            prior = comparison.get(metric)
            if prior is None or prior == 0:
                continue
            
            variance_pct = (current - prior) / abs(prior) * 100
            if abs(variance_pct) > 5:
                variances.append({
                    "metric": metric,
                    "current": current,
                    "prior": prior,
                    "variance_pct": variance_pct,
                    "direction": "favorable" if self.is_favorable(metric, variance_pct) else "unfavorable",
                    "insight": (
                        f"{metric} {self.direction_word(metric, variance_pct)} "
                        f"{abs(variance_pct):.1f}% vs prior period"
                    ),
                })
        
        return variances
    
    def check_business_thresholds(self, data: dict, ins: dict) -> list[dict]:
        """
        Apply UAE construction industry knowledge.
        Flag values that breach business norms.
        """
        flags = []
        
        # Gross margin check
        kpis = data.get("kpis", {})
        margin = kpis.get("margin_pct") or kpis.get("gross_margin")
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
                    "insight": "Margin below construction industry norm (10-20%)",
                })
            elif margin > 35:
                flags.append({
                    "severity": "info",
                    "metric": "margin",
                    "value": margin,
                    "insight": "Margin notably higher than industry average — verify",
                })
        
        # DSO check
        dso = kpis.get("days_sales_outstanding")
        if dso and dso > 90:
            flags.append({
                "severity": "warning",
                "metric": "dso",
                "value": dso,
                "insight": f"DSO {dso} days — collection cycle longer than ideal",
            })
        
        # Budget overrun
        if data.get("budget_variance_pct", 0) > 10:
            flags.append({
                "severity": "warning",
                "metric": "budget",
                "value": data.get("budget_variance_pct"),
                "insight": f"Over budget by {data['budget_variance_pct']:.0f}%",
            })
        
        return flags
    
    def label_row(self, row) -> str:
        """Get human label for a row."""
        if isinstance(row, dict):
            return row.get("name") or row.get("label") or row.get("account_name") or "Item"
        return str(row[0]) if row else "Item"
    
    def numeric_value(self, row):
        """Get primary numeric value from row."""
        if isinstance(row, dict):
            for key in ["value", "amount", "balance", "total"]:
                if key in row and isinstance(row[key], (int, float)):
                    return row[key]
            for val in row.values():
                if isinstance(val, (int, float)):
                    return val
        return None
```

## 6. UI: Progressive Insight Reveal

```
After perception, insights appear one by one:

┌────────────────────────────────────┐
│  ◊ Visualize                       │
├────────────────────────────────────┤
│                                    │
│  Analysis complete ✓               │
│                                    │
│  KEY FINDINGS                      │
│                                    │
│  ↗ Revenue grew 12% Q1 → Q4        │ ← Each insight
│                                    │   pops in
│  ⚠ Wages up 18% — outpacing       │   with brief
│    revenue growth                  │   appearance
│                                    │
│  ◉ Top 3 categories = 67% of       │
│    total expense                   │
│                                    │
│  ⚠ Project Zayidia 14% over       │
│    budget                          │
│                                    │
│  ───────────────────────────────   │
│                                    │
│  Continue to build report? [→]     │
│                                    │
└────────────────────────────────────┘

Icons used:
  ↗ ↘ → trend direction
  ⚠ → warning/concern
  ◉ → concentration/pareto
  ⊙ → outlier
  ✓ → positive finding
  ※ → informational

Color coding:
  Green: positive trends
  Amber: warnings
  Red: critical issues
  Cyan: informational

Animation:
  Each insight fades in over 200ms
  100ms gap between insights
  Creates "AI revealing thoughts" feel
```

---

# PART IV — STEP 3: OPINIONATE

## 7. The Recommendation Engine

```python
# visualize/opinionate.py

class FormatRecommender:
    """
    Forms opinions about what format/layout suits the data best.
    """
    
    def recommend(self, inspection: dict, analysis: dict) -> dict:
        """
        Returns a complete recommendation with reasoning.
        """
        # Decide primary format
        format_choice = self.choose_format(inspection, analysis)
        
        # Choose layout
        layout = self.choose_layout(inspection, analysis, format_choice)
        
        # Choose visualizations
        visualizations = self.choose_visualizations(inspection, analysis)
        
        # Choose theme
        theme = self.choose_theme(inspection)
        
        # Build sections list
        sections = self.build_sections(inspection, analysis, visualizations)
        
        return {
            "format": format_choice,
            "format_reasoning": self.format_reason(format_choice, inspection),
            "layout": layout,
            "layout_reasoning": self.layout_reason(layout, inspection),
            "theme": theme,
            "visualizations": visualizations,
            "sections": sections,
            "estimated_pages": self.estimate_pages(sections),
            "alternatives": self.suggest_alternatives(format_choice),
        }
    
    def choose_format(self, ins: dict, analysis: dict) -> str:
        """Pick PDF / Excel / PPT based on data and context."""
        row_count = ins.get("row_count", 0)
        has_lots_of_detail = row_count > 50
        has_calculations = ins.get("has_formulas", False)
        is_executive_summary = ins.get("is_summary_or_detailed") == "summary"
        
        # Excel best for: large datasets, formulas, analysis
        if has_lots_of_detail or has_calculations:
            return "excel"
        
        # PPT best for: executive presentations, board meetings
        if is_executive_summary and ins.get("audience") == "executive":
            return "ppt"
        
        # PDF best for: formal reports, sharing, archiving
        return "pdf"  # default
    
    def choose_layout(self, ins: dict, analysis: dict, fmt: str) -> str:
        """Pick specific layout within format."""
        row_count = ins.get("row_count", 0)
        has_findings = len(analysis.get("trends", [])) + len(analysis.get("variances", [])) > 2
        
        if fmt == "pdf":
            if row_count < 20 and has_findings:
                return "executive_summary"  # 1-2 pages, insight heavy
            if row_count > 100:
                return "detailed_analytical"  # 5-10 pages with appendix
            if ins.get("has_comparison"):
                return "comparative"  # side-by-side periods
            return "standard_report"  # balanced
        
        if fmt == "excel":
            if row_count > 200:
                return "pivot_ready"
            if ins.get("dimensions", []) and len(ins["dimensions"]) > 2:
                return "multi_sheet"
            return "single_sheet"
        
        if fmt == "ppt":
            return "boardroom"
        
        return "standard"
    
    def choose_visualizations(self, ins: dict, analysis: dict) -> list[dict]:
        """Pick which visualizations to include."""
        viz_list = []
        
        # Always include KPIs if available
        if ins.get("metrics"):
            viz_list.append({
                "type": "kpi_grid",
                "priority": 1,
                "reason": "Surface key metrics upfront",
            })
        
        # Time series → line chart
        if ins.get("has_time_series"):
            viz_list.append({
                "type": "line_chart",
                "priority": 2,
                "reason": "Show trend over time",
            })
        
        # Concentration finding → donut or treemap
        if analysis.get("concentrations"):
            viz_list.append({
                "type": "donut_chart",
                "priority": 2,
                "reason": "Visualize concentration pattern",
            })
        
        # Many categories → horizontal bar
        if ins.get("row_count", 0) >= 5 and ins.get("row_count", 0) <= 20:
            viz_list.append({
                "type": "horizontal_bar",
                "priority": 3,
                "reason": "Compare categories",
            })
        
        # Comparison → grouped bar
        if ins.get("has_comparison"):
            viz_list.append({
                "type": "grouped_bar",
                "priority": 2,
                "reason": "Side-by-side period comparison",
            })
        
        # Always include data table
        if ins.get("row_count", 0) > 0:
            viz_list.append({
                "type": "data_table",
                "priority": 4,
                "reason": "Detailed breakdown",
            })
        
        # Outliers → callout boxes
        if analysis.get("outliers"):
            viz_list.append({
                "type": "outlier_callout",
                "priority": 3,
                "reason": "Highlight unusual values",
            })
        
        return sorted(viz_list, key=lambda x: x["priority"])
    
    def choose_theme(self, ins: dict) -> str:
        """Pick theme based on audience and data type."""
        data_type = ins.get("primary_data_type", "")
        
        if "financial" in data_type:
            return "elegant_gold"  # Premium for financial
        if "project" in data_type:
            return "corporate_blue"  # Professional for ops
        
        return "elegant_gold"  # Default Elrace premium
    
    def build_sections(self, ins: dict, analysis: dict, vizs: list) -> list[dict]:
        """Build the full report structure."""
        sections = []
        
        # 1. Cover always first
        sections.append({
            "type": "cover",
            "order": 1,
            "config": {
                "title": ins.get("report_subject"),
                "period": ins.get("date_range"),
                "company": "Elrace Cos. & Gen. Cont. CO.",
            },
        })
        
        # 2. Executive summary (3-4 sentences of key findings)
        if analysis.get("trends") or analysis.get("variances"):
            sections.append({
                "type": "executive_summary",
                "order": 2,
                "config": {
                    "findings": self.top_findings(analysis, count=3),
                },
            })
        
        # 3. KPI dashboard
        if ins.get("metrics"):
            sections.append({
                "type": "kpi_dashboard",
                "order": 3,
                "config": {"metrics": ins["metrics"]},
            })
        
        # 4. Main chart (most important visualization)
        if vizs and vizs[0]["priority"] <= 2:
            sections.append({
                "type": "primary_chart",
                "order": 4,
                "config": vizs[0],
            })
        
        # 5. Insights section (concentration, outliers, etc.)
        sections.append({
            "type": "insights",
            "order": 5,
            "config": {
                "concentrations": analysis.get("concentrations"),
                "outliers": analysis.get("outliers"),
                "thresholds": analysis.get("thresholds"),
            },
        })
        
        # 6. Detail table
        sections.append({
            "type": "data_table",
            "order": 6,
            "config": {
                "show_top_n": 20 if ins.get("row_count", 0) > 50 else None,
            },
        })
        
        # 7. Recommendations / So-What section
        if analysis.get("thresholds") or analysis.get("variances"):
            sections.append({
                "type": "recommendations",
                "order": 7,
                "config": {
                    "items": self.generate_recommendations(analysis),
                },
            })
        
        return sections
    
    def format_reason(self, fmt: str, ins: dict) -> str:
        """Explain why this format was recommended."""
        reasons = {
            "pdf": (
                "PDF is best for sharing this kind of report formally — "
                "preserves formatting and is print-ready."
            ),
            "excel": (
                f"Excel suits your {ins.get('row_count')} records — "
                "easy to filter, sort, and analyze further."
            ),
            "ppt": (
                "PowerPoint format fits an executive summary — "
                "ready for board presentation."
            ),
        }
        return reasons.get(fmt, "")
```

## 8. UI: The Recommendation Card

```
After analysis, agent shows the recommendation as a complete card:

┌────────────────────────────────────┐
│  ◊ Visualize                       │
├────────────────────────────────────┤
│                                    │
│  ✦ MY RECOMMENDATION               │
│                                    │
│  Format:        PDF Report         │
│  Layout:        Executive Summary  │
│  Theme:         Elegant Gold       │
│  Est. pages:    4 pages            │
│  Language:      English            │
│                                    │
│  This report will include:         │
│                                    │
│  ✓ Cover page with company logo    │
│  ✓ Executive summary (3 findings)  │
│  ✓ KPI dashboard (4 metrics)       │
│  ✓ Monthly revenue trend chart     │
│  ✓ Expense category breakdown      │
│  ✓ Top 10 detail table             │
│  ✓ Insight callouts                │
│  ✓ Recommendations section         │
│                                    │
│  Why this approach:                │
│  Your data has clear trends and    │
│  3 critical findings. Executive    │
│  Summary highlights what matters   │
│  most without overwhelming detail. │
│                                    │
│  ───────────────────────────────   │
│                                    │
│  [Build This Report →]             │
│  [Customize First] [Different]     │
│                                    │
└────────────────────────────────────┘

Three primary buttons:
  1. Build This Report → start generating
  2. Customize First → tweak sections/theme
  3. Different → present alternatives

User can also type freely:
  "Make it Arabic"
  "Add a pie chart"
  "Remove the recommendations section"
  "Use dark theme instead"
```

## 9. Alternative Suggestions

```
When user clicks "Different" or asks for alternatives:

┌────────────────────────────────────┐
│  ◊ Visualize                       │
├────────────────────────────────────┤
│                                    │
│  OTHER OPTIONS                     │
│                                    │
│  ┌──────────────────────────────┐  │
│  │ 📊 Detailed Excel             │  │
│  │ All 247 records with pivot    │  │
│  │ tables and charts. Best for   │  │
│  │ further analysis.             │  │
│  │                               │  │
│  │ [Choose This]                 │  │
│  └──────────────────────────────┘  │
│                                    │
│  ┌──────────────────────────────┐  │
│  │ 📈 Board Presentation         │  │
│  │ 8-slide PowerPoint deck       │  │
│  │ ready for executive meeting.  │  │
│  │                               │  │
│  │ [Choose This]                 │  │
│  └──────────────────────────────┘  │
│                                    │
│  ┌──────────────────────────────┐  │
│  │ 📋 Comparative Report         │  │
│  │ Side-by-side periods with    │  │
│  │ variance analysis.           │  │
│  │                               │  │
│  │ [Choose This]                 │  │
│  └──────────────────────────────┘  │
│                                    │
│  [← Back to Recommendation]        │
│                                    │
└────────────────────────────────────┘
```

---

# PART V — STEP 4: PROPOSE WITH PREVIEW

## 10. Visual Preview Cards

```
When user clicks "Build This Report", show structure preview:

┌────────────────────────────────────────┐
│  ◊ Visualize                           │
├────────────────────────────────────────┤
│                                        │
│  BUILDING YOUR REPORT                  │
│                                        │
│  Structure preview:                    │
│                                        │
│  ┌──────────┐                          │
│  │ [Cover]  │ ← page 1                 │
│  └──────────┘                          │
│                                        │
│  ┌──────────┐                          │
│  │ [Exec    │ ← page 2                 │
│  │  Summary]│                          │
│  └──────────┘                          │
│                                        │
│  ┌──────────┐                          │
│  │ [KPIs +  │ ← page 3                 │
│  │  Chart]  │                          │
│  └──────────┘                          │
│                                        │
│  ┌──────────┐                          │
│  │ [Detail  │ ← page 4                 │
│  │  Table]  │                          │
│  └──────────┘                          │
│                                        │
│  ✓ Generate                            │
│  Generating page 2 of 4...             │
│  ▓▓▓▓░░░░░░ 50%                       │
│                                        │
└────────────────────────────────────────┘

As each page renders, its thumbnail materializes.
Replaces the placeholder block.
User sees progress visibly.
```

---

# PART VI — THE VISUALIZE AGENT PROMPT (UPDATED)

## 11. The Smart Agent System Prompt

```python
VISUALIZE_AGENT_PROMPT_V2 = """
You are "Visualize" — a specialized AI agent that transforms data 
into beautiful, professional reports. You are an experienced 
business analyst who happens to also be a great designer.

═══════════════════════════════════════════════════════════
YOUR FOUR-STEP PROCESS (always follow):
═══════════════════════════════════════════════════════════

STEP 1: PERCEIVE
  - Use the inspect_data tool to understand what was dropped
  - Note structure, size, type, time range, dimensions
  - Be specific in your acknowledgment

STEP 2: UNDERSTAND  
  - Use the analyze_patterns tool to find trends, outliers, 
    concentrations, variances, threshold breaches
  - Identify the "story" in the data — what's interesting?
  - Apply UAE construction industry knowledge

STEP 3: OPINIONATE
  - Use the recommend_format tool to propose the best approach
  - Form a clear, confident recommendation
  - Be opinionated — say WHY this approach suits the data
  
STEP 4: PROPOSE
  - Show a complete plan with sections, theme, layout
  - Offer 2-3 alternatives
  - Accept refinements via natural conversation
  - Then build using generate_pdf / generate_excel / generate_ppt

═══════════════════════════════════════════════════════════
RESPONSE STRUCTURE:
═══════════════════════════════════════════════════════════

When data is dropped, respond in this exact format:

1. SHORT acknowledgment of what you see
2. List of 3-5 KEY FINDINGS (use icons)
3. YOUR RECOMMENDATION with reasoning
4. Sections to include
5. Action buttons

Use visualize-card tags to format:

<visualize-card>
{
  "type": "inspection",
  "items_dropped": 1,
  "data_type": "P&L Statement",
  "period": "Jan – Apr 2026",
  "record_count": 247,
  "dimensions": ["account", "month"]
}
</visualize-card>

<visualize-card>
{
  "type": "insights",
  "findings": [
    {"icon": "trend_up", "text": "Revenue grew 12% Q1 → Q4", "color": "green"},
    {"icon": "warning", "text": "Wages up 18% — outpacing revenue", "color": "amber"},
    {"icon": "concentration", "text": "Top 3 categories = 67% of expenses", "color": "blue"}
  ]
}
</visualize-card>

<visualize-card>
{
  "type": "recommendation",
  "format": "pdf",
  "layout": "executive_summary",
  "theme": "elegant_gold",
  "estimated_pages": 4,
  "language": "en",
  "sections": [
    "Cover page with company logo",
    "Executive summary (3 findings)",
    "KPI dashboard (4 metrics)",
    "Monthly revenue trend chart",
    "Expense category breakdown",
    "Top 10 detail table",
    "Insight callouts",
    "Recommendations section"
  ],
  "reasoning": "Your data has clear trends and 3 critical findings. Executive Summary highlights what matters most without overwhelming detail.",
  "alternatives": [
    {"label": "Detailed Excel", "description": "All 247 records with pivot tables"},
    {"label": "Board Presentation", "description": "8-slide PowerPoint deck"},
    {"label": "Comparative Report", "description": "Side-by-side periods with variance"}
  ]
}
</visualize-card>

═══════════════════════════════════════════════════════════
TONE GUIDELINES:
═══════════════════════════════════════════════════════════

- Confident but not arrogant
- "I recommend..." not "Maybe you could..."
- "I see..." not "It looks like..."
- "This data shows..." not "I think this data..."
- Use design vocabulary correctly
- Acknowledge user expertise — they know their business
- Excited about creating beautiful outputs
- Brief when summarizing, detailed when explaining choices

═══════════════════════════════════════════════════════════
WHAT YOU DON'T DO:
═══════════════════════════════════════════════════════════

- Don't re-fetch data (main agent's job)
- Don't run new financial analyses
- Don't answer business questions about the data
- Don't refuse to build something just because data is incomplete
- Don't show raw JSON in responses
- Don't ask too many questions — propose, then refine

═══════════════════════════════════════════════════════════
REFINEMENT HANDLING:
═══════════════════════════════════════════════════════════

User says: "Make it Arabic"
  → Update spec, regenerate, show new preview

User says: "Use dark theme"
  → Switch theme, keep everything else

User says: "Remove the recommendations section"
  → Update sections list, regenerate

User says: "Add a pie chart for expenses"
  → Insert pie chart, regenerate

User says: "Make it shorter"
  → Switch to executive_summary layout

User says: "Make it longer"
  → Switch to detailed_analytical layout

Always confirm: "Updated. Regenerating with [change]..."
"""
```

---

# PART VII — BACKEND TOOLS (NEW)

## 12. Tools for Visualize Agent

```python
VISUALIZE_TOOLS_V2 = [
    {
        "name": "inspect_data",
        "description": (
            "Inspect dropped data structure. Returns metadata about "
            "data type, size, dimensions, date range, etc."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "dropped_items": {"type": "array"},
            },
        },
    },
    {
        "name": "analyze_patterns",
        "description": (
            "Detect trends, outliers, concentrations, variances, and "
            "threshold breaches in the data."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "data": {"type": "object"},
                "inspection": {"type": "object"},
            },
        },
    },
    {
        "name": "recommend_format",
        "description": (
            "Form opinion about best format/layout/theme based on "
            "inspection and analysis."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "inspection": {"type": "object"},
                "analysis": {"type": "object"},
            },
        },
    },
    # (PDF/Excel/PPT generators come in later layers)
]
```

## 13. API Endpoints

```
POST /visualize/inspect
  Input: dropped_items
  Returns: inspection result
  Used by frontend to show real-time inspection feedback

POST /visualize/analyze
  Input: inspection + data
  Returns: patterns and insights

POST /visualize/recommend
  Input: inspection + analysis
  Returns: complete recommendation

POST /visualize/chat/stream
  Updated to include the four-step flow
  Streams card-by-card responses
```

---

# PART VIII — COMPLETE UI FLOW

## 14. The Full User Experience

```
SECOND 0:
  User drops P&L data onto Visualize panel
  Panel slides open (already implemented)
  
SECOND 0.2:
  Card appears: "Analyzing your data..."
  
SECOND 0.5:
  First line: "● Detected: P&L Statement"
  
SECOND 0.7:
  Second line: "● Range: Jan – Apr 2026 (4 months)"
  
SECOND 0.9:
  Third line: "● Records: 247 transactions"
  
SECOND 1.1:
  Fourth line: "● 8 expense categories"
  
SECOND 1.3:
  Fifth line: "● Includes negative values"
  
SECOND 1.5:
  Progress bar: "▓▓▓▓▓▓▓░░░ Analyzing patterns..."
  
SECOND 2.5:
  "Analysis complete ✓"
  
SECOND 2.7:
  Insight 1 fades in: "↗ Revenue grew 12% Q1 → Q4"
  
SECOND 2.9:
  Insight 2: "⚠ Wages up 18% — outpacing revenue"
  
SECOND 3.1:
  Insight 3: "◉ Top 3 categories = 67% of total"
  
SECOND 3.3:
  Insight 4: "⚠ Project Zayidia 14% over budget"
  
SECOND 3.5:
  Recommendation card materializes
  Shows format, layout, theme, sections
  Action buttons appear
  
SECOND 3.5+:
  Waiting for user input
```

## 15. UI Components Needed

```
ooa-ui/src/visualize/cards/
├── InspectionCard.jsx        # Real-time data inspection display
├── InsightsCard.jsx          # Finding bullets with icons
├── RecommendationCard.jsx    # Complete format proposal
├── AlternativesCard.jsx      # Other format options
├── StructurePreviewCard.jsx  # Page-by-page preview
└── icons/
    ├── TrendIcon.jsx          # ↗ ↘ →
    ├── WarningIcon.jsx        # ⚠
    ├── ConcentrationIcon.jsx  # ◉
    └── OutlierIcon.jsx        # ⊙
```

## 16. Component Behaviors

```jsx
// InspectionCard.jsx — progressive line-by-line reveal

function InspectionCard({ inspection }) {
  const [visibleLines, setVisibleLines] = useState(0);
  
  useEffect(() => {
    const lines = buildInspectionLines(inspection);
    const interval = setInterval(() => {
      setVisibleLines(prev => {
        if (prev >= lines.length) {
          clearInterval(interval);
          return prev;
        }
        return prev + 1;
      });
    }, 150);
    return () => clearInterval(interval);
  }, [inspection]);
  
  return (
    <div className="inspection-card">
      <div className="card-title">Analyzing your data...</div>
      <div className="lines">
        {buildInspectionLines(inspection)
          .slice(0, visibleLines)
          .map((line, i) => (
            <div key={i} className="inspection-line fade-in">
              <span className="bullet">●</span>
              <span className="text">{line}</span>
            </div>
          ))}
      </div>
      {visibleLines >= 5 && (
        <ProgressBar duration={1000} label="Analyzing patterns..." />
      )}
    </div>
  );
}


// InsightsCard.jsx — each insight appears with stagger

function InsightsCard({ findings }) {
  const [revealed, setRevealed] = useState(0);
  
  useEffect(() => {
    const interval = setInterval(() => {
      setRevealed(prev => {
        if (prev >= findings.length) {
          clearInterval(interval);
          return prev;
        }
        return prev + 1;
      });
    }, 200);
    return () => clearInterval(interval);
  }, [findings]);
  
  return (
    <div className="insights-card">
      <div className="card-title">✦ KEY FINDINGS</div>
      <div className="findings">
        {findings.slice(0, revealed).map((f, i) => (
          <div key={i} className={`finding fade-in finding-${f.color}`}>
            <Icon name={f.icon} />
            <span className="finding-text">{f.text}</span>
          </div>
        ))}
      </div>
    </div>
  );
}


// RecommendationCard.jsx — full recommendation

function RecommendationCard({ recommendation, onAction }) {
  return (
    <div className="recommendation-card">
      <div className="card-title">✦ MY RECOMMENDATION</div>
      
      <div className="rec-grid">
        <div className="rec-row">
          <span className="rec-label">Format:</span>
          <span className="rec-value">{recommendation.format.toUpperCase()}</span>
        </div>
        <div className="rec-row">
          <span className="rec-label">Layout:</span>
          <span className="rec-value">{recommendation.layout_display}</span>
        </div>
        <div className="rec-row">
          <span className="rec-label">Theme:</span>
          <span className="rec-value">{recommendation.theme_display}</span>
        </div>
        <div className="rec-row">
          <span className="rec-label">Est. pages:</span>
          <span className="rec-value">{recommendation.estimated_pages}</span>
        </div>
      </div>
      
      <div className="sections-list">
        <div className="sections-title">This report will include:</div>
        {recommendation.sections.map((section, i) => (
          <div key={i} className="section-item">
            <span className="check">✓</span>
            <span>{section}</span>
          </div>
        ))}
      </div>
      
      <div className="reasoning">
        <div className="reasoning-title">Why this approach:</div>
        <p>{recommendation.reasoning}</p>
      </div>
      
      <div className="actions">
        <button 
          className="btn-primary"
          onClick={() => onAction('build')}
        >
          Build This Report →
        </button>
        <button 
          className="btn-secondary"
          onClick={() => onAction('customize')}
        >
          Customize First
        </button>
        <button 
          className="btn-tertiary"
          onClick={() => onAction('alternatives')}
        >
          Different
        </button>
      </div>
    </div>
  );
}
```

## 17. CSS / Styling

```css
/* Cards inside Visualize panel */

.inspection-card,
.insights-card,
.recommendation-card {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 16px;
  padding: 20px;
  margin-bottom: 12px;
}

.card-title {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  color: rgba(255, 255, 255, 0.5);
  margin-bottom: 12px;
}

/* Inspection lines */

.inspection-line {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.8);
  padding: 6px 0;
  opacity: 0;
}

.inspection-line.fade-in {
  animation: fadeInUp 0.2s ease forwards;
}

.bullet {
  color: #c9a84c;
  font-size: 16px;
  line-height: 1;
}

/* Findings (insights) */

.finding {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.03);
  margin-bottom: 8px;
  font-size: 13px;
}

.finding-green {
  border-left: 3px solid #10b981;
}

.finding-amber {
  border-left: 3px solid #f59e0b;
}

.finding-red {
  border-left: 3px solid #ef4444;
}

.finding-blue {
  border-left: 3px solid #4ecdc4;
}

/* Recommendation */

.rec-grid {
  margin-bottom: 16px;
  padding: 12px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.rec-row {
  display: flex;
  justify-content: space-between;
  padding: 4px 0;
  font-size: 13px;
}

.rec-label {
  color: rgba(255, 255, 255, 0.5);
}

.rec-value {
  color: rgba(255, 255, 255, 0.9);
  font-weight: 500;
}

.sections-list {
  margin: 16px 0;
}

.section-item {
  display: flex;
  gap: 8px;
  padding: 4px 0;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.7);
}

.check {
  color: #c9a84c;
}

.reasoning {
  background: rgba(201, 168, 76, 0.08);
  border-left: 3px solid #c9a84c;
  padding: 12px;
  border-radius: 8px;
  margin: 16px 0;
  font-size: 13px;
  font-style: italic;
  color: rgba(255, 255, 255, 0.8);
}

.actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 16px;
}

.btn-primary {
  background: linear-gradient(135deg, #c9a84c, #a8873d);
  color: #1a2744;
  padding: 12px;
  border-radius: 10px;
  border: none;
  font-weight: 600;
  cursor: pointer;
}

.btn-secondary,
.btn-tertiary {
  background: rgba(255, 255, 255, 0.06);
  color: rgba(255, 255, 255, 0.8);
  padding: 10px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  cursor: pointer;
}

/* Animations */

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
```

---

# PART IX — IMPLEMENTATION PHASES

## 18. Build Order (Layer 1 only — 4 weeks)

### Phase 1.1 — Data Inspection (Week 1)
```
[ ] Build DataInspector class
[ ] Implement all inspection methods
[ ] Add /visualize/inspect endpoint
[ ] Build InspectionCard React component
[ ] Test with 10 different data types
[ ] Verify progressive line reveal animation
```

### Phase 1.2 — Pattern Analysis (Week 2)
```
[ ] Build PatternAnalyzer class
[ ] Trend detection logic
[ ] Outlier detection (statistical)
[ ] Concentration detection (Pareto)
[ ] Variance detection
[ ] Business threshold checks (UAE construction)
[ ] Add /visualize/analyze endpoint
[ ] Build InsightsCard React component
[ ] Test with real Elrace data
```

### Phase 1.3 — Recommendation Engine (Week 3)
```
[ ] Build FormatRecommender class
[ ] Format choice logic
[ ] Layout choice logic
[ ] Visualization selection
[ ] Theme matching
[ ] Section building
[ ] Alternative generation
[ ] Add /visualize/recommend endpoint
[ ] Build RecommendationCard component
[ ] Build AlternativesCard component
```

### Phase 1.4 — Integration & Polish (Week 4)
```
[ ] Update Visualize agent system prompt
[ ] Wire all four steps end-to-end
[ ] Test complete flow on 20 different datasets
[ ] Performance: keep total analysis <3s
[ ] Refine UI animations
[ ] Add error handling
[ ] Document for team
```

---

# PART X — TESTING CHECKLIST

## 19. What "Layer 1 Done" Looks Like

```
DATA INSPECTION:
  ✓ Correctly identifies 10+ data types
  ✓ Extracts date range, record count, dimensions
  ✓ Detects negatives, comparisons, time series
  ✓ UI shows progressive line reveal
  ✓ Completes in <1.5 seconds

PATTERN ANALYSIS:
  ✓ Detects trends (10%+ changes)
  ✓ Finds outliers (2σ deviation)
  ✓ Identifies concentration patterns (Pareto)
  ✓ Calculates variances vs comparisons
  ✓ Flags business threshold breaches
  ✓ Returns 3-5 meaningful insights per dataset

RECOMMENDATION:
  ✓ Picks appropriate format (PDF/Excel/PPT)
  ✓ Chooses fitting layout
  ✓ Matches theme to data type
  ✓ Selects right visualizations
  ✓ Builds logical section order
  ✓ Provides 2-3 alternatives
  ✓ Explains reasoning clearly

UI EXPERIENCE:
  ✓ Smooth progressive reveal
  ✓ Insights pop in with stagger
  ✓ Recommendation card looks complete
  ✓ Action buttons clear and prominent
  ✓ Alternatives easily accessible
  ✓ User can refine with natural language
  ✓ Animations subtle, not distracting

INTELLIGENCE FEEL:
  ✓ User says "wow, it actually thinks"
  ✓ Recommendation feels considered, not random
  ✓ Insights are useful, not generic
  ✓ Reasoning makes sense
  ✓ Output feels like a senior analyst
```

---

# PART XI — TELL CURSOR

```
"Read VISUALIZE_LAYER_1_PLAN.md.

This is the analysis brain for the Visualize agent.
We are building this in 4 weeks across 4 phases.

Start Phase 1.1: Data Inspection.

1. Create visualize/perceive.py with DataInspector class
2. Implement all inspection methods from PART II
3. Add /visualize/inspect endpoint
4. Build InspectionCard.jsx with progressive line reveal
5. Test with at least 10 different data types

After Phase 1.1 confirmed working, move to Phase 1.2.

Reference:
- VISUALIZE_AGENT_PLAN.md for overall architecture
- PRODUCT_QUALITY_FRAMEWORK.md for output standards
- MAIN_SCREENS_LAYOUT_PLAN.md for Visualize panel design

Critical:
- This is the BRAIN of the agent
- Quality > Speed
- Real analysis, not mock responses
- UI should feel intelligent
- Each phase must be production-quality before moving on"
```

---

# PART XII — WHAT LAYER 2, 3, 4 WILL ADD

```
LAYER 2 — RICH TEMPLATES (after Layer 1)
  - Full PDF template library (6 layouts)
  - Excel template library (5 structures)
  - PPT template library (4 deck styles)
  - Theme system implementation
  - Generator backends

LAYER 3 — REPORT CONTENT LIBRARY (after Layer 2)
  - 15+ chart patterns
  - Multiple table patterns
  - Insight patterns
  - Layout compositions
  - Component library

LAYER 4 — CUSTOMIZATION ENGINE (after Layer 3)
  - Theme picker UI
  - Color customizer
  - Logo upload
  - Section toggles
  - Column selection
  - Chart type override
```

After all 4 layers, you will have a Visualize agent that thinks, analyzes, recommends, and produces world-class reports. Layer 1 is the foundation — without the brain, everything else is just templates.
