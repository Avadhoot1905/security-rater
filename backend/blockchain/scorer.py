from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv
from web3 import HTTPProvider, Web3

from core.scoring import score_features
from blockchain.debug import check_execution_mode
from utils.logger import get_logger


logger = get_logger(__name__)

BASE_DIR = Path(__file__).resolve().parent
ARTIFACTS_FILE = BASE_DIR / "artifacts.json"
DEFAULT_RPC_URL = "http://127.0.0.1:7545"

load_dotenv(BASE_DIR.parent / ".env")


def _tls_version_to_code(raw_value: str | None) -> int:
    value = (raw_value or "").upper().strip()
    if value in {"TLSV1.3", "TLS 1.3", "1.3"}:
        return 13
    if value in {"TLSV1.2", "TLS 1.2", "1.2"}:
        return 12
    return 0


def _extract_blockchain_features(features: Dict[str, Any]) -> Dict[str, Any]:
    headers = features.get("http", {}).get("headers") or {}
    header_keys = {str(key).lower() for key in headers.keys()}
    header_values_blob = " ".join(str(value).lower() for value in headers.values())
    server_header = str(features.get("http", {}).get("server") or "").lower()

    technologies = [str(item).lower() for item in (features.get("html", {}).get("technologies") or [])]

    return {
        "domainAgeDays": int(features.get("whois", {}).get("age_days") or 0),
        "tlsVersion": _tls_version_to_code(features.get("tls", {}).get("version")),
        "hasCSP": "content-security-policy" in header_keys,
        "hasHSTS": "strict-transport-security" in header_keys,
        "hasForms": int(features.get("html", {}).get("forms_count") or 0) > 0,
        "isCloudflare": "cloudflare" in server_header or "cloudflare" in header_values_blob,
        "isWordPress": "wordpress" in technologies,
    }


def _decode_grade(raw_grade: Any) -> str:
    if isinstance(raw_grade, str):
        return raw_grade or "D"
    if isinstance(raw_grade, (bytes, bytearray)):
        decoded = bytes(raw_grade).decode("utf-8", errors="ignore").strip("\x00")
        return decoded or "D"
    return "D"


def _load_artifacts() -> Dict[str, Any]:
    if not ARTIFACTS_FILE.exists():
        raise FileNotFoundError(f"Artifacts file not found at {ARTIFACTS_FILE}")

    artifacts = json.loads(ARTIFACTS_FILE.read_text(encoding="utf-8"))
    address = artifacts.get("address")
    abi = artifacts.get("abi")

    if not address or not abi:
        raise RuntimeError("Contract artifacts are missing address or ABI. Run deploy.py first.")

    return artifacts


def _resolve_signing_account(web3: Web3) -> tuple[str, str]:
    private_key = os.getenv("PRIVATE_KEY")
    if not private_key:
        raise RuntimeError("PRIVATE_KEY is required to sign blockchain transactions")

    derived_signer = web3.eth.account.from_key(private_key).address
    address = (
        os.getenv("ACCOUNT_ADDRESS")
    )
    if address:
        checksum_address = Web3.to_checksum_address(address)
        if checksum_address != Web3.to_checksum_address(derived_signer):
            logger.warning(
                "[BC-DEBUG] ACCOUNT_ADDRESS does not match PRIVATE_KEY derived address. configured=%s derived=%s",
                checksum_address,
                derived_signer,
            )
    else:
        checksum_address = Web3.to_checksum_address(derived_signer)

    return checksum_address, private_key


def _resolve_mode_a_account(web3: Web3) -> str:
    accounts = web3.eth.accounts
    if not accounts:
        raise RuntimeError("MODE A selected but Ganache has no unlocked accounts")
    return Web3.to_checksum_address(accounts[0])


def _decode_status(receipt: Any) -> int:
    return int(getattr(receipt, "status", 0) or 0)


def _blockchain_score(domain: str, chain_features: Dict[str, Any]) -> Dict[str, Any]:
    artifacts = _load_artifacts()
    rpc_url = os.getenv("GANACHE_RPC_URL", artifacts.get("provider") or DEFAULT_RPC_URL)

    web3 = Web3(HTTPProvider(rpc_url))
    if not web3.is_connected():
        raise RuntimeError(f"Unable to connect to Ganache at {rpc_url}")

    logger.info("[BC-DEBUG] Connected to RPC provider: %s", rpc_url)
    logger.info("[BC-DEBUG] Active chain_id: %s", web3.eth.chain_id)

    mode_info = check_execution_mode(web3)
    mode = mode_info["mode"]

    contract_address = Web3.to_checksum_address(artifacts["address"])
    contract_code = web3.eth.get_code(contract_address)
    if not contract_code or contract_code == b"" or contract_code.hex() == "0x":
        raise RuntimeError(f"Invalid contract address or empty code at {contract_address}")

    contract = web3.eth.contract(address=contract_address, abi=artifacts["abi"])
    logger.info("[BC-DEBUG] Contract address verified: %s", contract_address)

    private_key = ""
    if mode == "B":
        sender, private_key = _resolve_signing_account(web3)
    else:
        sender = _resolve_mode_a_account(web3)

    if os.getenv("DEBUG", "false").lower() == "true":
        logger.debug("[BC-DEBUG] Full feature payload for %s: %s", domain, chain_features)

    logger.info("[BC-DEBUG] Contract method: calculateScore")
    contract_function = contract.functions.calculateScore(
        domain,
        chain_features["domainAgeDays"],
        chain_features["tlsVersion"],
        chain_features["hasCSP"],
        chain_features["hasHSTS"],
        chain_features["hasForms"],
        chain_features["isCloudflare"],
        chain_features["isWordPress"],
    )

    tx_params = {"from": sender}
    try:
        tx_params["gas"] = contract_function.estimate_gas({"from": sender})
    except Exception:
        tx_params["gas"] = 500000

    try:
        tx_params["gasPrice"] = web3.eth.gas_price
    except Exception:
        tx_params["gasPrice"] = web3.to_wei("2", "gwei")

    logger.info("Submitting scoring transaction for %s using account %s", domain, sender)

    if mode == "A":
        logger.info("USING TRANSACT -> TX WILL BE MINED IN GANACHE")
        logger.info("[BC-DEBUG] TX lifecycle step: send tx")
        tx_hash = contract_function.transact(tx_params)
    else:
        logger.info("PRIVATE KEY MODE ACTIVE -> SIGNED TRANSACTION FLOW ENABLED")
        nonce = web3.eth.get_transaction_count(sender)
        tx_params["nonce"] = nonce
        tx_params["chainId"] = web3.eth.chain_id
        logger.info("USING TRANSACT -> TX WILL BE MINED IN GANACHE")
        logger.info("[BC-DEBUG] TX lifecycle step: build tx")
        built_tx = contract_function.build_transaction(tx_params)
        logger.info("[BC-DEBUG] TX lifecycle step: sign tx")
        signed_tx = web3.eth.account.sign_transaction(built_tx, private_key)
        logger.info("[BC-DEBUG] TX lifecycle step: send tx")
        tx_hash = web3.eth.send_raw_transaction(signed_tx.raw_transaction)

    logger.info("Scoring tx submitted: %s", tx_hash.hex())
    logger.info("[BC-DEBUG] TX lifecycle step: receipt wait")
    receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
    status = _decode_status(receipt)
    logger.info("[BC-DEBUG] tx_hash=%s", receipt.transactionHash.hex())
    logger.info("[BC-DEBUG] blockNumber=%s", receipt.blockNumber)
    logger.info("[BC-DEBUG] gasUsed=%s", receipt.gasUsed)
    logger.info("[BC-DEBUG] status=%s", status)
    if status == 0:
        logger.error("TRANSACTION FAILED ON EVM")
        raise RuntimeError("Transaction reverted on EVM")

    logger.error("USING CALL -> NO BLOCKCHAIN TRANSACTION GENERATED")
    on_chain_score, on_chain_grade, _, _ = contract.functions.getLatestScore(domain).call()
    grade = _decode_grade(on_chain_grade)

    logger.info(
        "On-chain score resolved for %s: score=%s grade=%s tx=%s block=%s gas=%s",
        domain,
        on_chain_score,
        grade,
        receipt.transactionHash.hex(),
        receipt.blockNumber,
        receipt.gasUsed,
    )

    return {
        "blockchain_score": int(on_chain_score),
        "grade": grade,
        "tx_hash": receipt.transactionHash.hex(),
        "block_number": int(receipt.blockNumber),
        "gas_used": int(receipt.gasUsed),
        "status": status,
        "chain_used": True,
        "flags": [],
    }


def score_with_blockchain(domain: str, features: Dict[str, Any]) -> Dict[str, Any]:
    chain_features = _extract_blockchain_features(features)

    try:
        result = _blockchain_score(domain, chain_features)
    except (FileNotFoundError, json.JSONDecodeError, RuntimeError) as error:
        message = str(error) or "blockchain_not_configured"
        logger.warning(
            "BLOCKCHAIN DISABLED -> USING LOCAL SCORING | domain=%s | reason=%s",
            domain,
            message,
        )
        fallback = score_features(features)
        result = {
            "blockchain_score": int(fallback.get("score", 50)),
            "score": int(fallback.get("score", 50)),
            "grade": fallback.get("grade", "C"),
            "tx_hash": None,
            "block_number": None,
            "gas_used": None,
            "status": None,
            "chain_used": False,
            "flags": fallback.get("flags", ["scoring_error"]),
            "fallback_reason": message,
        }
    except Exception as error:
        logger.exception("BLOCKCHAIN FAILED -> USING LOCAL SCORING FALLBACK | domain=%s | reason=%s", domain, error)
        fallback = score_features(features)
        result = {
            "blockchain_score": int(fallback.get("score", 50)),
            "score": int(fallback.get("score", 50)),
            "grade": fallback.get("grade", "C"),
            "tx_hash": None,
            "block_number": None,
            "gas_used": None,
            "status": None,
            "chain_used": False,
            "flags": fallback.get("flags", ["scoring_error"]),
            "fallback_reason": str(error) or "blockchain_error",
        }

    if "score" not in result:
        result["score"] = int(result.get("blockchain_score", 50))
    result["features_used"] = chain_features
    return result
