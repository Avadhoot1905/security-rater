from __future__ import annotations

from typing import Any, Dict, List

import dns.resolver


def _resolve_records(domain: str, record_type: str) -> List[str]:
    try:
        answers = dns.resolver.resolve(domain, record_type, lifetime=5)
        return [str(answer).strip() for answer in answers]
    except Exception as error:
        print(f"dns {record_type} lookup failed for {domain}: {error}")
        return []


def scan_dns(domain: str) -> Dict[str, Any]:
    return {
        "a_records": _resolve_records(domain, "A"),
        "mx_records": _resolve_records(domain, "MX"),
        "ns_records": _resolve_records(domain, "NS"),
    }