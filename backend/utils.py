from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse


def normalize_domain(value: str) -> str:
    if not value:
        return ""

    cleaned = value.strip().lower()
    if "//" in cleaned:
        parsed = urlparse(cleaned)
        cleaned = parsed.netloc or parsed.path

    cleaned = cleaned.split("/")[0]
    cleaned = cleaned.split(":")[0]
    if cleaned.startswith("www."):
        cleaned = cleaned[4:]

    cleaned = cleaned.rstrip(".")

    return cleaned.strip()


def safe_get(mapping: Any, key: str, default: Any = None) -> Any:
    if not isinstance(mapping, dict):
        return default
    return mapping.get(key, default)


def current_utc() -> datetime:
    return datetime.now(timezone.utc)


def clamp_score(value: int) -> int:
    return max(0, min(100, value))