"""
Chart Generator
===============
File    : integrations/chart_generator.py
Status  : STUB — Phase 4

Wraps KPIResponse data into the Standard Visualization JSON contract
defined in Phase 3. The frontend (Flutter/Web) renders from this schema.

Visualization types:
    KPI_CARD    → value, delta, color_code
    BAR_CHART   → labels[], datasets[], axis_title
    LINE_CHART  → time_unit, points[], regression_line
    DATA_TABLE  → columns[], rows[], sort_by
    PIVOT_TABLE → row_dimension, col_dimension, value_field, aggregation
"""

from core.state import VisualType


class ChartGenerator:

    def build(self, visual_type: VisualType, data: dict) -> dict:
        """Returns a Standard Visualization JSON payload."""
        builders = {
            VisualType.KPI_CARD   : self._kpi_card,
            VisualType.BAR_CHART  : self._bar_chart,
            VisualType.LINE_CHART : self._line_chart,
            VisualType.DATA_TABLE : self._data_table,
            VisualType.PIVOT_TABLE: self._pivot_table,
        }
        builder = builders.get(visual_type)
        if not builder:
            raise ValueError(f"Unknown visual type: {visual_type}")
        return builder(data)

    def _kpi_card(self, data: dict) -> dict:
        raise NotImplementedError("Phase 4.")

    def _bar_chart(self, data: dict) -> dict:
        raise NotImplementedError("Phase 4.")

    def _line_chart(self, data: dict) -> dict:
        raise NotImplementedError("Phase 4.")

    def _data_table(self, data: dict) -> dict:
        raise NotImplementedError("Phase 4.")

    def _pivot_table(self, data: dict) -> dict:
        raise NotImplementedError("Phase 4.")
