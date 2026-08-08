"""Dashboard composition primitives independent from UI frameworks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from analytics.models import ChartResult, KPIResult


@dataclass(frozen=True)
class DashboardSection:
    """A logical dashboard section containing KPIs and charts."""

    title: str
    kpis: list[KPIResult] = field(default_factory=list)
    charts: list[ChartResult] = field(default_factory=list)
    tables: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DashboardDefinition:
    """A UI-agnostic dashboard definition."""

    title: str
    sections: list[DashboardSection] = field(default_factory=list)

    def all_kpis(self) -> list[KPIResult]:
        """Return all KPIs from all sections in display order."""

        return [kpi for section in self.sections for kpi in section.kpis]

    def all_charts(self) -> list[ChartResult]:
        """Return all charts from all sections in display order."""

        return [chart for section in self.sections for chart in section.charts]
