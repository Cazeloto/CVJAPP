"""Framework-specific exceptions."""


class AnalyticsError(Exception):
    """Base exception for all analytics framework errors."""


class DependencyMissingError(AnalyticsError):
    """Raised when an optional analytics dependency is not installed."""


class DatabaseConnectionError(AnalyticsError):
    """Raised when the database connection cannot be created or used."""


class QueryExecutionError(AnalyticsError):
    """Raised when a SQL query fails."""


class InvalidIndicatorError(AnalyticsError):
    """Raised when an indicator cannot be calculated from the provided data."""


class ChartGenerationError(AnalyticsError):
    """Raised when a chart cannot be generated."""


class ExportError(AnalyticsError):
    """Raised when an export cannot be generated."""


class CacheError(AnalyticsError):
    """Raised when the cache layer fails."""
