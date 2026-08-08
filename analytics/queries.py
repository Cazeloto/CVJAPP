"""SQL execution layer for raw SQL, views, and materialized views."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Iterable

from analytics.database import DatabaseManager
from analytics.exceptions import QueryExecutionError
from analytics.models import QueryResult, SQLQuery
from analytics.utils import require_dependency

logger = logging.getLogger(__name__)


class QueryRegistry:
    """In-memory registry for named SQL statements."""

    def __init__(self) -> None:
        """Create an empty SQL registry."""

        self._queries: dict[str, str] = {}

    def register(self, name: str, sql: str) -> None:
        """Register a SQL statement by name."""

        self._queries[name] = sql

    def load_file(self, name: str, path: str | Path) -> None:
        """Register SQL loaded from a .sql file."""

        self.register(name, Path(path).read_text(encoding="utf-8"))

    def get(self, name: str) -> str:
        """Return registered SQL by name."""

        try:
            return self._queries[name]
        except KeyError as exc:
            raise QueryExecutionError(f"Query não registrada: {name}") from exc


class QueryExecutor:
    """Executes raw SQL through a DatabaseManager."""

    def __init__(self, database: DatabaseManager) -> None:
        """Create an executor bound to a database manager."""

        self.database = database

    def fetch_dataframe(
        self,
        sql: str | SQLQuery,
        params: dict[str, Any] | None = None,
        chunksize: int | None = None,
    ) -> Any:
        """Execute SQL and return a Pandas DataFrame or chunk iterator."""

        require_dependency("pandas", "pandas")
        require_dependency("sqlalchemy", "SQLAlchemy")
        import pandas as pd
        from sqlalchemy import text

        query = sql if isinstance(sql, SQLQuery) else SQLQuery(name="adhoc", sql=sql)
        merged_params = dict(query.params)
        merged_params.update(params or {})
        logger.info("Executing dataframe query: %s", query.name)

        try:
            with self.database.connection() as conn:
                return pd.read_sql_query(
                    text(query.sql),
                    conn,
                    params=merged_params,
                    chunksize=chunksize,
                )
        except Exception as exc:
            logger.exception("Query failed: %s", query.name)
            raise QueryExecutionError(str(exc)) from exc

    def execute(self, sql: str | SQLQuery, params: dict[str, Any] | None = None) -> QueryResult:
        """Execute SQL that does not need to return a DataFrame."""

        require_dependency("sqlalchemy", "SQLAlchemy")
        from sqlalchemy import text

        query = sql if isinstance(sql, SQLQuery) else SQLQuery(name="adhoc", sql=sql)
        merged_params = dict(query.params)
        merged_params.update(params or {})
        started = time.perf_counter()

        try:
            with self.database.connection() as conn:
                result = conn.execute(text(query.sql), merged_params)
                conn.commit()
                elapsed = time.perf_counter() - started
                return QueryResult(
                    name=query.name,
                    row_count=result.rowcount if result.rowcount is not None else 0,
                    elapsed_seconds=elapsed,
                )
        except Exception as exc:
            logger.exception("SQL execution failed: %s", query.name)
            raise QueryExecutionError(str(exc)) from exc

    def fetch_many(
        self,
        sql: str | SQLQuery,
        params: dict[str, Any] | None = None,
    ) -> Iterable[dict[str, Any]]:
        """Execute SQL and yield rows as dictionaries without Pandas."""

        require_dependency("sqlalchemy", "SQLAlchemy")
        from sqlalchemy import text

        query = sql if isinstance(sql, SQLQuery) else SQLQuery(name="adhoc", sql=sql)
        merged_params = dict(query.params)
        merged_params.update(params or {})

        try:
            with self.database.connection() as conn:
                for row in conn.execute(text(query.sql), merged_params).mappings():
                    yield dict(row)
        except Exception as exc:
            logger.exception("Row streaming failed: %s", query.name)
            raise QueryExecutionError(str(exc)) from exc
