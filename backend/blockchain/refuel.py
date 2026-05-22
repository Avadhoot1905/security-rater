from __future__ import annotations

import argparse
import logging
from decimal import Decimal
from typing import Any, Dict, Optional

from web3 import Web3

from blockchain.account_validator import build_web3, get_available_accounts, resolve_deployment_account


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(filename)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def _eth_to_wei(web3: Web3, amount_eth: float) -> int:
    return int(web3.to_wei(Decimal(str(amount_eth)), "ether"))


def _wei_to_eth(web3: Web3, amount_wei: int) -> str:
    return str(web3.from_wei(amount_wei, "ether"))


def _estimate_transfer_gas(web3: Web3, sender: str, recipient: str, value_wei: int) -> int:
    try:
        return int(
            web3.eth.estimate_gas(
                {
                    "from": sender,
                    "to": recipient,
                    "value": value_wei,
                }
            )
        )
    except Exception:
        return 21000


def _select_source_account(web3: Web3, destination: str) -> str:
    accounts = get_available_accounts(web3)
    if not accounts:
        raise RuntimeError("No Ganache accounts available")

    source_candidates = [account for account in accounts if account != destination]
    if not source_candidates:
        raise RuntimeError("No funded Ganache account available for refuel")

    richest_account = max(source_candidates, key=lambda account: web3.eth.get_balance(account))
    return richest_account


def refuel_account(amount_eth: float = 10.0, explicit_url: Optional[str] = None) -> Dict[str, Any]:
    web3, rpc_url = build_web3(explicit_url)
    if not web3.is_connected():
        raise RuntimeError(f"Unable to connect to Ganache at {rpc_url}")

    account_info = resolve_deployment_account(web3)
    destination = account_info["deployment_account"]
    source = _select_source_account(web3, destination)
    source_balance_wei = int(web3.eth.get_balance(source))
    destination_balance_before_wei = int(web3.eth.get_balance(destination))
    transfer_value_wei = _eth_to_wei(web3, amount_eth)
    gas_price_wei = int(web3.eth.gas_price)
    gas_limit = _estimate_transfer_gas(web3, source, destination, transfer_value_wei)
    gas_cost_wei = gas_limit * gas_price_wei

    logger.info("[BC-DEBUG] Refuel source selected: %s", source)
    logger.info("[BC-DEBUG] Refuel destination selected: %s", destination)
    logger.info("[BC-DEBUG] Source balance: %s ETH", _wei_to_eth(web3, source_balance_wei))
    logger.info("[BC-DEBUG] Destination balance before: %s ETH", _wei_to_eth(web3, destination_balance_before_wei))
    logger.info("[BC-DEBUG] Estimated gas: %s", gas_limit)
    logger.info("[BC-DEBUG] Estimated gas cost: %s ETH", _wei_to_eth(web3, gas_cost_wei))

    if source_balance_wei < transfer_value_wei + gas_cost_wei:
        raise RuntimeError("Sender lacks funds")

    tx_common = {
        "from": source,
        "to": destination,
        "value": transfer_value_wei,
        "gas": gas_limit,
        "gasPrice": gas_price_wei,
    }

    private_key = account_info.get("private_key")
    source_private_key = None
    if private_key:
        derived_account = Web3.to_checksum_address(web3.eth.account.from_key(private_key).address)
        if derived_account == source:
            source_private_key = private_key

    if source_private_key:
        nonce = web3.eth.get_transaction_count(source)
        tx = {**tx_common, "nonce": nonce, "chainId": web3.eth.chain_id}
        signed_tx = web3.eth.account.sign_transaction(tx, source_private_key)
        tx_hash = web3.eth.send_raw_transaction(signed_tx.raw_transaction)
        tx_mode = "private_key"
    else:
        tx_hash = web3.eth.send_transaction(tx_common)
        tx_mode = "unlocked_account"

    receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
    status = int(getattr(receipt, "status", 0) or 0)
    destination_balance_after_wei = int(web3.eth.get_balance(destination))

    print(f"Refueled: {destination}")
    print(f"Amount: {amount_eth} ETH")
    print(f"New balance: {_wei_to_eth(web3, destination_balance_after_wei)} ETH")
    print(f"tx_hash: {tx_hash.hex()}")
    print(f"gas_used: {receipt.gasUsed}")
    print(f"block_number: {receipt.blockNumber}")
    print(f"status: {status}")
    print(f"Before balance: {_wei_to_eth(web3, destination_balance_before_wei)} ETH")
    print(f"After balance: {_wei_to_eth(web3, destination_balance_after_wei)} ETH")

    logger.info("Refueled: %s", destination)
    logger.info("Amount: %s ETH", amount_eth)
    logger.info("New balance: %s ETH", _wei_to_eth(web3, destination_balance_after_wei))
    logger.info("tx_hash: %s", tx_hash.hex())
    logger.info("gas_used: %s", receipt.gasUsed)
    logger.info("block_number: %s", receipt.blockNumber)
    logger.info("status: %s", status)

    return {
        "source": source,
        "destination": destination,
        "amount_eth": amount_eth,
        "tx_hash": tx_hash.hex(),
        "gas_used": int(receipt.gasUsed),
        "block_number": int(receipt.blockNumber),
        "status": status,
        "before_balance_wei": destination_balance_before_wei,
        "after_balance_wei": destination_balance_after_wei,
        "before_balance_eth": _wei_to_eth(web3, destination_balance_before_wei),
        "after_balance_eth": _wei_to_eth(web3, destination_balance_after_wei),
        "tx_mode": tx_mode,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Refuel the configured Ganache deployment account")
    parser.add_argument("--amount", type=float, default=10.0, help="ETH to transfer to the deployment account")
    parser.add_argument("--rpc-url", default=None, help="Optional Ganache RPC URL override")
    args = parser.parse_args()

    refuel_account(amount_eth=args.amount, explicit_url=args.rpc_url)


if __name__ == "__main__":
    main()
