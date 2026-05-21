from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Dict

import whois


def _first_datetime(value: Any) -> datetime | None:
    if isinstance(value, list):
        for item in value:
            if isinstance(item, datetime):
                return item
            if isinstance(item, date):
                return datetime.combine(item, datetime.min.time())
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    return None


def scan_whois(domain: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {"creation_date": None, "age_days": 0}
    try:
        data = whois.whois(domain)
        creation_date = _first_datetime(getattr(data, "creation_date", None) or data.get("creation_date"))
        if creation_date is not None:
            if creation_date.tzinfo is None:
                creation_date = creation_date.replace(tzinfo=timezone.utc)
            age_days = max((datetime.now(timezone.utc) - creation_date).days, 0)
            result["creation_date"] = creation_date.isoformat()
            result["age_days"] = age_days
    except Exception as error:
        print(f"whois lookup failed for {domain}: {error}")
    return result