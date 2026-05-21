import os
import time
from uuid import uuid4

from flask import Flask, jsonify, request

from core.features import build_features
from core.scoring import score_features
from scanner.dns import scan_dns
from scanner.html import scan_html
from scanner.http import scan_http
from scanner.tls import scan_tls
from scanner.whois import scan_whois
from utils.logger import clear_request_id, get_logger, set_request_id
from utils import normalize_domain


logger = get_logger(__name__)


def create_app() -> Flask:
    app = Flask(__name__)

    @app.after_request
    def add_cors_headers(response):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        return response

    @app.before_request
    def handle_preflight():
        if request.method == "OPTIONS":
            return jsonify({}), 204

    @app.get("/health")
    def health():
        logger.info("Health check requested")
        return jsonify({"status": "ok"}), 200

    @app.get("/scan")
    def scan():
        request_id = str(uuid4())
        set_request_id(request_id)
        started_at = time.perf_counter()
        domain = normalize_domain(request.args.get("domain", ""))
        logger.info("Incoming scan request for domain=%s", domain or "<missing>")
        if not domain:
            logger.error("Scan rejected because domain query parameter is missing")
            clear_request_id()
            return jsonify({"error": "domain query parameter is required"}), 400

        try:
            logger.info("Starting scan pipeline for %s", domain)
            dns_data = scan_dns(domain)
            whois_data = scan_whois(domain)
            tls_data = scan_tls(domain)
            http_data = scan_http(domain)
            html_data = scan_html(domain)

            features = build_features(
                domain=domain,
                dns_data=dns_data,
                whois_data=whois_data,
                tls_data=tls_data,
                http_data=http_data,
                html_data=html_data,
            )
            result = score_features(features)

            logger.info(
                "Completed scan pipeline for %s with score=%s grade=%s flags=%s",
                domain,
                result.get("score"),
                result.get("grade"),
                result.get("flags", []),
            )
            logger.info("Partial data returned for %s: dns=%s whois=%s tls=%s http=%s html=%s", domain, bool(dns_data), bool(whois_data), bool(tls_data), bool(http_data), bool(html_data))
            total_ms = int((time.perf_counter() - started_at) * 1000)
            logger.info("Scan finished for %s in %dms", domain, total_ms)

            return jsonify(
                {
                    "domain": domain,
                    "features": features,
                    "result": result,
                }
            )
        except Exception:
            logger.exception("Unhandled failure in scan pipeline for %s", domain)
            return jsonify({"error": "scan failed"}), 500
        finally:
            clear_request_id()

    return app


app = create_app()


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    app.run(host="127.0.0.1", port=port, debug=True)