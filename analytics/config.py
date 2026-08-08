"""Configuration dataclasses for the analytics framework."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class DatabaseConfig:
    """PostgreSQL connection configuration used by SQLAlchemy."""

    url: str
    pool_size: int = 5
    max_overflow: int = 10
    pool_recycle_seconds: int = 1800
    echo: bool = False

    @classmethod
    def from_env(cls, env_var: str = "DATABASE_URL") -> "DatabaseConfig":
        """Create config from an environment variable containing the DB URL."""

        value = os.getenv(env_var, "").strip()
        if not value:
            raise ValueError(f"Variável de ambiente {env_var} não configurada.")
        return cls(url=value)


@dataclass(frozen=True)
class CacheConfig:
    """Cache configuration for indicators and expensive query results."""

    enabled: bool = True
    ttl_seconds: int = 300
    max_items: int = 512


@dataclass(frozen=True)
class ExportConfig:
    """Default export options."""

    output_dir: Path = Path("exports")
    company_name: str = "Analytics"
    report_author: str = "analytics"
    page_size: str = "A4"


@dataclass(frozen=True)
class AnalyticsConfig:
    """Top-level configuration object for applications."""

    database: DatabaseConfig | None = None
    cache: CacheConfig = field(default_factory=CacheConfig)
    exports: ExportConfig = field(default_factory=ExportConfig)
    default_locale: str = "pt_BR"
