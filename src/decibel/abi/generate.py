from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aptos_sdk.account_address import AccountAddress
from aptos_sdk.async_client import RestClient

from decibel._constants import (
    MAINNET_CONFIG,
    NAMED_CONFIGS,
    TESTNET_CONFIG,
    DecibelConfig,
)

logger = logging.getLogger(__name__)


def _setup_cli_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
    )


TESTNET_SDK_MODULES = ["usdc"]

#: Modules published under ``deployment.package``.
SDK_MODULES = [
    "admin_apis",
    "public_apis",
    "dex_accounts",
    "dex_accounts_entry",
    "dex_accounts_spot_entry",
    "dex_accounts_vault_extension",
    "perp_engine",
    "spot_admin_apis",
    "spot_engine",
    "spot_market_escrow",
    "spot_order_public_api",
    "spot_order_read_apis",
    "vault",
    "vault_api",
]

#: Campaign / funded-first-trade modules, published under ``deployment.campaign_package``.
#:
#: These live in a separate package, so their function ids carry a different address prefix than
#: everything in :data:`SDK_MODULES`. Deployments without a campaign package skip them entirely; on
#: a network where one of these modules isn't deployed yet the fetch lands in ``errors[]``.
CAMPAIGN_MODULES = [
    "campaign_manager",
    "funded_first_trade",
    "protected_trial",
]


def get_abi_filename(config: DecibelConfig) -> str:
    if config == TESTNET_CONFIG:
        return "testnet.json"
    elif config == MAINNET_CONFIG:
        return "mainnet.json"
    else:
        return f"{config.network.value}.json"


def _module_targets(config: DecibelConfig) -> list[tuple[str, str]]:
    """``(package, module)`` pairs to fetch, in output order."""
    modules = TESTNET_SDK_MODULES + SDK_MODULES if config == TESTNET_CONFIG else SDK_MODULES
    targets = [(config.deployment.package, module) for module in modules]

    campaign_package = config.deployment.campaign_package
    if campaign_package:
        targets += [(campaign_package, module) for module in CAMPAIGN_MODULES]
    else:
        logger.info(
            "No campaign package configured for %s; skipping %s",
            config.network.value,
            ", ".join(CAMPAIGN_MODULES),
        )

    return targets


async def fetch_all_abis(config: DecibelConfig) -> None:
    logger.info("Fetching ABIs for Decibel SDK functions...")
    logger.info("Package: %s", config.deployment.package)
    logger.info("Campaign package: %s", config.deployment.campaign_package or "(none)")
    logger.info("Network: %s", config.network.value)
    logger.info("Fullnode: %s", config.fullnode_url)
    logger.info("")

    if not config.deployment.package or not config.fullnode_url:
        logger.error("Error: config.package or config.fullnode_url is not set")
        sys.exit(1)

    client = RestClient(config.fullnode_url)
    abis: dict[str, dict[str, Any]] = {}
    errors: list[dict[str, str]] = []
    targets = _module_targets(config)

    for package, module in targets:
        try:
            logger.info("Fetching entire module: %s::%s", package, module)

            module_info: dict[str, Any] = await client.account_module(  # pyright: ignore[reportUnknownMemberType,reportUnknownVariableType]
                AccountAddress.from_str(package),
                module,
            )

            abi: dict[str, Any] | None = module_info.get("abi")
            if not abi:
                raise ValueError("Module or ABI not found")

            exposed_functions: list[dict[str, Any]] = abi.get("exposed_functions", [])
            relevant_functions: list[dict[str, Any]] = [
                f for f in exposed_functions if f.get("is_entry") or f.get("is_view")
            ]

            logger.info("Found %d exposed functions in %s", len(exposed_functions), module)
            logger.info("Keeping %d functions in %s", len(relevant_functions), module)

            for func in relevant_functions:
                function_id = f"{package}::{module}::{func['name']}"
                abis[function_id] = func

            logger.info(
                "Successfully collected %d functions from %s", len(relevant_functions), module
            )

        except Exception as e:
            error_message = str(e)
            logger.error("Error in %s: %s", module, error_message)
            errors.append({"module": module, "function": "entire_module", "error": error_message})

    await client.close()

    modules = [module for _, module in targets]

    total_functions = len(abis)
    successful = total_functions
    failed = len(errors)

    result: dict[str, Any] = {
        "packageAddress": config.deployment.package,
        "campaignPackageAddress": config.deployment.campaign_package or None,
        "network": config.network.value,
        "fullnodeUrl": config.fullnode_url,
        "fetchedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "abis": abis,
        "errors": errors,
        "summary": {
            "totalModules": len(modules),
            "totalFunctions": total_functions,
            "successful": successful,
            "failed": failed,
        },
        "modules": modules,
    }

    filename = get_abi_filename(config)
    output_path = Path(__file__).parent / "json" / filename
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)

    logger.info("")
    logger.info("Summary:")
    logger.info("  Total modules fetched: %d", len(modules))
    logger.info("  Total functions found: %d", successful)
    logger.info("  Failed modules: %d", failed)

    if errors:
        logger.info("")
        logger.info("Errors:")
        for err in errors:
            logger.info("  %s::%s: %s", err["module"], err["function"], err["error"])

    logger.info("")
    logger.info("ABIs saved to: %s", output_path)
    logger.info("")
    logger.info("ABI fetching complete!")


async def main(networks: list[str]) -> None:
    for network in networks:
        config = NAMED_CONFIGS.get(network)
        if not config:
            logger.error("Unknown network: %s", network)
            logger.error("Available networks: %s", ", ".join(NAMED_CONFIGS.keys()))
            sys.exit(1)

        try:
            await fetch_all_abis(config)
        except Exception as e:
            logger.error("Failed to fetch ABIs for %s: %s", network, e)


def cli() -> None:
    _setup_cli_logging()
    parser = argparse.ArgumentParser(
        description="Fetch ABIs from the Decibel smart contract",
        prog="python -m decibel.abi.generate",
    )
    parser.add_argument(
        "networks",
        nargs="*",
        default=["testnet"],
        help="Networks to fetch ABIs for (testnet, mainnet, all). Default: testnet",
    )

    args = parser.parse_args()

    networks: list[str] = args.networks
    if "all" in networks:
        networks = ["testnet", "mainnet"]

    asyncio.run(main(networks))


if __name__ == "__main__":
    cli()
