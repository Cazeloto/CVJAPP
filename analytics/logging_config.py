"""Logging helpers for the analytics framework."""

from __future__ import annotations

import logging


def configure_logging(level: int = logging.INFO) -> None:
    """Configure a default logging format for applications that want it.

    The framework never configures logging automatically. Applications can call
    this helper during startup, or configure logging themselves.
    """

    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
