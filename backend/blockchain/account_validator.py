from __future__ import annotations

import logging
import os
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from web3 import HTTPProvider, Web3


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(filename)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_RPC_URL = "http://127.0.0.1:7545"

load_dotenv(BASE_DIR.parent / ".env")


def resolve_rpc_url(explicit_url: Optional[str] = None) -> str:
    return (
        explicit_url
        or os.getenv("GANACHE_URL")
        or os.getenv("GANACHE_RPC_URL")
        or DEFAULT_RPC_URL
    )


def build_web3(explicit_url: Optional[str] = None) -> tuple[Web3, str]:
    rpc_url = resolve_rpc_url(explicit_url)
    return Web3(HTTPProvider(rpc_url)), rpc_url


def _checksum_or_none(value: str | None) -> str | None:
    if not value:
        return None
    return Web3.to_checksum_address(value)


def _format_eth(web3: Web3, balance_wei: int) -> str:
    return str(web3.from_wei(balance_wei, "ether"))


def get_available_accounts(web3: Web3) -> list[str]:
    return [Web3.to_checksum_address(account) for account in web3.eth.accounts]


def resolve_deployment_account(web3: Web3) -> Dict[str, Any]:
    accounts = get_available_accounts(web3)
    configured_account = _checksum_or_none(os.getenv("ACCOUNT_ADDRESS", "").strip())
    private_key = os.getenv("PRIVATE_KEY", "").strip()

    if private_key:
        derived_account = Web3.to_checksum_address(web3.eth.account.from_key(private_key).address)
        if configured_account and configured_account != derived_account:
            raise RuntimeError("Private key mismatch")
        if derived_account not in accounts:
            raise RuntimeError("Account not found in Ganache")
        return {
            "mode": "B",
            "deployment_account": derived_account,
            "configured_account": configured_account or derived_account,
            "private_key": private_key,
            "sender": derived_account,
            "private_key_configured": True,
        }

    if not accounts:
        raise RuntimeError("No Ganache accounts available")

    deployment_account = accounts[0]
    if configured_account:
        if configured_account not in accounts:
            logger.error("Account not found in Ganache")
            print("Account not found in Ganache")
            configured_account = None
        elif configured_account != deployment_account:
            logger.warning(
                "Configured account differs from auto-selected unlocked account. configured=%s selected=%s",
                configured_account,
                deployment_account,
            )

    return {
        "mode": "A",
        "deployment_account": deployment_account,
        "configured_account": configured_account,
        "private_key": None,
        "sender": deployment_account,
        "private_key_configured": False,
    }


def validate_account(
    minimum_balance_eth: float = 0.0,
    explicit_url: Optional[str] = None,
    web3: Optional[Web3] = None,
) -> Dict[str, Any]:
    active_web3 = web3
    rpc_url = resolve_rpc_url(explicit_url)
    if active_web3 is None:
        active_web3 = Web3(HTTPProvider(rpc_url))

    if not active_web3.is_connected():
        raise RuntimeError(f"Unable to connect to Ganache at {rpc_url}")

    accounts = get_available_accounts(active_web3)
    chain_id = int(active_web3.eth.chain_id)
    account_info = resolve_deployment_account(active_web3)
    deployment_account = account_info["deployment_account"]
    configured_account = account_info.get("configured_account")

    balance_wei = int(active_web3.eth.get_balance(deployment_account))
    balance_eth = _format_eth(active_web3, balance_wei)
    configured_balance_wei = None
    configured_balance_eth = None
    if configured_account and configured_account != deployment_account:
        configured_balance_wei = int(active_web3.eth.get_balance(configured_account))
        configured_balance_eth = _format_eth(active_web3, configured_balance_wei)

    print(f"Chain ID: {chain_id}")
    print(f"Configured account: {configured_account or 'not set'}")
    print(f"Deployment account: {deployment_account}")
    print(f"Available Ganache accounts: {accounts}")
    print(f"Deployment balance: {balance_eth} ETH")
    if configured_balance_eth is not None:
        print(f"Configured account balance: {configured_balance_eth} ETH")

    logger.info("[BC-DEBUG] Chain ID: %s", chain_id)
    logger.info("[BC-DEBUG] Configured account: %s", configured_account or "not set")
    logger.info("[BC-DEBUG] Deployment account: %s", deployment_account)
    logger.info("[BC-DEBUG] Available Ganache accounts: %s", accounts)
    logger.info("[BC-DEBUG] Deployment balance: %s ETH", balance_eth)

    required_balance_wei = active_web3.to_wei(Decimal(str(minimum_balance_eth)), "ether")
    if balance_wei < required_balance_wei:
        raise RuntimeError("Balance insufficient")

    print("Configured account verified")
    logger.info("Configured account verified")

    return {
        "chain_id": chain_id,
        "rpc_url": rpc_url,
        "accounts": accounts,
        "deployment_account": deployment_account,
        "configured_account": configured_account,
        "deployment_balance_wei": balance_wei,
        "deployment_balance_eth": balance_eth,
        "configured_balance_wei": configured_balance_wei,
        "configured_balance_eth": configured_balance_eth,
        "private_key": account_info.get("private_key"),
        "mode": account_info["mode"],
        "private_key_configured": account_info["private_key_configured"],
        "sender": account_info["sender"],
    }
