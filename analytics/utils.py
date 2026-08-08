"""Small generic helpers used across the analytics framework."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

from analytics.exceptions import DependencyMissingError


def require_dependency(module_name: str, package_hint: str | None = None) -> None:
    """Raise a clear error when an optional dependency is not installed."""

    if importlib.util.find_spec(module_name) is None:
        package = package_hint or module_name
        raise DependencyMissingError(
            f"Dependência opcional ausente: instale '{package}' para usar este recurso."
        )


def stable_hash(value: Any) -> str:
    """Return a stable SHA-256 hash for JSON-serializable values."""

    payload = json.dumps(value, sort_keys=True, default=str, ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def safe_filename(value: str, fallback: str = "arquivo") -> str:
    """Return a filesystem-friendly filename stem."""

    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", (value or "").strip()).strip("._")
    return cleaned or fallback


def ensure_directory(path: str | Path) -> Path:
    """Create a directory if needed and return it as a Path."""

    target = Path(path)
    target.mkdir(parents=True, exist_ok=True)
    return target


def format_percent(value: float, decimals: int = 2) -> str:
    """Format a numeric value as a percentage string."""

    return f"{value:.{decimals}f}%"


def parse_date(value: str | date | datetime | None) -> date | None:
    """Parse common date values into a date object."""

    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Data inválida: {value}")
