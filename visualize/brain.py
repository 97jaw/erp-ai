"""Layer 1 analysis brain — orchestrates perceive → understand → opinionate."""

from __future__ import annotations

from typing import Any

from visualize.opinionate import FormatRecommender
from visualize.perceive import DataInspector
from visualize.understand import PatternAnalyzer


def _primary_viz_data(items: list[dict]) -> dict[str, Any]:
    for item in items:
        viz = item.get("visualization")
        if isinstance(viz, dict) and viz.get("data"):
            data = viz["data"]
            if isinstance(data, dict):
                return data
    for item in items:
        viz = item.get("visualization")
        if isinstance(viz, dict):
            return viz.get("data") if isinstance(viz.get("data"), dict) else {}
    return {}


def run_inspection(dropped_items: list[dict]) -> dict[str, Any]:
    return DataInspector().inspect(dropped_items)


def run_pattern_analysis(
    dropped_items: list[dict],
    inspection: dict[str, Any] | None = None,
) -> dict[str, Any]:
    inspection = inspection or run_inspection(dropped_items)
    data = _primary_viz_data(dropped_items)
    analyzer = PatternAnalyzer()
    analysis = analyzer.analyze(data, inspection)
    analysis["findings"] = analyzer.build_findings(analysis)
    return analysis


def run_recommendation(
    inspection: dict[str, Any],
    analysis: dict[str, Any],
) -> dict[str, Any]:
    return FormatRecommender().recommend(inspection, analysis)


def run_full_brain(dropped_items: list[dict]) -> dict[str, Any]:
    """Run complete Layer 1 pipeline."""
    inspection = run_inspection(dropped_items)
    analysis = run_pattern_analysis(dropped_items, inspection)
    recommendation = run_recommendation(inspection, analysis)
    return {
        "inspection": inspection,
        "analysis": analysis,
        "recommendation": recommendation,
    }
