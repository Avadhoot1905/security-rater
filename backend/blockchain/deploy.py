from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv
from solcx import compile_standard, install_solc, set_solc_version
from web3 import HTTPProvider, Web3

from blockchain.account_validator import build_web3, validate_account
from blockchain.refuel import refuel_account


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(filename)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
CONTRACT_FILE = BASE_DIR / "SecurityScore.sol"
ARTIFACTS_FILE = BASE_DIR / "artifacts.json"
DEFAULT_RPC_URL = "http://127.0.0.1:7545"
DEFAULT_SOLC_VERSION = "0.8.19"
DEPLOYMENT_BALANCE_THRESHOLD_ETH = 0.5
DEFAULT_REFUEL_AMOUNT_ETH = 10.0

load_dotenv(BASE_DIR.parent / ".env")


def _extract_pragma_version(source_code: str) -> str:
    pragma_match = re.search(r"pragma\s+solidity\s+([^;]+);", source_code)
    if not pragma_match:
        raise RuntimeError("Solidity pragma not found")
    return pragma_match.group(1).strip()


def _ensure_compiler_compatibility(source_code: str, solc_version: str) -> str:
    pragma_version = _extract_pragma_version(source_code)
    if "0.8.19" not in pragma_version:
        logger.error("Solidity pragma/compiler mismatch")
        logger.error("Contract: %s", pragma_version)
        logger.error("Compiler: %s", solc_version)
        raise RuntimeError("Solidity pragma/compiler mismatch")
    return pragma_version


def compile_contract(solc_version: str) -> Dict[str, Any]:
    logger.info("Compiling Solidity contract from %s with solc %s", CONTRACT_FILE, solc_version)
    install_solc(solc_version)
    set_solc_version(solc_version)

    source_code = CONTRACT_FILE.read_text(encoding="utf-8")
    pragma_version = _ensure_compiler_compatibility(source_code, solc_version)
    logger.info("Detected pragma: %s", pragma_version)
    logger.info("Using solc: %s", solc_version)
    logger.info("Target EVM: paris")
    logger.info("Updated Solidity version alignment")
    compiled = compile_standard(
        {
            "language": "Solidity",
            "sources": {
                "SecurityScore.sol": {
                    "content": source_code,
                }
            },
            "settings": {
                "optimizer": {"enabled": True, "runs": 200},
                "evmVersion": "paris",
                "outputSelection": {
                    "*": {
                        "*": ["abi", "evm.bytecode.object"],
                    }
                },
            },
        },
        solc_version=solc_version,
    )

    contract_data = compiled["contracts"]["SecurityScore.sol"]["SecurityScore"]
    abi = contract_data["abi"]
    bytecode = contract_data["evm"]["bytecode"]["object"]

    if not isinstance(abi, list):
        raise RuntimeError("Malformed ABI")
    if not bytecode:
        raise RuntimeError("Compiled bytecode is empty")

    logger.info("Contract compiled successfully")
    return {"abi": abi, "bytecode": bytecode}


def _get_constructor_abi(abi: Any) -> Dict[str, Any] | None:
    constructor_entries = [entry for entry in abi if isinstance(entry, dict) and entry.get("type") == "constructor"]
    if len(constructor_entries) > 1:
        raise RuntimeError("Malformed ABI: multiple constructors declared")
    return constructor_entries[0] if constructor_entries else None


def _validate_deployment_artifacts(abi: Any, bytecode: str) -> list[Any]:
    if not isinstance(abi, list) or not abi:
        raise RuntimeError("Malformed ABI")
    if not isinstance(bytecode, str) or not bytecode.strip():
        raise RuntimeError("Compiled bytecode is empty")

    constructor_abi = _get_constructor_abi(abi)
    if constructor_abi and not isinstance(constructor_abi.get("inputs", []), list):
        raise RuntimeError("Malformed ABI: constructor inputs are invalid")

    constructor_args: list[Any] = []
    if constructor_abi:
        constructor_inputs = constructor_abi.get("inputs", [])
        if len(constructor_inputs) != len(constructor_args):
            raise RuntimeError("Constructor parameter mismatch")

    return constructor_args


def _build_fee_params(web3: Web3) -> Dict[str, Any]:
    latest_block = web3.eth.get_block("latest")
    base_fee = latest_block.get("baseFeePerGas")
    if base_fee is None:
        legacy_gas_price = web3.eth.gas_price
        logger.info("Using legacy gas pricing")
        logger.info("Legacy gas price: %s", legacy_gas_price)
        return {"gasPrice": legacy_gas_price}

    priority_fee = web3.to_wei(2, "gwei")
    max_fee = int(base_fee + (priority_fee * 2))
    logger.info("Base fee: %s", base_fee)
    logger.info("Priority fee: %s", priority_fee)
    logger.info("Max fee: %s", max_fee)
    return {
        "maxFeePerGas": max_fee,
        "maxPriorityFeePerGas": priority_fee,
    }


def deploy_contract(web3: Web3, rpc_url: str, abi: Any, bytecode: str, account_info: Dict[str, Any]) -> Dict[str, Any]:
    logger.info("Deploying contract to Ganache at %s", rpc_url)
    if not web3.is_connected():
        raise RuntimeError(f"Unable to connect to Ganache at {rpc_url}")

    client_version = getattr(web3, "client_version", None)
    logger.info("Chain ID: %s", web3.eth.chain_id)
    logger.info("Client version: %s", client_version or "unknown")

    sender = Web3.to_checksum_address(account_info["sender"])
    private_key = account_info.get("private_key")
    mode = account_info.get("mode", "A")
    logger.info("Using deployer account: %s", sender)
    logger.info("Transaction mode: %s", mode)
    logger.info("Deployment wallet balance: %s ETH", account_info.get("deployment_balance_eth"))

    constructor_args = _validate_deployment_artifacts(abi, bytecode)
    logger.info("Bytecode size: %s bytes", len(bytecode) // 2)
    logger.info("Constructor arguments: %s", constructor_args)

    contract = web3.eth.contract(abi=abi, bytecode=bytecode)
    constructor = contract.constructor(*constructor_args)
    try:
        logger.info("Dry run gas estimate starting")
        dry_run_gas = constructor.estimate_gas({"from": sender})
        logger.info("Dry run gas estimate: %s", dry_run_gas)
    except Exception as error:
        logger.error("Deployment failed due to EVM compatibility issue")
        logger.error("Gas estimation failed: %s", error)
        logger.error("Suggested actions: downgrade compiler, update Ganache, verify hardfork")
        raise RuntimeError("Deployment failed due to EVM compatibility issue") from error

    gas_estimate = int(dry_run_gas * 1.2)
    fee_params = _build_fee_params(web3)
    logger.info("Gas estimate: %s", dry_run_gas)
    logger.info("Final gas limit: %s", gas_estimate)

    constructor_tx = constructor.build_transaction(
        {
            "from": sender,
            "nonce": web3.eth.get_transaction_count(sender),
            "chainId": web3.eth.chain_id,
            **fee_params,
            "gas": gas_estimate,
        }
    )
    logger.info("Final tx object: %s", constructor_tx)

    if mode == "B" and private_key:
        signed_tx = web3.eth.account.sign_transaction(constructor_tx, private_key)
        tx_hash = web3.eth.send_raw_transaction(signed_tx.raw_transaction)
    else:
        tx_hash = web3.eth.send_transaction(constructor_tx)
    logger.info("Deployment transaction submitted: %s", tx_hash.hex())

    receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
    logger.info(
        "Contract deployed at %s | tx=%s | block=%s | gas_used=%s",
        receipt.contractAddress,
        receipt.transactionHash.hex(),
        receipt.blockNumber,
        receipt.gasUsed,
    )

    return {
        "address": receipt.contractAddress,
        "tx_hash": receipt.transactionHash.hex(),
        "block_number": receipt.blockNumber,
        "gas_used": receipt.gasUsed,
        "chain_id": web3.eth.chain_id,
        "deployer": sender,
    }


def write_artifacts(rpc_url: str, abi: Any, deployment: Dict[str, Any]) -> None:
    artifacts = {
        "address": deployment["address"],
        "abi": abi,
        "network": "ganache",
        "provider": rpc_url,
        "chain_id": deployment["chain_id"],
        "deployment_tx_hash": deployment["tx_hash"],
        "deployment_block_number": deployment["block_number"],
        "deployment_gas_used": deployment["gas_used"],
        "deployer": deployment["deployer"],
    }

    ARTIFACTS_FILE.write_text(json.dumps(artifacts, indent=2), encoding="utf-8")
    logger.info("Artifacts saved to %s", ARTIFACTS_FILE)


def main() -> None:
    web3, rpc_url = build_web3(os.getenv("GANACHE_URL") or os.getenv("GANACHE_RPC_URL") or DEFAULT_RPC_URL)
    solc_version = os.getenv("SOLC_VERSION", DEFAULT_SOLC_VERSION)

    logger.info("Chain: %s", web3.eth.chain_id)
    logger.info("Client version: %s", getattr(web3, "client_version", "unknown"))

    compiled = compile_contract(solc_version)
    try:
        account_info = validate_account(
            minimum_balance_eth=DEPLOYMENT_BALANCE_THRESHOLD_ETH,
            explicit_url=rpc_url,
            web3=web3,
        )
    except RuntimeError as error:
        if str(error) == "Balance insufficient":
            logger.warning("Deployment wallet below threshold. Triggering local refuel before retry.")
            refuel_account(amount_eth=DEFAULT_REFUEL_AMOUNT_ETH, explicit_url=rpc_url)
            account_info = validate_account(
                minimum_balance_eth=DEPLOYMENT_BALANCE_THRESHOLD_ETH,
                explicit_url=rpc_url,
                web3=web3,
            )
        else:
            raise

    deployment = deploy_contract(web3, rpc_url, compiled["abi"], compiled["bytecode"], account_info)
    write_artifacts(rpc_url, compiled["abi"], deployment)

    logger.info("Deployment complete")
    print(f"Contract Address: {deployment['address']}")


if __name__ == "__main__":
    main()
