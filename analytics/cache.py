"""Simple TTL cache for indicators and expensive analytics operations."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable, TypeVar

from analytics.config import CacheConfig
from analytics.utils import stable_hash

logger = logging.getLogger(__name__)
T = TypeVar("T")


@dataclass
class _CacheEntry:
    value: Any
    expires_at: float


class CacheManager:
    """Small in-memory TTL cache with deterministic keys."""

    def __init__(self, config: CacheConfig | None = None) -> None:
        """Create a cache manager."""

        self.config = config or CacheConfig()
        self._items: dict[str, _CacheEntry] = {}

    def build_key(self, namespace: str, payload: Any) -> str:
        """Build a stable cache key."""

        return f"{namespace}:{stable_hash(payload)}"

    def get(self, key: str) -> Any | None:
        """Return a cached value, or None when missing/expired/disabled."""

        if not self.config.enabled:
            return None
        entry = self._items.get(key)
        if entry is None:
            return None
        if entry.expires_at < time.time():
            self._items.pop(key, None)
            return None
        return entry.value

    def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        """Store a value in cache."""

        if not self.config.enabled:
            return
        if len(self._items) >= self.config.max_items:
            oldest = min(self._items, key=lambda item: self._items[item].expires_at)
            self._items.pop(oldest, None)
        ttl = ttl_seconds if ttl_seconds is not None else self.config.ttl_seconds
        self._items[key] = _CacheEntry(value=value, expires_at=time.time() + ttl)

    def clear(self) -> None:
        """Clear all cached values."""

        self._items.clear()

    def cached(self, namespace: str) -> Callable[[Callable[..., T]], Callable[..., T]]:
        """Decorate a pure function with TTL caching."""

        def decorator(func: Callable[..., T]) -> Callable[..., T]:
            @wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> T:
                key = self.build_key(namespace, {"args": args, "kwargs": kwargs})
                value = self.get(key)
                if value is not None:
                    logger.debug("Cache hit: %s", key)
                    return value
                result = func(*args, **kwargs)
                self.set(key, result)
                return result

            return wrapper

        return decorator
