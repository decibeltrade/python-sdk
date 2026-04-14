from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Literal

import httpx
from pydantic import BaseModel

from ._utils import FetchError

if TYPE_CHECKING:
    from ._constants import DecibelConfig

__all__ = [
    "OrderStatus",
    "OrderStatusClient",
    "OrderStatusType",
]

logger = logging.getLogger(__name__)

OrderStatusType = Literal["Acknowledged", "Filled", "Cancelled", "Rejected", "Unknown"]


class OrderStatus(BaseModel):
    parent: str
    market: str
    order_id: str
    status: str
    orig_size: float
    remaining_size: float
    size_delta: float
    price: float
    is_buy: bool
    details: str
    transaction_version: int
    unix_ms: int


class OrderStatusClient:
    def __init__(
        self,
        config: DecibelConfig,
        *,
        http_client: httpx.AsyncClient | None = None,
        http_client_sync: httpx.Client | None = None,
    ) -> None:
        self._config = config
        self._http_client = http_client
        self._http_client_sync = http_client_sync

    async def get_order_status(
        self,
        order_id: str,
        market_address: str,
        user_address: str,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> OrderStatus | None:
        url = f"{self._config.trading_http_url}/api/v1/orders"
        params = {
            "order_id": order_id,
            "market_address": market_address,
            "account": user_address,
        }

        effective_client = client or self._http_client

        try:
            if effective_client is not None:
                response = await effective_client.get(url, params=params, timeout=5.0)
            else:
                async with httpx.AsyncClient() as temp_client:
                    response = await temp_client.get(url, params=params, timeout=5.0)

            if response.status_code == 404:
                return None

            if not response.is_success:
                raise FetchError(response.text, response.status_code, response.reason_phrase)

            return OrderStatus.model_validate(response.json())
        except Exception as e:
            logger.error("Error fetching order status: %s", e)
            return None

    def get_order_status_sync(
        self,
        order_id: str,
        market_address: str,
        user_address: str,
        *,
        client: httpx.Client | None = None,
    ) -> OrderStatus | None:
        url = f"{self._config.trading_http_url}/api/v1/orders"
        params = {
            "order_id": order_id,
            "market_address": market_address,
            "account": user_address,
        }

        effective_client = client or self._http_client_sync

        try:
            if effective_client is not None:
                response = effective_client.get(url, params=params, timeout=5.0)
            else:
                with httpx.Client() as temp_client:
                    response = temp_client.get(url, params=params, timeout=5.0)

            if response.status_code == 404:
                return None

            if not response.is_success:
                raise FetchError(response.text, response.status_code, response.reason_phrase)

            return OrderStatus.model_validate(response.json())
        except Exception as e:
            logger.error("Error fetching order status: %s", e)
            return None

    @staticmethod
    def parse_order_status_type(status: str | None) -> OrderStatusType:
        if not status:
            return "Unknown"
        lower_status = status.lower()
        if "acknowledged" in lower_status:
            return "Acknowledged"
        if "filled" in lower_status:
            return "Filled"
        if "cancelled" in lower_status:
            return "Cancelled"
        if "rejected" in lower_status:
            return "Rejected"
        return "Unknown"

    @staticmethod
    def is_success_status(status: str | None) -> bool:
        return OrderStatusClient.parse_order_status_type(status) == "Filled"

    @staticmethod
    def is_failure_status(status: str | None) -> bool:
        status_type = OrderStatusClient.parse_order_status_type(status)
        return status_type in ("Cancelled", "Rejected")

    @staticmethod
    def is_final_status(status: str | None) -> bool:
        return OrderStatusClient.is_success_status(status) or OrderStatusClient.is_failure_status(
            status
        )
