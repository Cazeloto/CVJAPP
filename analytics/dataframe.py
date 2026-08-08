"""Pandas transformation helpers."""

from __future__ import annotations

from typing import Any

from analytics.utils import require_dependency


def _pd() -> Any:
    require_dependency("pandas", "pandas")
    import pandas as pd

    return pd


def normalize_columns(df: Any) -> Any:
    """Return a copy of a DataFrame with normalized lowercase column names."""

    result = df.copy()
    result.columns = [
        str(col).strip().lower().replace(" ", "_").replace("-", "_") for col in result.columns
    ]
    return result


def convert_date_column(df: Any, column: str) -> Any:
    """Return a copy with a column converted to Pandas datetime."""

    pd = _pd()
    result = df.copy()
    result[column] = pd.to_datetime(result[column], errors="coerce")
    return result


def filter_date_range(df: Any, column: str, start: Any = None, end: Any = None) -> Any:
    """Filter a DataFrame by an inclusive date range."""

    result = convert_date_column(df, column)
    mask = result[column].notna()
    if start is not None:
        mask &= result[column] >= start
    if end is not None:
        mask &= result[column] <= end
    return result.loc[mask].copy()


def group_count(df: Any, by: str | list[str], count_name: str = "total") -> Any:
    """Group a DataFrame and count rows."""

    return df.groupby(by, dropna=False).size().reset_index(name=count_name)


def group_sum(df: Any, by: str | list[str], value: str, result_name: str = "total") -> Any:
    """Group a DataFrame and sum a numeric column."""

    return df.groupby(by, dropna=False)[value].sum().reset_index(name=result_name)


def optimize_types(df: Any) -> Any:
    """Return a copy with memory-friendly numeric and object types when possible."""

    pd = _pd()
    result = df.copy()
    for column in result.select_dtypes(include=["int"]).columns:
        result[column] = pd.to_numeric(result[column], downcast="integer")
    for column in result.select_dtypes(include=["float"]).columns:
        result[column] = pd.to_numeric(result[column], downcast="float")
    for column in result.select_dtypes(include=["object"]).columns:
        unique_ratio = result[column].nunique(dropna=False) / max(len(result), 1)
        if unique_ratio < 0.5:
            result[column] = result[column].astype("category")
    return result
