"""Generic KPI and analytical indicator functions."""

from __future__ import annotations

from typing import Any

from analytics.exceptions import InvalidIndicatorError
from analytics.models import KPIResult
from analytics.utils import require_dependency


def _pd() -> Any:
    require_dependency("pandas", "pandas")
    import pandas as pd

    return pd


def total_records(df: Any, name: str = "total_registros") -> KPIResult:
    """Return total number of records in a DataFrame."""

    return KPIResult(name=name, label="Total de registros", value=int(len(df)))


def count_where(df: Any, column: str, value: Any, name: str | None = None) -> KPIResult:
    """Count records where a column is equal to a value."""

    _ensure_column(df, column)
    total = int((df[column] == value).sum())
    return KPIResult(
        name=name or f"{column}_{value}",
        label=f"{column} = {value}",
        value=total,
        metadata={"column": column, "value": value},
    )


def active_records(df: Any, status_column: str = "status", active_value: Any = "A") -> KPIResult:
    """Count active records using a configurable status column."""

    return count_where(df, status_column, active_value, "registros_ativos")


def finalized_records(
    df: Any,
    status_column: str = "status",
    finalized_value: Any = "F",
) -> KPIResult:
    """Count finalized records using a configurable status column."""

    return count_where(df, status_column, finalized_value, "registros_finalizados")


def new_records(df: Any, date_column: str, start: Any, end: Any = None) -> KPIResult:
    """Count records created within an inclusive date range."""

    pd = _pd()
    _ensure_column(df, date_column)
    dates = pd.to_datetime(df[date_column], errors="coerce")
    mask = dates >= pd.to_datetime(start)
    if end is not None:
        mask &= dates <= pd.to_datetime(end)
    return KPIResult(
        name="novos_registros",
        label="Novos registros",
        value=int(mask.sum()),
        metadata={"date_column": date_column, "start": str(start), "end": str(end)},
    )


def percentage(part: int | float, total: int | float, name: str = "percentual") -> KPIResult:
    """Calculate a percentage from part and total."""

    value = 0.0 if total == 0 else (float(part) / float(total)) * 100.0
    return KPIResult(name=name, label="Percentual", value=value, unit="%")


def temporal_evolution(df: Any, date_column: str, freq: str = "D") -> Any:
    """Return counts grouped by a temporal frequency."""

    pd = _pd()
    _ensure_column(df, date_column)
    result = df.copy()
    result[date_column] = pd.to_datetime(result[date_column], errors="coerce")
    result = result.dropna(subset=[date_column])
    return result.set_index(date_column).resample(freq).size().reset_index(name="total")


def ranking(df: Any, group_by: str, metric: str | None = None, ascending: bool = False) -> Any:
    """Return a grouped ranking by count or by a metric sum."""

    _ensure_column(df, group_by)
    if metric is None:
        result = df.groupby(group_by, dropna=False).size().reset_index(name="total")
    else:
        _ensure_column(df, metric)
        result = df.groupby(group_by, dropna=False)[metric].sum().reset_index(name="total")
    return result.sort_values("total", ascending=ascending).reset_index(drop=True)


def top_n(df: Any, group_by: str, n: int = 10, metric: str | None = None) -> Any:
    """Return the top N groups."""

    return ranking(df, group_by=group_by, metric=metric, ascending=False).head(n)


def bottom_n(df: Any, group_by: str, n: int = 10, metric: str | None = None) -> Any:
    """Return the bottom N groups."""

    return ranking(df, group_by=group_by, metric=metric, ascending=True).head(n)


def average(df: Any, column: str) -> KPIResult:
    """Return the average value of a numeric column."""

    _ensure_column(df, column)
    return KPIResult(name=f"media_{column}", label=f"Média de {column}", value=float(df[column].mean()))


def average_time(df: Any, start_column: str, end_column: str, unit: str = "minutes") -> KPIResult:
    """Calculate average elapsed time between two datetime columns."""

    pd = _pd()
    _ensure_column(df, start_column)
    _ensure_column(df, end_column)
    start = pd.to_datetime(df[start_column], errors="coerce")
    end = pd.to_datetime(df[end_column], errors="coerce")
    seconds = (end - start).dt.total_seconds().dropna()
    factor = {"seconds": 1, "minutes": 60, "hours": 3600, "days": 86400}.get(unit)
    if factor is None:
        raise InvalidIndicatorError(f"Unidade inválida: {unit}")
    value = 0.0 if seconds.empty else float(seconds.mean() / factor)
    return KPIResult(name="tempo_medio", label="Tempo médio", value=value, unit=unit)


def compare_values(current: int | float, previous: int | float, name: str = "comparativo") -> KPIResult:
    """Compare current and previous values as percentage variation."""

    variation = 0.0 if previous == 0 else ((float(current) - float(previous)) / float(previous)) * 100
    return KPIResult(
        name=name,
        label="Comparativo",
        value=variation,
        unit="%",
        metadata={"current": current, "previous": previous},
    )


def _ensure_column(df: Any, column: str) -> None:
    if column not in df.columns:
        raise InvalidIndicatorError(f"Coluna não encontrada: {column}")
