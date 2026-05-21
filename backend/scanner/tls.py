from __future__ import annotations

import time
import socket
import ssl
from datetime import datetime, timezone
from typing import Any, Dict

from utils.logger import get_logger


logger = get_logger(__name__)


def scan_tls(domain: str, port: int = 443) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "version": None,
        "certificate_expires_at": None,
        "certificate_valid_days": None,
    }
    started_at = time.perf_counter()
    try:
        logger.info("TLS handshake start for %s:%d", domain, port)
        context = ssl.create_default_context()
        with socket.create_connection((domain, port), timeout=5) as raw_socket:
            with context.wrap_socket(raw_socket, server_hostname=domain) as secure_socket:
                result["version"] = secure_socket.version()
                logger.info("TLS version detected for %s: %s", domain, result["version"] or "unknown")
                certificate = secure_socket.getpeercert()
                not_after = certificate.get("notAfter")
                if not_after:
                    expires_at = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
                    result["certificate_expires_at"] = expires_at.isoformat()
                    result["certificate_valid_days"] = max((expires_at - datetime.now(timezone.utc)).days, 0)
                    logger.info("TLS certificate expiry for %s: %s", domain, result["certificate_expires_at"])
    except Exception as error:
        logger.error("TLS handshake failed for %s: %s", domain, error)
    finally:
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        logger.info("[TIMER] tls.py completed in %dms", elapsed_ms)
    return result