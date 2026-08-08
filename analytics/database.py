"""Database connection management using SQLAlchemy engines."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Iterator

from analytics.config import DatabaseConfig
from analytics.exceptions import DatabaseConnectionError
from analytics.utils import require_dependency

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Owns the SQLAlchemy engine and exposes connection helpers."""

    def __init__(self, config: DatabaseConfig) -> None:
        """Create a manager from database configuration."""

        self.config = config
        self._engine: Any | None = None

    @property
    def engine(self) -> Any:
        """Return a lazily-created SQLAlchemy engine."""

        if self._engine is None:
            require_dependency("sqlalchemy", "SQLAlchemy")
            from sqlalchemy import create_engine

            try:
                self._engine = create_engine(
                    self.config.url,
                    pool_size=self.config.pool_size,
                    max_overflow=self.config.max_overflow,
                    pool_recycle=self.config.pool_recycle_seconds,
                    echo=self.config.echo,
                    future=True,
                )
            except Exception as exc:
                logger.exception("Could not create SQLAlchemy engine.")
                raise DatabaseConnectionError(str(exc)) from exc
        return self._engine

    @contextmanager
    def connection(self) -> Iterator[Any]:
        """Yield a SQLAlchemy connection and close it afterwards."""

        try:
            with self.engine.connect() as conn:
                yield conn
        except Exception as exc:
            logger.exception("Database connection failed.")
            raise DatabaseConnectionError(str(exc)) from exc

    def test_connection(self) -> bool:
        """Return True when the database accepts a simple SELECT 1."""

        require_dependency("sqlalchemy", "SQLAlchemy")
        from sqlalchemy import text

        with self.connection() as conn:
            conn.execute(text("SELECT 1"))
        return True

    def dispose(self) -> None:
        """Dispose the SQLAlchemy engine if it was created."""

        if self._engine is not None:
            self._engine.dispose()
            self._engine = None
