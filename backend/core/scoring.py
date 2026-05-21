from __future__ import annotations

from typing import Any, Dict, List

from utils import clamp_score
from utils.logger import get_logger, log_duration


logger = get_logger(__name__)


def grade_for_score(score: int) -> str:
    if score >= 85:
        return "A"
    if score >= 70:
        return "B"
    if score >= 55:
        return "C"
    return "D"


def score_features(features: Dict[str, Any]) -> Dict[str, Any]:
    with log_duration(logger, "scoring.py"):
        try:
            logger.info("Scoring started for %s", features.get("domain", "<unknown>"))

            score = 50
            flags: List[str] = []

            age_days = features.get("whois", {}).get("age_days") or 0
            age_delta = 0
            if age_days > 365 * 5:
                age_delta = 20
                score += age_delta
            elif age_days >= 365:
                age_delta = 10
                score += age_delta
            else:
                age_delta = -10
                score += age_delta
                flags.append("domain_new")
            logger.info("Domain age contribution for %s: %s (age_days=%s)", features.get("domain", "<unknown>"), age_delta, age_days)

            tls_version = (features.get("tls", {}).get("version") or "").upper()
            tls_delta = 0
            if tls_version == "TLSV1.3" or tls_version == "TLS 1.3" or tls_version == "1.3":
                tls_delta = 15
                score += tls_delta
            elif tls_version == "TLSV1.2" or tls_version == "TLS 1.2" or tls_version == "1.2":
                tls_delta = 5
                score += tls_delta
            else:
                tls_delta = -15
                score += tls_delta
                flags.append("weak_tls_or_unknown")
            logger.info("TLS contribution for %s: %s (version=%s)", features.get("domain", "<unknown>"), tls_delta, tls_version or "unknown")

            headers = features.get("http", {}).get("headers") or {}
            header_keys = {key.lower() for key in headers.keys()}
            header_delta = 0
            if "strict-transport-security" in header_keys:
                header_delta += 5
            else:
                flags.append("missing_hsts")
            if "content-security-policy" in header_keys:
                header_delta += 5
            else:
                flags.append("missing_csp")
            if "x-frame-options" in header_keys:
                header_delta += 3
            score += header_delta
            logger.info("Headers contribution for %s: %s", features.get("domain", "<unknown>"), header_delta)

            server = (features.get("http", {}).get("server") or "").strip()
            header_values = " ".join(str(value) for value in headers.values()).lower()
            exposure_delta = 0
            if server:
                if "cloudflare" in server.lower() or "cloudflare" in header_values:
                    exposure_delta += 10
                else:
                    exposure_delta -= 10
                    flags.append("raw_server_exposed")
            else:
                flags.append("server_header_missing")
            score += exposure_delta
            logger.info("Infrastructure exposure contribution for %s: %s (server=%s)", features.get("domain", "<unknown>"), exposure_delta, server or "missing")

            forms_count = features.get("html", {}).get("forms_count") or 0
            login_forms_present = bool(features.get("html", {}).get("login_forms_present"))
            surface_delta = 0
            if forms_count > 0:
                surface_delta -= 2
            if login_forms_present:
                surface_delta -= 3
                flags.append("login_forms_present")
            technologies = features.get("html", {}).get("technologies") or []
            if "wordpress" in technologies:
                surface_delta -= 5
                flags.append("wordpress_detected")
            score += surface_delta
            logger.info("Surface contribution for %s: %s", features.get("domain", "<unknown>"), surface_delta)

            score = clamp_score(score)
            result = {
                "score": score,
                "grade": grade_for_score(score),
                "flags": flags,
            }
            logger.info("Final score for %s: %s (%s)", features.get("domain", "<unknown>"), result["score"], result["grade"])
            return result
        except Exception as error:
            logger.error("Scoring failed for %s: %s", features.get("domain", "<unknown>"), error)
            return {"score": 50, "grade": "C", "flags": ["scoring_error"]}