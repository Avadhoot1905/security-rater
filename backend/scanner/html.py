from __future__ import annotations

import time
from typing import Any, Dict, List

import requests
from bs4 import BeautifulSoup

from utils.logger import get_logger


logger = get_logger(__name__)


def _detect_technologies(html: str) -> List[str]:
    technologies: List[str] = []
    lowered = html.lower()
    if "wp-content" in lowered:
        technologies.append("wordpress")
    if "__next_data__" in lowered:
        technologies.append("nextjs")
    if 'id="root"' in lowered or "id='root'" in lowered:
        technologies.append("react")
    return technologies


def scan_html(domain: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "forms_count": 0,
        "links_count": 0,
        "scripts_count": 0,
        "login_forms_present": False,
        "technologies": [],
    }
    url = f"https://{domain}"
    started_at = time.perf_counter()
    try:
        logger.info("HTML fetch start for %s", url)
        response = requests.get(url, timeout=8, allow_redirects=True)
        soup = BeautifulSoup(response.text, "html.parser")
        forms = soup.find_all("form")
        links = soup.find_all("a")
        scripts = soup.find_all("script")

        login_forms_present = False
        for form in forms:
            form_text = form.get_text(" ", strip=True).lower()
            form_html = str(form).lower()
            if any(token in form_text or token in form_html for token in ["login", "sign in", "password", "username", "email"]):
                login_forms_present = True
                break

        result.update(
            {
                "forms_count": len(forms),
                "links_count": len(links),
                "scripts_count": len(scripts),
                "login_forms_present": login_forms_present,
                "technologies": _detect_technologies(response.text),
            }
        )
        logger.info("HTML parse counts for %s: forms=%d links=%d scripts=%d", domain, len(forms), len(links), len(scripts))
        logger.info("Detected technologies for %s: %s", domain, result["technologies"])
    except Exception as error:
        logger.error("HTML parsing failed for %s: %s", domain, error)
    finally:
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        logger.info("[TIMER] html.py completed in %dms", elapsed_ms)
    return result