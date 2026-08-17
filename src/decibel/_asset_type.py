from __future__ import annotations

from enum import StrEnum
from typing import Literal

__all__ = [
    "AssetTypeName",
    "AssetTypeFilter",
    "to_asset_type_param",
    "is_spot",
]


class AssetTypeName(StrEnum):
    """Product discriminator carried on rows of endpoints that serve perp and spot together.

    ``/markets``, open orders, order history, bulk orders/fills, trades, and their WS topics
    all carry this field. It is optional everywhere: API versions that predate spot support
    omit it, and an absent value means ``perp``.
    """

    PERP = "perp"
    SPOT = "spot"


AssetTypeFilter = Literal["perp", "spot", "all"]
"""SDK-side product filter for the dual-use endpoints.

``"perp"`` and ``"spot"`` are sent to the API as the ``asset_type`` query param; ``"all"``
omits the param, which the API treats as "union both products" (rows are then demuxed
client-side via each row's ``asset_type`` field).

Readers default to ``"perp"`` so existing perp consumers keep their exact pre-spot responses
(and pagination) — spot is strictly opt-in.
"""


def to_asset_type_param(asset_type: AssetTypeFilter) -> str | None:
    """Resolve an :data:`AssetTypeFilter` to the ``asset_type`` wire param (``"all"`` -> omit)."""
    return None if asset_type == "all" else asset_type


def is_spot(asset_type: AssetTypeName | str | None) -> bool:
    """Whether a row's ``asset_type`` denotes spot. Absent/unknown values are treated as perp."""
    return asset_type == AssetTypeName.SPOT
