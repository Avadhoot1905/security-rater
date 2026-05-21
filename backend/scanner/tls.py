from __future__ import annotations

import socket
import ssl
from datetime import datetime, timezone
from typing import Any, Dict


def scan_tls(domain: str, port: int = 443) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "version": None,
        "certificate_expires_at": None,
        "certificate_valid_days": None,
    }
    try:
        context = ssl.create_default_context()
        with socket.create_connection((domain, port), timeout=5) as raw_socket:
            with context.wrap_socket(raw_socket, server_hostname=domain) as secure_socket:
                result["version"] = secure_socket.version()
                certificate = secure_socket.getpeercert()
                not_after = certificate.get("notAfter")
                if not_after:
                    expires_at = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
                    result["certificate_expires_at"] = expires_at.isoformat()
                    result["certificate_valid_days"] = max((expires_at - datetime.now(timezone.utc)).days, 0)
    except Exception as error:
        print(f"tls handshake failed for {domain}: {error}")
    return result