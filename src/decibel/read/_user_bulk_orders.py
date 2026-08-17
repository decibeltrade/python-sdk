from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, RootModel

from .._asset_type import AssetTypeName, to_asset_type_param
from ._base import BaseReader

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from .._asset_type import AssetTypeFilter
    from ._ws import Unsubscribe

__all__ = [
    "UserBulkOrder",
    "UserBulkOrderFill",
    "UserBulkOrderFillsResponse",
    "UserBulkOrdersReader",
    "UserBulkOrderStatus",
    "UserBulkOrderWsMessage",
]


class UserBulkOrder(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    # Absent on API versions that predate spot support (treat as "perp").
    asset_type: AssetTypeName | None = None
    market: str
    sequence_number: int
    # Null on bulk-order rejection rows (no accepted predecessor), and absent on API versions
    # that predate the field.
    previous_seq_num: int | None = None
    bid_prices: list[float]
    bid_sizes: list[float]
    ask_prices: list[float]
    ask_sizes: list[float]
    cancelled_bid_prices: list[float]
    cancelled_bid_sizes: list[float]
    cancelled_ask_prices: list[float]
    cancelled_ask_sizes: list[float]
    user: str | None = None
    cancellation_reason: str | None = None
    transaction_version: int | None = None
    transaction_unix_ms: int | None = None


class _UserBulkOrdersList(RootModel[list[UserBulkOrder]]):
    pass


class UserBulkOrderStatus(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    #: "Placed" or "Rejected".
    status: str
    details: str
    bulk_order: UserBulkOrder


class UserBulkOrderFill(BaseModel):
    """A single fill against a resting bulk-order level.

    The wire payload also carries ``event_uid`` (a u128); it is intentionally not surfaced
    for parity with the TypeScript SDK, which cannot represent it losslessly.
    """

    model_config = ConfigDict(populate_by_name=True)

    # Absent on API versions that predate spot support (treat as "perp").
    asset_type: AssetTypeName | None = None
    market: str
    sequence_number: int
    user: str
    filled_size: float
    price: float
    is_bid: bool
    trade_id: str
    transaction_unix_ms: int
    transaction_version: int


class UserBulkOrderFillsResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    items: list[UserBulkOrderFill]
    total_count: int | None = None


class _UserBulkOrderInner(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    status: str
    details: str
    bulk_order: UserBulkOrder


class UserBulkOrderWsMessage(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    bulk_order: _UserBulkOrderInner


class UserBulkOrdersReader(BaseReader):
    async def get_by_addr(
        self,
        *,
        sub_addr: str,
        market: str | None = None,
        asset_type: AssetTypeFilter = "perp",
    ) -> list[UserBulkOrder]:
        """Get the bulk orders for a subaccount.

        ``asset_type`` is a server-side product filter (default ``"perp"``). Pass ``"spot"`` to
        scope the response to spot, or ``"all"`` to omit the param and receive perp and spot
        merged — each row then carries ``asset_type`` for client-side demux.
        """
        params: dict[str, str] = {"account": sub_addr, "market": market or "all"}
        asset_type_param = to_asset_type_param(asset_type)
        if asset_type_param is not None:
            params["asset_type"] = asset_type_param

        response, _, _ = await self.get_request(
            model=_UserBulkOrdersList,
            url=f"{self.config.trading_http_url}/api/v1/bulk_orders",
            params=params,
        )
        return response.root

    async def get_status(
        self,
        *,
        sub_addr: str,
        market: str,
        sequence_number: int,
        asset_type: AssetTypeName = AssetTypeName.PERP,
    ) -> UserBulkOrderStatus:
        """Get the status of a single bulk order by (account, market, sequence number).

        Bulk-order status is keyed per product, so there is no merged ``"all"`` view here.
        """
        response, _, _ = await self.get_request(
            model=UserBulkOrderStatus,
            url=f"{self.config.trading_http_url}/api/v1/bulk_order_status",
            params={
                "account": sub_addr,
                "market": market,
                "sequence_number": str(sequence_number),
                "asset_type": asset_type.value,
            },
        )
        return response

    async def get_fills(
        self,
        *,
        sub_addr: str,
        market: str | None = None,
        sequence_number: int | None = None,
        start_sequence_number: int | None = None,
        end_sequence_number: int | None = None,
        limit: int | None = None,
        offset: int | None = None,
        asset_type: AssetTypeFilter = "perp",
    ) -> UserBulkOrderFillsResponse:
        """Get fills of a subaccount's bulk orders.

        Optionally scoped to a market and to a single ``sequence_number`` or a
        ``start_sequence_number``/``end_sequence_number`` range (the end requires the start).
        """
        params: dict[str, str] = {"account": sub_addr}
        if market is not None:
            params["market"] = market
        if sequence_number is not None:
            params["sequence_number"] = str(sequence_number)
        if start_sequence_number is not None:
            params["start_sequence_number"] = str(start_sequence_number)
        if end_sequence_number is not None:
            params["end_sequence_number"] = str(end_sequence_number)
        if limit is not None:
            params["limit"] = str(limit)
        if offset is not None:
            params["offset"] = str(offset)
        asset_type_param = to_asset_type_param(asset_type)
        if asset_type_param is not None:
            params["asset_type"] = asset_type_param

        response, _, _ = await self.get_request(
            model=UserBulkOrderFillsResponse,
            url=f"{self.config.trading_http_url}/api/v1/bulk_order_fills",
            params=params,
        )
        return response

    def subscribe_by_addr(
        self,
        sub_addr: str,
        on_data: (
            Callable[[UserBulkOrderWsMessage], None]
            | Callable[[UserBulkOrderWsMessage], Awaitable[None]]
        ),
    ) -> Unsubscribe:
        topic = f"bulk_orders:{sub_addr}"
        return self.ws.subscribe(topic, UserBulkOrderWsMessage, on_data)
