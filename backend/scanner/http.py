from __future__ import annotations

import time
from typing import Any, Dict

import requests

from utils.logger import get_logger


logger = get_logger(__name__)


def scan_http(domain: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {"status_code": None, "server": None, "headers": {}}
    url = f"https://{domain}"
    started_at = time.perf_counter()
    try:
        logger.info("HTTP request start for %s", url)
        response = requests.get(url, timeout=8, allow_redirects=True)
        result["status_code"] = response.status_code
        result["headers"] = dict(response.headers)
        result["server"] = response.headers.get("Server")
        logger.info("HTTP status code for %s: %s", domain, response.status_code)
        if result["server"]:
            logger.info("Server header detected for %s: %s", domain, result["server"])
        else:
            logger.info("No server header detected for %s", domain)
    except Exception as error:
        logger.error("HTTP request failed for %s: %s", domain, error)
    finally:
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        logger.info("[TIMER] http.py completed in %dms", elapsed_ms)
    return result