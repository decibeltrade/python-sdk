from __future__ import annotations

import json
import logging
import math
import secrets
from typing import TYPE_CHECKING, Any, TypeVar, cast

import httpx
from aptos_sdk.account_address import AccountAddress
from aptos_sdk.bcs import Serializer
from pydantic import BaseModel, ValidationError

if TYPE_CHECKING:
    from ._constants import CompatVersion

logger = logging.getLogger(__name__)

__all__ = [
    "FetchError",
    "bigint_reviver",
    "prettify_validation_error",
    "get_request",
    "get_request_sync",
    "post_request",
    "post_request_sync",
    "patch_request",
    "patch_request_sync",
    "get_market_addr",
    "get_primary_subaccount_addr",
    "get_trading_competition_subaccount_addr",
    "get_vault_share_address",
    "round_to_tick_size",
    "round_to_valid_price",
    "round_to_valid_order_size",
    "amount_to_chain_units",
    "chain_units_to_amount",
    "extract_vault_address_from_create_tx",
    "generate_random_replay_protection_nonce",
]

T = TypeVar("T", bound=BaseModel)


class FetchError(Exception):
    status: int
    status_text: str
    response_message: str

    def __init__(self, response_data: str, status: int, status_text: str) -> None:
        self.status = status

        try:
            parsed_data: Any = json.loads(response_data)
            parsed_status: str | None = None
            parsed_message: str | None = None

            if isinstance(parsed_data, dict):
                data_dict = cast("dict[str, Any]", parsed_data)
                status_val = data_dict.get("status")
                message_val = data_dict.get("message")
                if isinstance(status_val, str):
                    parsed_status = status_val
                if isinstance(message_val, str):
                    parsed_message = message_val

            self.status_text = parsed_status if parsed_status is not None else status_text
            self.response_message = parsed_message if parsed_message is not None else response_data
        except (json.JSONDecodeError, TypeError):
            self.status_text = status_text
            self.response_message = response_data

        formatted_status_text = f" ({self.status_text})" if self.status_text else ""
        message = f"HTTP Error {self.status}{formatted_status_text}: {self.response_message}"
        super().__init__(message)


def bigint_reviver(obj: dict[str, Any]) -> Any:
    if "$bigint" in obj and isinstance(obj["$bigint"], str):
        return int(obj["$bigint"])
    return obj


def prettify_validation_error(e: ValidationError) -> str:
    errors = e.errors()
    lines: list[str] = []
    for err in errors:
        loc = " -> ".join(str(loc) for loc in err["loc"]) if err["loc"] else "root"
        lines.append(f"  {loc}: {err['msg']}")
    return "Validation error:\n" + "\n".join(lines)


async def get_request(
    model: type[T],
    url: str,
    *,
    params: dict[str, Any] | None = None,
    api_key: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> tuple[T, int, str]:
    return await _base_request_async(
        model=model,
        url=url,
        method="GET",
        params=params,
        api_key=api_key,
        client=client,
    )


async def post_request(
    model: type[T],
    url: str,
    *,
    body: Any | None = None,
    api_key: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> tuple[T, int, str]:
    return await _base_request_async(
        model=model,
        url=url,
        method="POST",
        body=body,
        api_key=api_key,
        client=client,
    )


async def patch_request(
    model: type[T],
    url: str,
    *,
    body: Any | None = None,
    api_key: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> tuple[T, int, str]:
    return await _base_request_async(
        model=model,
        url=url,
        method="PATCH",
        body=body,
        api_key=api_key,
        client=client,
    )


def get_request_sync(
    model: type[T],
    url: str,
    *,
    params: dict[str, Any] | None = None,
    api_key: str | None = None,
    client: httpx.Client | None = None,
) -> tuple[T, int, str]:
    return _base_request_sync(
        model=model,
        url=url,
        method="GET",
        params=params,
        api_key=api_key,
        client=client,
    )


def post_request_sync(
    model: type[T],
    url: str,
    *,
    body: Any | None = None,
    api_key: str | None = None,
    client: httpx.Client | None = None,
) -> tuple[T, int, str]:
    return _base_request_sync(
        model=model,
        url=url,
        method="POST",
        body=body,
        api_key=api_key,
        client=client,
    )


def patch_request_sync(
    model: type[T],
    url: str,
    *,
    body: Any | None = None,
    api_key: str | None = None,
    client: httpx.Client | None = None,
) -> tuple[T, int, str]:
    return _base_request_sync(
        model=model,
        url=url,
        method="PATCH",
        body=body,
        api_key=api_key,
        client=client,
    )


async def _base_request_async(
    model: type[T],
    url: str,
    method: str,
    *,
    params: dict[str, Any] | None = None,
    body: Any | None = None,
    api_key: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> tuple[T, int, str]:
    headers: dict[str, str] = {}
    if method in ("POST", "PATCH"):
        headers["Content-Type"] = "application/json"
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    json_body = body if method in ("POST", "PATCH") else None

    if client is not None:
        response = await client.request(
            method=method,
            url=url,
            params=params,
            json=json_body,
            headers=headers,
        )
    else:
        async with httpx.AsyncClient() as temp_client:
            response = await temp_client.request(
                method=method,
                url=url,
                params=params,
                json=json_body,
                headers=headers,
            )

    return _process_response(model, response)


def _base_request_sync(
    model: type[T],
    url: str,
    method: str,
    *,
    params: dict[str, Any] | None = None,
    body: Any | None = None,
    api_key: str | None = None,
    client: httpx.Client | None = None,
) -> tuple[T, int, str]:
    headers: dict[str, str] = {}
    if method in ("POST", "PATCH"):
        headers["Content-Type"] = "application/json"
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    json_body = body if method in ("POST", "PATCH") else None

    if client is not None:
        response = client.request(
            method=method,
            url=url,
            params=params,
            json=json_body,
            headers=headers,
        )
    else:
        with httpx.Client() as temp_client:
            response = temp_client.request(
                method=method,
                url=url,
                params=params,
                json=json_body,
                headers=headers,
            )

    return _process_response(model, response)


def _process_response(model: type[T], response: httpx.Response) -> tuple[T, int, str]:
    status = response.status_code
    status_text = response.reason_phrase

    if not response.is_success:
        raise FetchError(response.text, status, status_text)

    try:
        raw_data = json.loads(response.text, object_hook=bigint_reviver)
        data = model.model_validate(raw_data)
        return (data, status, status_text)
    except ValidationError as e:
        raise ValueError(prettify_validation_error(e)) from e


def _bcs_encode_string(s: str) -> bytes:
    serializer = Serializer()
    serializer.str(s)
    return serializer.output()


def _get_subaccount_seed_bytes(owner_addr: AccountAddress, seed: str) -> bytes:
    # TODO: Is this the best way to concatenate/serialize SubaccountSeed?
    return bytes(owner_addr.address) + _bcs_encode_string(seed)


def get_market_addr(name: str, perp_engine_global_addr: str) -> str:
    creator = AccountAddress.from_str(perp_engine_global_addr)
    market_name_bytes = _bcs_encode_string(name)
    return str(AccountAddress.for_named_object(creator, market_name_bytes))


def get_primary_subaccount_addr(
    addr: AccountAddress | str,
    compat_version: CompatVersion,
    package_addr: AccountAddress | str,
) -> str:
    _ = compat_version
    account = AccountAddress.from_str(addr) if isinstance(addr, str) else addr
    package_address = (
        AccountAddress.from_str(package_addr) if isinstance(package_addr, str) else package_addr
    )
    deriver = AccountAddress.for_named_object(package_address, b"GlobalSubaccountManager")
    seed_bytes = _get_subaccount_seed_bytes(account, "primary_subaccount")
    result = str(AccountAddress.for_named_object(deriver, seed_bytes))
    logger.debug(
        "Deriving primary subaccount address for account %s, package %s, deriver %s, got: %s",
        account,
        package_address,
        deriver,
        result,
    )
    return result


def get_trading_competition_subaccount_addr(addr: AccountAddress | str) -> str:
    account = AccountAddress.from_str(addr) if isinstance(addr, str) else addr
    return str(AccountAddress.for_named_object(account, b"trading_competition"))


def get_vault_share_address(vault_address: str) -> str:
    creator = AccountAddress.from_str(vault_address)
    return str(AccountAddress.for_named_object(creator, b"vault_share_asset"))


def round_to_tick_size(price: float, tick_size: int, px_decimals: int, round_up: bool) -> float:
    if price == 0:
        return 0.0
    denormalized = price * (10**px_decimals)
    if round_up:
        rounded = math.ceil(denormalized / tick_size) * tick_size
    else:
        rounded = math.floor(denormalized / tick_size) * tick_size
    return round(rounded / (10**px_decimals), px_decimals)


def round_to_valid_price(price: float, tick_size: int, px_decimals: int) -> float:
    """Round a price to the nearest valid tick size using standard rounding."""
    if price == 0:
        return 0.0
    denormalized = price * (10**px_decimals)
    rounded = round(denormalized / tick_size) * tick_size
    return round(rounded / (10**px_decimals), px_decimals)


def round_to_valid_order_size(
    order_size: float,
    lot_size: int,
    sz_decimals: int,
    min_size: int,
) -> float:
    """Round an order size to the nearest valid lot size, enforcing minimum size."""
    if order_size == 0:
        return 0.0

    normalized_min_size = min_size / (10**sz_decimals)
    if order_size < normalized_min_size:
        return normalized_min_size

    denormalized = order_size * (10**sz_decimals)
    rounded = round(denormalized / lot_size) * lot_size
    return round(rounded / (10**sz_decimals), sz_decimals)


def amount_to_chain_units(amount: float, decimals: int = 6) -> int:
    """Convert a decimal amount to chain units (e.g., 5.67 USDC -> 5670000)."""
    return int(amount * (10**decimals))


def chain_units_to_amount(chain_units: int, decimals: int = 6) -> float:
    """Convert chain units to a decimal amount (e.g., 5670000 -> 5.67)."""
    return chain_units / (10**decimals)


def extract_vault_address_from_create_tx(create_vault_tx: dict[str, Any]) -> str:
    vault_address: str | dict[str, str] | None = None

    events = create_vault_tx.get("events")
    if isinstance(events, list):
        events_list = cast("list[Any]", events)
        for event in events_list:
            if isinstance(event, dict):
                event_dict = cast("dict[str, Any]", event)
                event_type = event_dict.get("type", "")
                if isinstance(event_type, str) and "::vault::VaultCreatedEvent" in event_type:
                    event_data = event_dict.get("data", {})
                    if isinstance(event_data, dict):
                        data_dict = cast("dict[str, Any]", event_data)
                        vault_val = data_dict.get("vault")
                        if isinstance(vault_val, str):
                            vault_address = vault_val
                        elif isinstance(vault_val, dict):
                            vault_address = cast("dict[str, str]", vault_val)
                    break

    if vault_address is None:
        raise ValueError("Unable to extract vault address from transaction")

    if isinstance(vault_address, dict) and "inner" in vault_address:
        return vault_address["inner"]

    if isinstance(vault_address, str):
        return vault_address

    raise ValueError("Unable to extract vault address from transaction")


def generate_random_replay_protection_nonce() -> int | None:
    buf = [secrets.randbits(32), secrets.randbits(32)]

    if buf[0] == 0 or buf[1] == 0:
        return None

    return (buf[0] << 32) | buf[1]
