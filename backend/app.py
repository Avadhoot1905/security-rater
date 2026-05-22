import os
import time
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from utils.logger import clear_request_id, get_logger, set_request_id


logger = get_logger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parent
logger.info("Project root detected: %s", PROJECT_ROOT)
logger.info("Import mode: ABSOLUTE")

try:
    from blockchain.debug import (
        check_accounts,
        check_balance,
        check_execution_mode,
        check_web3_connection,
        send_test_transaction,
    )
    from blockchain.scorer import score_with_blockchain
    from core.features import build_features
    from scanner.dns import scan_dns
    from scanner.html import scan_html
    from scanner.http import scan_http
    from scanner.tls import scan_tls
    from scanner.whois import scan_whois
    from utils import normalize_domain
except ImportError:
    logger.exception("Failed to import backend modules using absolute imports")
    raise


load_dotenv(PROJECT_ROOT / ".env")


def _is_debug_enabled() -> bool:
    return os.getenv("DEBUG", "false").lower() == "true"


def _bootstrap_blockchain_checks() -> None:
    try:
        connection = check_web3_connection()
        if not connection.get("connected"):
            return
        check_execution_mode()
        check_accounts()
        check_balance()
    except Exception as error:
        logger.exception("[BC-DEBUG] Startup blockchain diagnostics failed: %s", error)


def create_app() -> Flask:
    app = Flask(__name__)
    _bootstrap_blockchain_checks()

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

    @app.get("/blockchain/debug")
    def blockchain_debug():
        run_test_tx = request.args.get("testTx", "false").lower() == "true"
        diagnostics = {
            "connection": check_web3_connection(),
            "execution_mode": check_execution_mode(),
            "accounts": check_accounts(),
            "balance": check_balance(),
        }
        if run_test_tx:
            diagnostics["test_transaction"] = send_test_transaction()
        return jsonify(diagnostics), 200

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
            if _is_debug_enabled():
                logger.debug("[BC-DEBUG] Scan features payload for %s: %s", domain, features)

            result = score_with_blockchain(domain, features)

            logger.info(
                "Completed scan pipeline for %s with score=%s grade=%s flags=%s chain_used=%s tx_hash=%s",
                domain,
                result.get("score"),
                result.get("grade"),
                result.get("flags", []),
                result.get("chain_used"),
                result.get("tx_hash"),
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