from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from web3 import HTTPProvider, Web3

from utils.logger import get_logger


logger = get_logger(__name__)

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_RPC_URL = "http://127.0.0.1:7545"

load_dotenv(BASE_DIR.parent / ".env")


def _resolve_rpc_url(explicit_url: Optional[str] = None) -> str:
    return explicit_url or os.getenv("GANACHE_RPC_URL") or DEFAULT_RPC_URL


def _build_web3(explicit_url: Optional[str] = None) -> tuple[Web3, str]:
    rpc_url = _resolve_rpc_url(explicit_url)
    return Web3(HTTPProvider(rpc_url)), rpc_url


def check_web3_connection(explicit_url: Optional[str] = None) -> Dict[str, Any]:
    web3, rpc_url = _build_web3(explicit_url)
    is_connected = web3.is_connected()

    logger.info("[BC-DEBUG] Provider URL: %s", rpc_url)
    if not is_connected:
        logger.error("[BC-DEBUG] Web3 connection status: DISCONNECTED")
        logger.warning("[BC-DEBUG] Wrong or unreachable provider URL. Expected default: %s", DEFAULT_RPC_URL)
        return {
            "provider_url": rpc_url,
            "connected": False,
            "chain_id": None,
        }

    chain_id = web3.eth.chain_id
    logger.info("[BC-DEBUG] Web3 connection status: CONNECTED")
    logger.info("[BC-DEBUG] Chain ID: %s", chain_id)
    return {
        "provider_url": rpc_url,
        "connected": True,
        "chain_id": int(chain_id),
    }


def check_execution_mode(web3: Optional[Web3] = None) -> Dict[str, Any]:
    active_web3 = web3
    if active_web3 is None:
        active_web3, _ = _build_web3()

    private_key = os.getenv("PRIVATE_KEY", "").strip()
    if private_key:
        derived_signer = active_web3.eth.account.from_key(private_key).address
        signer = derived_signer
        account_address = os.getenv("ACCOUNT_ADDRESS", "").strip()
        if account_address:
            signer = Web3.to_checksum_address(account_address)
            if signer != Web3.to_checksum_address(derived_signer):
                logger.warning(
                    "[BC-DEBUG] ACCOUNT_ADDRESS does not match PRIVATE_KEY derived address. configured=%s derived=%s",
                    signer,
                    derived_signer,
                )
        logger.info("[BC-DEBUG] Execution mode: MODE B (PRIVATE KEY MODE via .env)")
        logger.info("PRIVATE KEY MODE ACTIVE -> SIGNED TRANSACTION FLOW ENABLED")
        return {
            "mode": "B",
            "mode_name": "private_key",
            "signer": signer,
            "derived_signer": Web3.to_checksum_address(derived_signer),
            "private_key_configured": True,
        }

    accounts = active_web3.eth.accounts
    signer = accounts[0] if accounts else None
    logger.info("[BC-DEBUG] Execution mode: MODE A (Ganache unlocked accounts)")
    if signer:
        logger.info("[BC-DEBUG] Auto-selected unlocked account: %s", signer)
    else:
        logger.error("[BC-DEBUG] MODE A selected but no Ganache unlocked accounts are available")
    return {
        "mode": "A",
        "mode_name": "ganache_unlocked",
        "signer": signer,
        "private_key_configured": False,
    }


def check_accounts(web3: Optional[Web3] = None) -> Dict[str, Any]:
    active_web3 = web3
    if active_web3 is None:
        active_web3, _ = _build_web3()

    accounts = [str(account) for account in active_web3.eth.accounts]
    logger.info("[BC-DEBUG] Available accounts (%d): %s", len(accounts), accounts)
    return {
        "accounts": accounts,
        "count": len(accounts),
    }


def check_balance(web3: Optional[Web3] = None) -> Dict[str, Any]:
    active_web3 = web3
    if active_web3 is None:
        active_web3, _ = _build_web3()

    mode_info = check_execution_mode(active_web3)
    account = mode_info.get("signer")
    if not account:
        raise RuntimeError("No account available for balance check")

    balance_wei = active_web3.eth.get_balance(account)
    balance_eth = active_web3.from_wei(balance_wei, "ether")
    logger.info("[BC-DEBUG] Balance for %s: %s wei (%s ETH)", account, balance_wei, balance_eth)
    return {
        "account": account,
        "balance_wei": int(balance_wei),
        "balance_eth": str(balance_eth),
    }


def send_test_transaction(web3: Optional[Web3] = None) -> Dict[str, Any]:
    active_web3 = web3
    if active_web3 is None:
        active_web3, _ = _build_web3()

    mode_info = check_execution_mode(active_web3)
    mode = mode_info["mode"]
    accounts = active_web3.eth.accounts
    if len(accounts) < 2:
        raise RuntimeError("At least two Ganache accounts are required to run send_test_transaction")

    sender = Web3.to_checksum_address(mode_info.get("signer") or accounts[0])
    receiver = Web3.to_checksum_address(accounts[1])
    gas_price = active_web3.eth.gas_price

    logger.info("[BC-DEBUG] Sending test transaction from %s to %s", sender, receiver)

    if mode == "A":
        tx_hash = active_web3.eth.send_transaction(
            {
                "from": sender,
                "to": receiver,
                "value": 1,
                "gas": 21000,
                "gasPrice": gas_price,
            }
        )
    else:
        private_key = os.getenv("PRIVATE_KEY", "").strip()
        if not private_key:
            raise RuntimeError("PRIVATE_KEY must be set in MODE B")

        nonce = active_web3.eth.get_transaction_count(sender)
        tx = {
            "from": sender,
            "to": receiver,
            "value": 1,
            "nonce": nonce,
            "gas": 21000,
            "gasPrice": gas_price,
            "chainId": active_web3.eth.chain_id,
        }
        signed_tx = active_web3.eth.account.sign_transaction(tx, private_key)
        tx_hash = active_web3.eth.send_raw_transaction(signed_tx.raw_transaction)

    receipt = active_web3.eth.wait_for_transaction_receipt(tx_hash)
    tx_hash_hex = tx_hash.hex()
    status = int(receipt.status)

    logger.info("[BC-DEBUG] Test transaction tx_hash=%s", tx_hash_hex)
    logger.info("[BC-DEBUG] Test transaction blockNumber=%s", receipt.blockNumber)
    logger.info("[BC-DEBUG] Test transaction gasUsed=%s", receipt.gasUsed)
    logger.info("[BC-DEBUG] Test transaction status=%s", status)
    if status == 0:
        logger.error("TRANSACTION FAILED ON EVM")

    return {
        "mode": mode,
        "from": sender,
        "to": receiver,
        "tx_hash": tx_hash_hex,
        "block_number": int(receipt.blockNumber),
        "gas_used": int(receipt.gasUsed),
        "status": status,
    }
