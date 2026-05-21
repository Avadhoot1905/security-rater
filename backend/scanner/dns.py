from __future__ import annotations

import logging
import time
from typing import Any, Dict, List

import dns.resolver

from utils.logger import get_logger


logger = get_logger(__name__)


def _resolve_records(domain: str, record_type: str) -> List[str]:
    started_at = time.perf_counter()
    try:
        logger.info("DNS resolution start for %s record on %s", record_type, domain)
        answers = dns.resolver.resolve(domain, record_type, lifetime=5)
        records = [str(answer).strip() for answer in answers]
        if records:
            logger.info("DNS %s results for %s: %d records", record_type, domain, len(records))
        else:
            logger.info("DNS %s returned no records for %s", record_type, domain)
        return records
    except Exception as error:
        logger.error("DNS %s lookup failed for %s: %s", record_type, domain, error)
        return []
    finally:
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        logger.info("[TIMER] dns.py %s completed in %dms", record_type, elapsed_ms)


def scan_dns(domain: str) -> Dict[str, Any]:
    logger.info("Starting DNS scan for %s", domain)
    return {
        "a_records": _resolve_records(domain, "A"),
        "mx_records": _resolve_records(domain, "MX"),
        "ns_records": _resolve_records(domain, "NS"),
    }