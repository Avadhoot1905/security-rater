from __future__ import annotations

from typing import Any, Dict, List

import requests
from bs4 import BeautifulSoup


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
    try:
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
    except Exception as error:
        print(f"html fetch failed for {domain}: {error}")
    return result