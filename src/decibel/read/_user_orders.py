from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from ._base import BaseReader
from ._user_order_history import UserOrder

if TYPE_CHECKING:
    from .._asset_type import AssetTypeName

__all__ = [
    "UserOrderUpdate",
    "UserOrdersReader",
]


class UserOrderUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    status: str
    details: str
    order: UserOrder


class UserOrdersReader(BaseReader):
    async def get_order(
        self,
        *,
        sub_addr: str,
        market: str,
        order_id: str | None = None,
        client_order_id: str | None = None,
        asset_type: AssetTypeName | None = None,
    ) -> UserOrderUpdate:
        """Look up a single order by ``order_id`` (perp + spot) or ``client_order_id`` (perp only).

        Unlike the list readers, ``asset_type`` defaults to unset: the API then checks perp first
        and falls through to spot, which is the right behaviour for a point lookup by id.

        Exactly one of ``order_id`` / ``client_order_id`` must be given. ``client_order_id`` is a
        perp-only field — spot orders don't carry one.
        """
        if (order_id is None) == (client_order_id is None):
            raise ValueError("Pass exactly one of order_id or client_order_id")

        params: dict[str, str] = {"account": sub_addr, "market": market}
        if order_id is not None:
            params["order_id"] = order_id
        if client_order_id is not None:
            params["client_order_id"] = client_order_id
        if asset_type is not None:
            params["asset_type"] = asset_type.value

        response, _, _ = await self.get_request(
            model=UserOrderUpdate,
            url=f"{self.config.trading_http_url}/api/v1/orders",
            params=params,
        )
        return response
