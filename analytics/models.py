"""Dataclasses shared by analytics modules."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DateRange:
    """Inclusive date range used by indicators and queries."""

    start: date | datetime | None = None
    end: date | datetime | None = None


@dataclass(frozen=True)
class SQLQuery:
    """Named SQL query with optional parameters."""

    name: str
    sql: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class QueryResult:
    """Metadata returned with query execution results."""

    name: str
    row_count: int
    columns: tuple[str, ...] = ()
    elapsed_seconds: float = 0.0


@dataclass(frozen=True)
class KPIResult:
    """Generic KPI value."""

    name: str
    value: int | float | str
    label: str | None = None
    unit: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ChartResult:
    """Chart generation result."""

    name: str
    figure: Any
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExportResult:
    """Export generation result."""

    path: Path
    format: str
    metadata: dict[str, Any] = field(default_factory=dict)
