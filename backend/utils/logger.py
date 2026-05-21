from __future__ import annotations

import logging
import os
import sys
import time
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator


_configured = False
_request_id: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _request_id.get()
        return True


def configure_logging() -> None:
    global _configured
    if _configured:
        return

    level = logging.DEBUG if os.getenv("DEBUG", "false").lower() == "true" else logging.INFO
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s | %(levelname)s | %(filename)s | %(request_id)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    handler.addFilter(RequestIdFilter())

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.propagate = False

    _configured = True


def get_logger(name: str | None = None) -> logging.Logger:
    configure_logging()
    return logging.getLogger(name)


def set_request_id(request_id: str) -> None:
    _request_id.set(request_id)


def clear_request_id() -> None:
    _request_id.set("-")


def current_request_id() -> str:
    return _request_id.get()


@contextmanager
def log_duration(logger: logging.Logger, label: str) -> Iterator[None]:
    started_at = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        logger.info("[TIMER] %s completed in %dms", label, elapsed_ms)