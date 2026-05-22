# Website Security Rating System

A focused tool that converts public internet signals about a domain into a structured, auditable security rating. Enter a domain, the backend runs a light recon pipeline (DNS, WHOIS, TLS, HTTP, HTML), extracts signals, computes a deterministic security score and grade — optionally persisting the calculation on a local Ethereum-compatible chain (Ganache) via a Solidity contract — and the React frontend visualizes the results.

Why this exists
- Many security posture tools are heavyweight or require privileged access. This project demonstrates a reproducible, transparent pipeline to assess external-facing website security signals.

Problem statement
- Given just a domain name, produce a concise security score, explain which signals influenced it, and provide an auditable record of the scoring logic.

What blockchain solves here
- Transparency & immutability: the scoring logic (MVP deterministic formula) can be executed on-chain and an event emitted so third-parties can verify that a particular score was computed and persisted.
- Audit trail: contract stores latest score by hashed domain and emits a `ScoreCalculated` event.

What blockchain does NOT solve
- It does not replace the live scanning work (the scanners run off-chain). The blockchain component only stores/executes the deterministic scoring logic and provides an auditable record — it is not a distributed crawler, nor is it a source of raw signals.

This README was generated from the repository source to reflect actual implementation details.

---

## Architecture Overview

Simple linear pipeline implemented in the codebase:

Domain
↓
Recon (DNS, WHOIS)
↓
HTTP Probe (TLS + HTTP headers)
↓
HTML parse (homepage signals)
↓
Feature extraction (Python aggregator)
↓
Blockchain scoring (Solidity contract on Ganache) OR local scoring fallback
↓
Frontend visualization (Vite + React)

Explanation of each layer
- Domain: input normalized by `backend/utils/normalize_domain` and validated by the Flask `GET /scan` endpoint.
- Recon: `backend/scanner/dns.py` resolves A/MX/NS records; `backend/scanner/whois.py` extracts domain creation date and computes age in days.
- HTTP Probe: `backend/scanner/tls.py` performs a TLS handshake to read TLS version and certificate expiry; `backend/scanner/http.py` issues an HTTPS GET and collects status and response headers.
- HTML parse: `backend/scanner/html.py` fetches the homepage and extracts counts (forms, links, scripts), detects login forms and a small set of technologies (WordPress, Next.js, React) via token matching.
- Feature extraction: `backend/core/features.py` composes a normalized feature vector used by the scoring engine.
- Blockchain scoring: `backend/blockchain/SecurityScore.sol` implements the deterministic scoring formula; `backend/blockchain/deploy.py` compiles and deploys the contract; `backend/blockchain/scorer.py` calls the contract to persist and retrieve scores. When blockchain is unavailable or misconfigured the service falls back to the local scorer in `backend/core/scoring.py`.
- Frontend: `frontend/src` contains a minimal React UI (Vite) which calls the backend `/scan` endpoint and renders a `ResultCard` and `FeatureList`.

## Features (implemented)
- DNS: A, MX, NS lookups (`backend/scanner/dns.py`).
- WHOIS: domain creation date and age computation (`backend/scanner/whois.py`).
- TLS inspection: TLS version, certificate expiry and days remaining (`backend/scanner/tls.py`).
- HTTP probe: status code, full response headers and `Server` header capture (`backend/scanner/http.py`).
- Homepage scanning: counts of forms/links/scripts, login form detection, lightweight technology fingerprinting (`backend/scanner/html.py`).
- Deterministic scoring: Python-based local scoring (`backend/core/scoring.py`) used as fallback or for local-only runs.
- Solidity scoring contract: `SecurityScore.sol` implements the same deterministic rules on-chain and emits `ScoreCalculated` events.
- Ganache integration: deployment and diagnostic utilities (`backend/blockchain/deploy.py`, `debug.py`, `refuel.py`, `account_validator.py`).
- Logging and timing: request-scoped request IDs and duration timers (`backend/utils/logger.py`).
- Blockchain fallback mechanism: `backend/blockchain/scorer.py` will use local scoring if artifacts are missing or the chain is unreachable.

## Repository Structure

Top-level layout (important files):

backend/
- app.py                - Flask application and HTTP routes (`/health`, `/scan`, `/blockchain/debug`).
- requirements.txt      - Python dependencies.
- core/
	- features.py         - Aggregates scanner outputs into a feature vector.
	- scoring.py          - Local deterministic scoring engine (same logic as the contract).
- scanner/
	- dns.py              - DNS lookups (A, MX, NS).
	- whois.py            - WHOIS lookup and domain age computation.
	- tls.py              - TLS handshake and certificate parsing.
	- http.py             - HTTPS probe (status + headers).
	- html.py             - Homepage parsing and tech detection.
- blockchain/
	- SecurityScore.sol   - Solidity contract (scoring logic, storage, events).
	- deploy.py           - Compile (py-solc-x) and deploy contract to Ganache, writes `artifacts.json`.
	- artifacts.json      - Contract address, ABI, provider and deployment metadata (generated by `deploy.py`).
	- scorer.py           - Web3-based flow that submits scoring tx and reads on-chain score; falls back to local scoring.
	- debug.py            - Small helpers for Web3 connection, execution mode (Mode A: Ganache unlocked, Mode B: PRIVATE_KEY).
	- refuel.py           - Utility to transfer ETH between Ganache accounts to fund the deployer.
	- account_validator.py- Validates/chooses the deploying account and checks balances.
- utils/
	- logger.py           - Structured logging, timers, request-id context.
	- __init__.py         - helpers: `normalize_domain`, `clamp_score`, `safe_get`.

frontend/
- package.json          - Vite + React configuration and scripts.
- index.html
- src/
	- api/scan.js         - `scanDomain(domain)` wrapper calling backend `/scan`.
	- App.jsx             - Application shell wiring input → scan → results.
	- components/*        - `DomainInput`, `ResultCard`, `FeatureList` UI components.

Other
- README.md             - (this file)

## Installation

Prerequisites
- Python 3.10+ recommended
- Node 18+ (for frontend dev server)
- Ganache (local Ethereum chain) for the on-chain flow. Install `ganache` or `ganache-cli`.

Backend
1. Create and activate a virtual environment

	 Mac / Linux

	 ```bash
	 python -m venv venv
	 source venv/bin/activate
	 ```

	 Windows (PowerShell)

	 ```powershell
	 python -m venv venv
	 .\venv\Scripts\Activate.ps1
	 ```

2. Install dependencies

	 ```bash
	 cd backend
	 pip install -r requirements.txt
	 ```

Frontend

1. Install dependencies

	 ```bash
	 cd frontend
	 npm install
	 ```

## Environment (.env.example)

Create `backend/.env` (do NOT commit real secrets). Example variables used by the code:

```
# Backend / blockchain
GANACHE_RPC_URL=http://127.0.0.1:7545   # RPC provider for Ganache
GANACHE_URL=http://127.0.0.1:7545       # alternative name used in some modules
ACCOUNT_ADDRESS=                         # optional explicitly configured deployer address
PRIVATE_KEY=                             # optional private key (MODE B). Keep private.
SOLC_VERSION=0.8.19                      # solc version used by deploy.py

# App
PORT=8080                                # Flask server port (app.py default)
DEBUG=false                              # Set to "true" for verbose logging

# Frontend (vite) - set in frontend/.env or pass as environment
VITE_API_BASE_URL=http://127.0.0.1:8080   # URL the frontend will call (used by frontend/src/api/scan.js)
```

Notes
- `PRIVATE_KEY` and `ACCOUNT_ADDRESS` enable "Mode B" (signed transactions). Without them the code uses Ganache unlocked accounts (Mode A).
- `artifacts.json` (generated by `deploy.py`) contains the contract ABI and deployed address and is required for the on-chain scoring flow.

## Running Locally

1) Start Ganache (optional — only required for on-chain persistence)

	 Examples:

	 ```bash
	 # Ganache v7+ (recommended)
	 ganache --chainId 1337 --port 7545

	 # Or legacy CLI
	 ganache-cli -p 7545 -i 1337
	 ```

	 Expected RPC URL: `http://127.0.0.1:7545` (default in artifacts and code). Chain ID used by provided artifacts: `1337`.

2) Backend

	 ```bash
	 cd backend
	 source ../venv/bin/activate    # if not already activated
	 python app.py
	 ```

	 By default the Flask app binds to `127.0.0.1:8080` (see `PORT` environment variable).

3) Frontend

	 ```bash
	 cd frontend
	 npm run dev
	 ```

	 Ensure `VITE_API_BASE_URL` points to the Flask server (for example `http://127.0.0.1:8080`).

## Blockchain Setup & Deployment

1. Start Ganache (see above).
2. Ensure `backend/.env` is populated with `GANACHE_RPC_URL` (or use defaults).
3. Compile & deploy the contract (from the `backend` directory):

	 ```bash
	 cd backend
	 # Deploy script compiles (py-solc-x) and writes backend/blockchain/artifacts.json
	 python -m blockchain.deploy
	 # or
	 python blockchain/deploy.py
	 ```

4. Inspect `backend/blockchain/artifacts.json` — it contains `address`, `abi`, `provider`, and deployment metadata. `backend/blockchain/scorer.py` reads this file to connect and call the contract.

5. Optional: run quick diagnostics

	 ```bash
	 # from backend folder
	 python -c "from blockchain.debug import check_web3_connection; print(check_web3_connection())"

	 # or use the running Flask endpoint
	 curl 'http://127.0.0.1:8080/blockchain/debug?testTx=true'
	 ```

Notes
- `deploy.py` enforces Solidity pragma compatibility (expects `^0.8.19` in the contract) and will install the requested solc version via `py-solc-x`.
- If the deployer account balance is below thresholds the script will attempt to `refuel` using another Ganache account (`refuel.py`). This assumes Ganache has multiple accounts with funds.

## Debugging Guide (common issues)

- Issue: Ganache connection fails / Web3 disconnected
	- Cause: Ganache not running or wrong RPC URL.
	- Fix: Start Ganache and confirm RPC URL (default: `http://127.0.0.1:7545`). Use `python -c "from blockchain.debug import check_web3_connection; print(check_web3_connection())"` to verify.

- Issue: Account not found / Private key mismatch
	- Cause: `PRIVATE_KEY` and `ACCOUNT_ADDRESS` mismatch or `PRIVATE_KEY` derived address not present in Ganache.
	- Fix: Remove `ACCOUNT_ADDRESS` to let the derived address be used, or ensure the corresponding account is present in Ganache or use Mode A (no private key).

- Issue: Insufficient funds during deploy
	- Cause: Deploy account balance below `DEPLOYMENT_BALANCE_THRESHOLD_ETH` in `deploy.py`.
	- Fix: Either fund the account in Ganache UI or run `python -m blockchain.refuel` (from `backend`) to transfer ETH from another unlocked account.

- Issue: Transaction reverted / status == 0
	- Cause: Contract call logic reverted (bad inputs) or gas/evm compatibility issue.
	- Fix: Inspect transaction receipt (gasUsed, blockNumber). Re-run `deploy.py` after confirming compiler/evm versions and check `SecurityScore.sol` constructor parameters.

- Issue: Solidity pragma/compiler mismatch
	- Cause: `SecurityScore.sol` pragma does not match `SOLC_VERSION` used by `deploy.py`.
	- Fix: Ensure `SOLC_VERSION` in `.env` or `deploy.py` default matches the contract pragma (project uses `^0.8.19`).

- Issue: Missing `artifacts.json`
	- Cause: Contract not deployed or `deploy.py` not run.
	- Fix: Run the deploy command. The file should appear in `backend/blockchain/artifacts.json` and include `address` and `abi`.

- Issue: Import problems running modules as packages
	- Cause: Running from incorrect working directory changes import behaviour.
	- Fix: Run scripts from the `backend` directory (e.g., `cd backend && python blockchain/deploy.py`) or use the project root and `python -m backend.blockchain.deploy` if Python package resolution is desired.

## API Documentation

Base: `GET /` is not provided — use the endpoints below.

1) Health
- GET `/health`

Response (200):

```json
{ "status": "ok" }
```

2) Blockchain diagnostics
- GET `/blockchain/debug`
- Query params: `testTx=true` optionally runs a small send transaction test (requires at least two Ganache accounts or `PRIVATE_KEY` configured).

Response (200, sample):

```json
{
	"connection": { "provider_url": "http://127.0.0.1:7545", "connected": true, "chain_id": 1337 },
	"execution_mode": { "mode": "A", "mode_name": "ganache_unlocked", "signer": "0x...", "private_key_configured": false },
	"accounts": { "accounts": ["0x...","0x..."], "count": 2 },
	"balance": { "account": "0x...","balance_wei": 10000000000000000000, "balance_eth": "10" },
	"test_transaction": { "tx_hash": "0x...", "status": 1 }
}
```

3) Scan endpoint
- GET `/scan?domain=example.com`
- The handler normalizes the domain, runs DNS/WHOIS/TLS/HTTP/HTML probes, builds features, then calls `score_with_blockchain` which either persists to chain and returns on-chain result or falls back to local scoring.

Response (200, sample):

```json
{
	"domain": "example.com",
	"features": {
		"domain": "example.com",
		"dns": { "a_records": ["1.2.3.4"], "mx_records": [], "ns_records": ["ns1.example.com"] },
		"whois": { "creation_date": "2018-01-01T00:00:00+00:00", "age_days": 3000 },
		"tls": { "version": "TLSv1.3", "certificate_expires_at": "2027-01-01T00:00:00+00:00", "certificate_valid_days": 365 },
		"http": { "status_code": 200, "server": "cloudflare", "headers": { ... } },
		"html": { "forms_count": 2, "links_count": 10, "scripts_count": 5, "login_forms_present": true, "technologies": ["wordpress"] }
	},
	"result": {
		"blockchain_score": 85,
		"score": 85,
		"grade": "A",
		"tx_hash": "0x...", 
		"block_number": 123,
		"gas_used": 21000,
		"status": 1,
		"chain_used": true,
		"flags": []
	}
}
```

Error responses include a JSON `error` key and appropriate HTTP status codes (400 for missing domain, 500 for internal failures).

## Scoring Logic

The scoring logic is intentionally simple and deterministic. It exists in two places:

- `backend/core/scoring.py` (Python local scorer used as fallback)
- `backend/blockchain/SecurityScore.sol` (Solidity contract used for on-chain scoring)

Rules (summarized)
- Base score: 50.
- Domain age:
	- > 5 years: +20
	- >= 1 year: +10
	- else: -10 and `domain_new` flag
- TLS version:
	- TLS 1.3: +15
	- TLS 1.2: +5
	- else: -15 and `weak_tls_or_unknown` flag
- HTTP security headers:
	- `strict-transport-security` (HSTS): +5 else `missing_hsts` flag
	- `content-security-policy` (CSP): +5 else `missing_csp` flag
- Server exposure:
	- `cloudflare` observed: +10
	- otherwise -10 and `raw_server_exposed` flag
	- missing `Server` header adds `server_header_missing` flag
- Homepage surface:
	- presence of forms: -2
	- login forms: -3 + `login_forms_present` flag
	- WordPress detected: -5 + `wordpress_detected` flag

The Solidity contract implements the same adjustments so that on-chain and local scoring remain compatible. The `scorer.py` module translates the Python feature vector into primitive types expected by the contract.

Fallback behavior
- If `backend/blockchain/artifacts.json` is missing, malformed, or the chain is unreachable the code logs a warning and returns the local scoring result alongside a `fallback_reason` and `chain_used: false`.

## Development Notes

- Heavy scans are avoided: the project only probes the live homepage and a small set of signals to remain fast and safe for unauthenticated scans.
- Homepage-only analysis: HTML parsing operates against the root URL (`https://{domain}`) and extracts lightweight features (forms, scripts, links, simple technology tokens) — this keeps the tool non-invasive.
- Blockchain responsibility separation: the chain stores and executes the deterministic grading logic and provides immutability for results — raw scans and network requests remain off-chain for performance and cost reasons.

## Future Roadmap

- Phase 2: Expand scanning surface (crawler with endpoint graph and rate limits).
- Phase 3: ML-backed scoring using historical labeled data and signals.
- Phase 4: Multi-oracle architecture to combine multiple on-chain verifiers and distributed scoring consensus.

---

If you'd like, I can also:
- run the backend test import/quick-checks (syntax & import verification),
- generate a `backend/.env.example` file in the repo, or
- add a short CONTRIBUTING.md with run/debug steps.

Changes made: README replaced with a code-driven, production-style document.