from __future__ import annotations

from typing import Any, Dict, List

from utils import clamp_score


def grade_for_score(score: int) -> str:
    if score >= 85:
        return "A"
    if score >= 70:
        return "B"
    if score >= 55:
        return "C"
    return "D"


def score_features(features: Dict[str, Any]) -> Dict[str, Any]:
    score = 50
    flags: List[str] = []

    age_days = features.get("whois", {}).get("age_days") or 0
    if age_days > 365 * 5:
        score += 20
    elif age_days >= 365:
        score += 10
    else:
        score -= 10
        flags.append("domain_new")

    tls_version = (features.get("tls", {}).get("version") or "").upper()
    if tls_version == "TLSV1.3" or tls_version == "TLS 1.3" or tls_version == "1.3":
        score += 15
    elif tls_version == "TLSV1.2" or tls_version == "TLS 1.2" or tls_version == "1.2":
        score += 5
    else:
        score -= 15
        flags.append("weak_tls_or_unknown")

    headers = features.get("http", {}).get("headers") or {}
    header_keys = {key.lower() for key in headers.keys()}
    if "strict-transport-security" in header_keys:
        score += 5
    else:
        flags.append("missing_hsts")
    if "content-security-policy" in header_keys:
        score += 5
    else:
        flags.append("missing_csp")
    if "x-frame-options" in header_keys:
        score += 3

    server = (features.get("http", {}).get("server") or "").strip()
    header_values = " ".join(str(value) for value in headers.values()).lower()
    if server:
        if "cloudflare" in server.lower() or "cloudflare" in header_values:
            score += 10
        else:
            score -= 10
            flags.append("raw_server_exposed")
    else:
        flags.append("server_header_missing")

    forms_count = features.get("html", {}).get("forms_count") or 0
    login_forms_present = bool(features.get("html", {}).get("login_forms_present"))
    if forms_count > 0:
        score -= 2
    if login_forms_present:
        score -= 3
        flags.append("login_forms_present")

    technologies = features.get("html", {}).get("technologies") or []
    if "wordpress" in technologies:
        score -= 5
        flags.append("wordpress_detected")

    score = clamp_score(score)
    return {
        "score": score,
        "grade": grade_for_score(score),
        "flags": flags,
    }