from flask import Flask, jsonify, request

from core.features import build_features
from core.scoring import score_features
from scanner.dns import scan_dns
from scanner.html import scan_html
from scanner.http import scan_http
from scanner.tls import scan_tls
from scanner.whois import scan_whois
from utils import normalize_domain


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/scan")
    def scan():
        domain = normalize_domain(request.args.get("domain", ""))
        if not domain:
            return jsonify({"error": "domain query parameter is required"}), 400

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

        return jsonify(
            {
                "domain": domain,
                "features": features,
                "result": result,
            }
        )

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)