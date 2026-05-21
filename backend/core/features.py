from __future__ import annotations

from typing import Any, Dict


def build_features(
    *,
    domain: str,
    dns_data: Dict[str, Any],
    whois_data: Dict[str, Any],
    tls_data: Dict[str, Any],
    http_data: Dict[str, Any],
    html_data: Dict[str, Any],
) -> Dict[str, Any]:
    features = {
        "domain": domain,
        "dns": {
            "a_records": dns_data.get("a_records", []),
            "mx_records": dns_data.get("mx_records", []),
            "ns_records": dns_data.get("ns_records", []),
        },
        "whois": {
            "creation_date": whois_data.get("creation_date"),
            "age_days": whois_data.get("age_days", 0),
        },
        "tls": {
            "version": tls_data.get("version"),
            "certificate_expires_at": tls_data.get("certificate_expires_at"),
            "certificate_valid_days": tls_data.get("certificate_valid_days"),
        },
        "http": {
            "status_code": http_data.get("status_code"),
            "server": http_data.get("server"),
            "headers": http_data.get("headers", {}),
        },
        "html": {
            "forms_count": html_data.get("forms_count", 0),
            "links_count": html_data.get("links_count", 0),
            "scripts_count": html_data.get("scripts_count", 0),
            "login_forms_present": html_data.get("login_forms_present", False),
            "technologies": html_data.get("technologies", []),
        },
    }
    return features