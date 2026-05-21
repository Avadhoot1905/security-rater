from __future__ import annotations

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

    return cleaned.rstrip(".").strip()


def safe_get(mapping, key, default=None):
    if not isinstance(mapping, dict):
        return default
    return mapping.get(key, default)


def clamp_score(value: int) -> int:
    return max(0, min(100, value))