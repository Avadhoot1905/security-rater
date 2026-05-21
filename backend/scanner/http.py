from __future__ import annotations

from typing import Any, Dict

import requests


def scan_http(domain: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {"status_code": None, "server": None, "headers": {}}
    url = f"https://{domain}"
    try:
        response = requests.get(url, timeout=8, allow_redirects=True)
        result["status_code"] = response.status_code
        result["headers"] = dict(response.headers)
        result["server"] = response.headers.get("Server")
    except Exception as error:
        print(f"http request failed for {domain}: {error}")
    return result