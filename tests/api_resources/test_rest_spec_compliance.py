"""Behavioral tests verifying the SDK matches the REST API specification.

These tests mock HTTP transport to verify:
1. Readers call the correct endpoint URLs (SPEC-REST.md)
2. Readers send the correct query parameters
3. Authentication headers are included/excluded correctly
4. Response JSON is correctly parsed into Pydantic models
5. Required fields are enforced (missing required fields → error)
6. Nullable fields accept None properly
7. Wrong types are rejected
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import httpx
import pytest
from pydantic import ValidationError

from decibel._utils import FetchError, get_request
from decibel.read._account_overview import AccountOverview
from decibel.read._candlesticks import Candlestick
from decibel.read._market_prices import MarketPrice, MarketPricesReader
from decibel.read._markets import PerpMarket
from decibel.read._user_open_orders import UserOpenOrder
from decibel.read._user_positions import UserPosition

from .conftest import MockTransport

if TYPE_CHECKING:
    from decibel.read._base import ReaderDeps

# ---------------------------------------------------------------------------
# SPEC Section 2.1 — GET /api/v1/prices
# Tests the READER, not just the model.
# ---------------------------------------------------------------------------


class TestMarketPricesReader:
    """Verify MarketPricesReader calls correct endpoints with correct params."""

    SAMPLE_PRICE: dict[str, Any] = {
        "market": "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
        "oracle_px": 50125.75,
        "mark_px": 50120.5,
        "mid_px": 50122.25,
        "funding_rate_bps": 5.0,
        "is_funding_positive": True,
        "transaction_unix_ms": 1699564800000,
        "open_interest": 125000.5,
    }

    @pytest.fixture
    def mock_reader(
        self, reader_deps: ReaderDeps, mock_transport: MockTransport
    ) -> tuple[MarketPricesReader, MockTransport]:
        mock_transport.set_response([self.SAMPLE_PRICE])

        reader = MarketPricesReader(reader_deps)

        async def patched_get(model: type, url: str, *, params: dict | None = None) -> tuple:
            async with httpx.AsyncClient(transport=mock_transport) as client:
                return await get_request(
                    model=model,
                    url=url,
                    params=params,
                    api_key="test-key",
                    client=client,
                )

        reader.get_request = patched_get  # type: ignore[assignment]
        return reader, mock_transport

    async def test_get_all_calls_prices_endpoint(
        self, mock_reader: tuple[MarketPricesReader, MockTransport]
    ) -> None:
        """Reader.get_all() SHALL call GET /api/v1/prices."""
        reader, transport = mock_reader
        prices = await reader.get_all()

        assert len(transport.captured_requests) == 1
        req = transport.captured_requests[0]
        assert req.method == "GET"
        assert "/api/v1/prices" in req.url
        # Verify returned data is parsed
        assert len(prices) == 1
        assert prices[0].oracle_px == 50125.75


# ---------------------------------------------------------------------------
# SPEC Section 4 — Authentication
# ---------------------------------------------------------------------------


class TestAuthentication:
    """SPEC.md Section 4.1: REST API Authentication headers."""

    async def test_bearer_token_included_when_key_set(self) -> None:
        """SHALL include Authorization: Bearer <KEY> header."""
        transport = MockTransport()
        transport.set_response([])

        async with httpx.AsyncClient(transport=transport) as client:
            from decibel.read._market_prices import _MarketPriceList

            await get_request(
                model=_MarketPriceList,
                url="https://test/api/v1/prices",
                api_key="my-api-key-xyz",
                client=client,
            )

        req = transport.captured_requests[0]
        assert req.headers["authorization"] == "Bearer my-api-key-xyz"

    async def test_no_auth_header_when_key_is_none(self) -> None:
        """SHALL NOT include Authorization header when api_key is None."""
        transport = MockTransport()
        transport.set_response([])

        async with httpx.AsyncClient(transport=transport) as client:
            from decibel.read._market_prices import _MarketPriceList

            await get_request(
                model=_MarketPriceList,
                url="https://test/api/v1/prices",
                api_key=None,
                client=client,
            )

        req = transport.captured_requests[0]
        assert "authorization" not in req.headers


# ---------------------------------------------------------------------------
# SPEC Section 6 — Error Handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """SPEC.md Section 6: Error response parsing and FetchError."""

    async def _fetch_and_expect_error(self, body: dict, status_code: int) -> FetchError:
        """Helper: make a request that returns an error, return the FetchError."""
        transport = MockTransport()
        transport.set_response(body, status_code=status_code)

        async with httpx.AsyncClient(transport=transport) as client:
            from decibel.read._market_prices import _MarketPriceList

            with pytest.raises(FetchError) as exc_info:
                await get_request(
                    model=_MarketPriceList,
                    url="https://test/fail",
                    api_key="k",
                    client=client,
                )

        return exc_info.value

    async def test_400_raises_fetch_error(self) -> None:
        """SHALL raise FetchError for 400 Bad Request."""
        err = await self._fetch_and_expect_error(
            {"status": "failed", "message": "Invalid parameters"}, 400
        )
        assert err.status == 400
        assert err.status_text == "failed"
        assert err.response_message == "Invalid parameters"

    async def test_404_raises_fetch_error_with_not_found(self) -> None:
        """SHALL parse notFound status from error body."""
        err = await self._fetch_and_expect_error(
            {"status": "notFound", "message": "Market not found"}, 404
        )
        assert err.status == 404
        assert err.status_text == "notFound"

    async def test_500_raises_fetch_error(self) -> None:
        """SHALL raise FetchError for 500 Internal Server Error."""
        err = await self._fetch_and_expect_error(
            {"status": "failed", "message": "Server error"}, 500
        )
        assert err.status == 500


# ---------------------------------------------------------------------------
# Model validation: PriceDto — positive AND negative
# ---------------------------------------------------------------------------


class TestPriceDtoValidation:
    """PriceDto SHALL enforce required fields and reject bad types."""

    def test_valid_price_parses(self) -> None:
        """Valid PriceDto with all required fields SHALL parse."""
        price = MarketPrice.model_validate(
            {
                "market": "0x" + "a" * 64,
                "oracle_px": 100.0,
                "mark_px": 99.0,
                "mid_px": 99.5,
                "funding_rate_bps": 1.0,
                "is_funding_positive": True,
                "transaction_unix_ms": 1000,
                "open_interest": 50.0,
            }
        )
        assert price.oracle_px == 100.0

    def test_missing_required_field_raises(self) -> None:
        """Missing 'market' field SHALL raise ValidationError."""
        with pytest.raises(ValidationError):
            MarketPrice.model_validate(
                {
                    # "market" is missing
                    "oracle_px": 100.0,
                    "mark_px": 99.0,
                    "mid_px": 99.5,
                    "funding_rate_bps": 1.0,
                    "is_funding_positive": True,
                    "transaction_unix_ms": 1000,
                    "open_interest": 50.0,
                }
            )

    def test_wrong_type_for_oracle_px_raises(self) -> None:
        """Non-numeric oracle_px SHALL raise ValidationError."""
        with pytest.raises(ValidationError):
            MarketPrice.model_validate(
                {
                    "market": "0x" + "a" * 64,
                    "oracle_px": "not_a_number",
                    "mark_px": 99.0,
                    "mid_px": 99.5,
                    "funding_rate_bps": 1.0,
                    "is_funding_positive": True,
                    "transaction_unix_ms": 1000,
                    "open_interest": 50.0,
                }
            )


# ---------------------------------------------------------------------------
# Model validation: MarketDto — positive AND negative
# ---------------------------------------------------------------------------


class TestMarketDtoValidation:
    """MarketDto SHALL enforce required fields and mode enum."""

    def test_valid_market_parses(self) -> None:
        market = PerpMarket.model_validate(
            {
                "market_addr": "0x" + "a" * 64,
                "market_name": "BTC-PERP",
                "sz_decimals": 4,
                "max_leverage": 50,
                "tick_size": 100,
                "min_size": 1000,
                "lot_size": 100,
                "max_open_interest": 1000000.0,
                "px_decimals": 1,
                "mode": "Open",
            }
        )
        assert market.market_name == "BTC-PERP"
        assert market.mode.value == "Open"

    def test_mode_reduce_only_parses(self) -> None:
        """ReduceOnly mode SHALL be accepted."""
        market = PerpMarket.model_validate(
            {
                "market_addr": "0x" + "b" * 64,
                "market_name": "ETH-PERP",
                "sz_decimals": 8,
                "max_leverage": 20,
                "tick_size": 10,
                "min_size": 100,
                "lot_size": 10,
                "max_open_interest": 500000.0,
                "px_decimals": 2,
                "mode": "ReduceOnly",
            }
        )
        assert market.mode.value == "ReduceOnly"

    def test_missing_market_name_raises(self) -> None:
        """Missing required field SHALL raise ValidationError."""
        with pytest.raises(ValidationError):
            PerpMarket.model_validate(
                {
                    "market_addr": "0x" + "a" * 64,
                    # "market_name" missing
                    "sz_decimals": 4,
                    "max_leverage": 50,
                    "tick_size": 100,
                    "min_size": 1000,
                    "lot_size": 100,
                    "max_open_interest": 1000000.0,
                    "px_decimals": 1,
                    "mode": "Open",
                }
            )


# ---------------------------------------------------------------------------
# Model validation: CandlestickDto — alias mapping
# ---------------------------------------------------------------------------


class TestCandlestickDtoValidation:
    """CandlestickDto SHALL map single-letter JSON keys to descriptive field names."""

    def test_alias_mapping(self) -> None:
        """JSON keys t/T/o/h/l/c/v/i SHALL map to descriptive Python attrs."""
        candle = Candlestick.model_validate(
            {
                "t": 1000,
                "T": 2000,
                "o": 10.0,
                "h": 12.0,
                "l": 9.0,
                "c": 11.0,
                "v": 500.0,
                "i": "1h",
            }
        )
        assert candle.time_start == 1000
        assert candle.time_end == 2000
        assert candle.open_price == 10.0
        assert candle.high == 12.0
        assert candle.low == 9.0
        assert candle.close == 11.0
        assert candle.volume == 500.0
        assert candle.interval == "1h"

    def test_missing_alias_field_raises(self) -> None:
        """Missing 'o' (open) alias SHALL raise ValidationError."""
        with pytest.raises(ValidationError):
            Candlestick.model_validate(
                {
                    "t": 1000,
                    "T": 2000,
                    # "o" missing
                    "h": 12.0,
                    "l": 9.0,
                    "c": 11.0,
                    "v": 500.0,
                    "i": "1h",
                }
            )


# ---------------------------------------------------------------------------
# Model validation: AccountOverviewDto — nullable vs required
# ---------------------------------------------------------------------------


class TestAccountOverviewValidation:
    """AccountOverviewDto SHALL enforce required fields and accept nulls for optional ones."""

    MINIMAL_VALID: dict[str, Any] = {
        "perp_equity_balance": 100.0,
        "unrealized_pnl": 10.0,
        "unrealized_funding_cost": -5.0,
        "cross_margin_ratio": 0.01,
        "maintenance_margin": 50.0,
        "cross_account_leverage_ratio": None,  # nullable
        "total_margin": 80.0,
        "usdc_cross_withdrawable_balance": 70.0,
        "usdc_isolated_withdrawable_balance": 0.0,
        "cross_account_position": 0.0,
        "volume": None,
        "all_time_return": None,
        "pnl_90d": None,
        "sharpe_ratio": None,
        "max_drawdown": None,
        "weekly_win_rate_12w": None,
        "average_cash_position": None,
        "average_leverage": None,
        "realized_pnl": None,
        "liquidation_fees_paid": None,
        "liquidation_losses": None,
    }

    def test_minimal_valid_overview_parses(self) -> None:
        overview = AccountOverview.model_validate(self.MINIMAL_VALID)
        assert overview.perp_equity_balance == 100.0
        assert overview.volume is None

    def test_missing_perp_equity_balance_raises(self) -> None:
        """perp_equity_balance is required — omitting it SHALL fail."""
        data = {**self.MINIMAL_VALID}
        del data["perp_equity_balance"]
        with pytest.raises(ValidationError):
            AccountOverview.model_validate(data)

    def test_null_for_required_field_raises(self) -> None:
        """Setting perp_equity_balance=None SHALL fail (it's not nullable)."""
        data = {**self.MINIMAL_VALID, "perp_equity_balance": None}
        with pytest.raises(ValidationError):
            AccountOverview.model_validate(data)


# ---------------------------------------------------------------------------
# Model validation: PositionDto — TP/SL nullable contract
# ---------------------------------------------------------------------------


class TestPositionDtoValidation:
    """PositionDto SHALL enforce required fields and allow null TP/SL."""

    VALID_POSITION: dict[str, Any] = {
        "market": "0x" + "a" * 64,
        "user": "0x" + "b" * 64,
        "size": 2.5,
        "user_leverage": 10,
        "entry_price": 49800.0,
        "is_isolated": False,
        "is_deleted": False,
        "unrealized_funding": -25.5,
        "estimated_liquidation_price": 45000.0,
        "transaction_version": 123,
        "has_fixed_sized_tpsls": False,
        "tp_order_id": None,
        "tp_trigger_price": None,
        "tp_limit_price": None,
        "sl_order_id": None,
        "sl_trigger_price": None,
        "sl_limit_price": None,
    }

    def test_valid_position_parses(self) -> None:
        pos = UserPosition.model_validate(self.VALID_POSITION)
        assert pos.size == 2.5
        assert pos.tp_order_id is None

    def test_position_with_tp_sl_set(self) -> None:
        """Positions with TP/SL SHALL parse correctly."""
        data = {
            **self.VALID_POSITION,
            "tp_order_id": "tp1",
            "tp_trigger_price": 55000.0,
            "sl_order_id": "sl1",
            "sl_trigger_price": 40000.0,
        }
        pos = UserPosition.model_validate(data)
        assert pos.tp_order_id == "tp1"
        assert pos.sl_trigger_price == 40000.0

    def test_missing_size_raises(self) -> None:
        """'size' is required — omitting it SHALL fail."""
        data = {**self.VALID_POSITION}
        del data["size"]
        with pytest.raises(ValidationError):
            UserPosition.model_validate(data)


# ---------------------------------------------------------------------------
# Model validation: OrderDto — required fields
# ---------------------------------------------------------------------------


class TestOrderDtoValidation:
    """OrderDto (UserOpenOrder) SHALL enforce required fields."""

    VALID_ORDER: dict[str, Any] = {
        "parent": "0x" + "0" * 64,
        "market": "0x" + "a" * 64,
        "client_order_id": "c1",
        "order_id": "45678",
        "is_buy": True,
        "is_tpsl": False,
        "details": "",
        "transaction_version": 12345678,
        "unix_ms": 1699564800000,
        "tp_trigger_price": None,
        "tp_limit_price": None,
        "sl_trigger_price": None,
        "sl_limit_price": None,
        "orig_size": 1.5,
        "remaining_size": 1.5,
        "size_delta": None,
        "price": 50000.5,
    }

    def test_valid_order_parses(self) -> None:
        order = UserOpenOrder.model_validate(self.VALID_ORDER)
        assert order.order_id == "45678"
        assert order.is_buy is True

    def test_missing_order_id_raises(self) -> None:
        data = {**self.VALID_ORDER}
        del data["order_id"]
        with pytest.raises(ValidationError):
            UserOpenOrder.model_validate(data)

    def test_missing_is_buy_raises(self) -> None:
        data = {**self.VALID_ORDER}
        del data["is_buy"]
        with pytest.raises(ValidationError):
            UserOpenOrder.model_validate(data)


# ---------------------------------------------------------------------------
# Model validation: TwapDto — status literal enforcement
# ---------------------------------------------------------------------------


class TestTwapDtoValidation:
    """TwapDto SHALL enforce status Literal and required fields."""

    VALID_TWAP: dict[str, Any] = {
        "market": "0x" + "a" * 64,
        "is_buy": True,
        "order_id": "78901",
        "client_order_id": "twap_123",
        "is_reduce_only": False,
        "start_unix_ms": 1699564800000,
        "frequency_s": 300,
        "duration_s": 3600,
        "orig_size": 100.0,
        "remaining_size": 75.0,
        "status": "Activated",
        "transaction_unix_ms": 1699564800000,
        "transaction_version": 12345679,
    }

    def test_valid_twap_parses(self) -> None:
        from decibel.read._user_active_twaps import UserActiveTwap

        twap = UserActiveTwap.model_validate(self.VALID_TWAP)
        assert twap.frequency_s == 300
        assert twap.status == "Activated"

    def test_invalid_status_raises(self) -> None:
        """Status must be a valid TwapStatus literal — bogus values SHALL fail."""
        from decibel.read._user_active_twaps import UserActiveTwap

        data = {**self.VALID_TWAP, "status": "InvalidStatus"}
        with pytest.raises(ValidationError):
            UserActiveTwap.model_validate(data)

    def test_missing_frequency_raises(self) -> None:
        from decibel.read._user_active_twaps import UserActiveTwap

        data = {**self.VALID_TWAP}
        del data["frequency_s"]
        with pytest.raises(ValidationError):
            UserActiveTwap.model_validate(data)


# ---------------------------------------------------------------------------
# Utility function tests
# ---------------------------------------------------------------------------


class TestUtilityFunctions:
    """Verify chain unit conversion utilities match spec Section 5.6."""

    def test_amount_to_chain_units(self) -> None:
        from decibel._utils import amount_to_chain_units

        assert amount_to_chain_units(1.0) == 1_000_000
        assert amount_to_chain_units(0.5) == 500_000
        assert amount_to_chain_units(100.123456) == 100_123_456

    def test_chain_units_to_amount(self) -> None:
        from decibel._utils import chain_units_to_amount

        assert chain_units_to_amount(1_000_000) == 1.0
        assert chain_units_to_amount(500_000) == 0.5

    def test_bigint_reviver_converts_bigint(self) -> None:
        from decibel._utils import bigint_reviver

        result = bigint_reviver({"$bigint": "340282366920938463463374607431768211455"})
        assert result == 340282366920938463463374607431768211455
        assert isinstance(result, int)

    def test_bigint_reviver_passes_through_normal_dicts(self) -> None:
        from decibel._utils import bigint_reviver

        obj = {"key": "value", "num": 42}
        assert bigint_reviver(obj) == obj


# ---------------------------------------------------------------------------
# SPEC Section 2.13 — GET /api/v1/spot/asset_contexts
# ---------------------------------------------------------------------------


SAMPLE_SPOT_ASSET_CONTEXT: dict[str, Any] = {
    "market_addr": "0x26f1ddaa436a7b134d5c872c032eaa66653b673bca2bb1539642094d6b113c50",
    "name": "APT/USDC",
    "ticker_id": "APT_USDC",
    "base_asset_addr": "0xa",
    "quote_asset_addr": "0xbae207659db88bea0cbead6da0ed00aac12edcdda169e591cd41c94180b46f3b",
    "base_decimals": 8,
    "quote_decimals": 6,
    "last_price": 12.5,
    "mid": 12.51,
    "prev_day_price": 12.0,
    "volume_24h_base": 1000.0,
    "volume_24h_quote": 12500.0,
    "high_24h": 13.0,
    "low_24h": 11.5,
    "timestamp_unix_ms": 1699564800000,
}


class TestSpotAssetContextsEndpoint:
    """Spot asset contexts SHALL be served from GET /api/v1/spot/asset_contexts."""

    async def test_endpoint_url_and_no_params(
        self, transport_deps: ReaderDeps, mock_transport: MockTransport
    ) -> None:
        from decibel.read._spot_asset_contexts import SpotAssetContextsReader

        mock_transport.set_response([SAMPLE_SPOT_ASSET_CONTEXT])
        contexts = await SpotAssetContextsReader(transport_deps).get_all()

        req = mock_transport.captured_requests[0]
        assert req.method == "GET"
        assert req.url.endswith("/api/v1/spot/asset_contexts")
        assert req.params is None
        assert contexts[0].name == "APT/USDC"
        assert contexts[0].base_decimals == 8

    async def test_sends_bearer_token(
        self, transport_deps: ReaderDeps, mock_transport: MockTransport
    ) -> None:
        from decibel.read._spot_asset_contexts import SpotAssetContextsReader

        mock_transport.set_response([])
        await SpotAssetContextsReader(transport_deps).get_all()

        assert mock_transport.captured_requests[0].headers["authorization"] == (
            "Bearer test-api-key-123"
        )

    def test_price_fields_are_nullable(self) -> None:
        """A market with no 24h trades SHALL parse with null prices, not fail."""
        from decibel.read._spot_asset_contexts import SpotAssetContext

        context = SpotAssetContext.model_validate(
            {
                **SAMPLE_SPOT_ASSET_CONTEXT,
                "last_price": None,
                "mid": None,
                "prev_day_price": None,
                "high_24h": None,
                "low_24h": None,
            }
        )
        assert context.last_price is None
        assert context.volume_24h_base == 1000.0

    def test_missing_market_addr_raises(self) -> None:
        from decibel.read._spot_asset_contexts import SpotAssetContext

        data = {**SAMPLE_SPOT_ASSET_CONTEXT}
        del data["market_addr"]
        with pytest.raises(ValidationError):
            SpotAssetContext.model_validate(data)


# ---------------------------------------------------------------------------
# SPEC — the `asset_type` query parameter on dual-product endpoints
# ---------------------------------------------------------------------------


class TestAssetTypeQueryParam:
    """Dual-product endpoints SHALL send asset_type=perp by default and omit it for "all"."""

    async def test_open_orders_defaults_to_perp(
        self, transport_deps: ReaderDeps, mock_transport: MockTransport
    ) -> None:
        from decibel.read._user_open_orders import UserOpenOrdersReader

        mock_transport.set_response({"items": [], "total_count": 0})
        await UserOpenOrdersReader(transport_deps).get_by_addr(sub_addr="0xuser")

        params = mock_transport.captured_requests[0].params
        assert params is not None
        assert params["asset_type"] == "perp"
        # The spec names this param `account`, not `user`.
        assert params["account"] == "0xuser"

    async def test_open_orders_spot_filter(
        self, transport_deps: ReaderDeps, mock_transport: MockTransport
    ) -> None:
        from decibel.read._user_open_orders import UserOpenOrdersReader

        mock_transport.set_response({"items": [], "total_count": 0})
        await UserOpenOrdersReader(transport_deps).get_by_addr(sub_addr="0xuser", asset_type="spot")

        params = mock_transport.captured_requests[0].params
        assert params is not None
        assert params["asset_type"] == "spot"

    async def test_all_omits_the_param(
        self, transport_deps: ReaderDeps, mock_transport: MockTransport
    ) -> None:
        """ "all" is an SDK-side concept: the merged view is what the API returns with no filter."""
        from decibel.read._user_open_orders import UserOpenOrdersReader

        mock_transport.set_response({"items": [], "total_count": 0})
        await UserOpenOrdersReader(transport_deps).get_by_addr(sub_addr="0xuser", asset_type="all")

        params = mock_transport.captured_requests[0].params
        assert params is not None
        assert "asset_type" not in params

    async def test_order_history_sends_asset_type(
        self, transport_deps: ReaderDeps, mock_transport: MockTransport
    ) -> None:
        from decibel.read._user_order_history import UserOrderHistoryReader

        mock_transport.set_response({"items": [], "total_count": 0})
        await UserOrderHistoryReader(transport_deps).get_by_addr(
            sub_addr="0xuser", asset_type="spot", limit=10
        )

        req = mock_transport.captured_requests[0]
        assert "/api/v1/order_history" in req.url
        assert req.params == {"account": "0xuser", "limit": "10", "asset_type": "spot"}

    async def test_bulk_orders_sends_asset_type(
        self, transport_deps: ReaderDeps, mock_transport: MockTransport
    ) -> None:
        from decibel.read._user_bulk_orders import UserBulkOrdersReader

        mock_transport.set_response([])
        await UserBulkOrdersReader(transport_deps).get_by_addr(sub_addr="0xuser")

        req = mock_transport.captured_requests[0]
        assert "/api/v1/bulk_orders" in req.url
        assert req.params == {"account": "0xuser", "market": "all", "asset_type": "perp"}

    def test_rows_may_omit_asset_type(self) -> None:
        """Pre-spot API versions omit asset_type entirely; those rows SHALL still parse."""
        order = UserOpenOrder.model_validate(TestOrderDtoValidation.VALID_ORDER)
        assert order.asset_type is None


# ---------------------------------------------------------------------------
# SPEC — GET /api/v1/orders (single-order lookup)
# ---------------------------------------------------------------------------


class TestSingleOrderEndpoint:
    """The point lookup SHALL accept exactly one of order_id / client_order_id."""

    RESPONSE: dict[str, Any] = {
        "status": "Open",
        "details": "",
        "order": {
            "parent": "0xparent",
            "market": "0xmarket",
            "client_order_id": "42",
            "order_id": "1001",
            "status": "Open",
            "order_type": "Limit",
            "trigger_condition": "None",
            "order_direction": "Buy",
            "orig_size": 1.0,
            "remaining_size": 1.0,
            "size_delta": 0.0,
            "price": 100.0,
            "is_buy": True,
            "is_reduce_only": False,
            "details": "",
            "is_tpsl": False,
            "tp_trigger_price": None,
            "tp_limit_price": None,
            "sl_trigger_price": None,
            "sl_limit_price": None,
            "transaction_version": 1,
            "unix_ms": 1699564800000,
        },
    }

    async def test_lookup_by_order_id_omits_asset_type(
        self, transport_deps: ReaderDeps, mock_transport: MockTransport
    ) -> None:
        """Unset asset_type lets the API check perp then fall through to spot."""
        from decibel.read._user_orders import UserOrdersReader

        mock_transport.set_response(self.RESPONSE)
        result = await UserOrdersReader(transport_deps).get_order(
            sub_addr="0xuser", market="0xmarket", order_id="1001"
        )

        req = mock_transport.captured_requests[0]
        assert "/api/v1/orders" in req.url
        assert req.params == {"account": "0xuser", "market": "0xmarket", "order_id": "1001"}
        assert result.order.order_id == "1001"

    async def test_lookup_by_client_order_id(
        self, transport_deps: ReaderDeps, mock_transport: MockTransport
    ) -> None:
        from decibel.read._user_orders import UserOrdersReader

        mock_transport.set_response(self.RESPONSE)
        await UserOrdersReader(transport_deps).get_order(
            sub_addr="0xuser", market="0xmarket", client_order_id="42"
        )

        params = mock_transport.captured_requests[0].params
        assert params is not None
        assert params["client_order_id"] == "42"
        assert "order_id" not in params

    async def test_explicit_asset_type_is_forwarded(
        self, transport_deps: ReaderDeps, mock_transport: MockTransport
    ) -> None:
        from decibel._asset_type import AssetTypeName
        from decibel.read._user_orders import UserOrdersReader

        mock_transport.set_response(self.RESPONSE)
        await UserOrdersReader(transport_deps).get_order(
            sub_addr="0xuser",
            market="0xmarket",
            order_id="1001",
            asset_type=AssetTypeName.SPOT,
        )

        params = mock_transport.captured_requests[0].params
        assert params is not None
        assert params["asset_type"] == "spot"

    async def test_both_ids_rejected_before_any_request(
        self, transport_deps: ReaderDeps, mock_transport: MockTransport
    ) -> None:
        from decibel.read._user_orders import UserOrdersReader

        with pytest.raises(ValueError, match="exactly one"):
            await UserOrdersReader(transport_deps).get_order(
                sub_addr="0xuser", market="0xmarket", order_id="1", client_order_id="2"
            )
        assert mock_transport.captured_requests == []


# ---------------------------------------------------------------------------
# SPEC — GET /api/v1/bulk_order_status and /api/v1/bulk_order_fills
# ---------------------------------------------------------------------------


class TestBulkOrderStatusAndFills:
    BULK_ORDER: dict[str, Any] = {
        "market": "0xmarket",
        "sequence_number": 7,
        "previous_seq_num": 6,
        "bid_prices": [100.0],
        "bid_sizes": [1.0],
        "ask_prices": [101.0],
        "ask_sizes": [1.0],
        "cancelled_bid_prices": [],
        "cancelled_bid_sizes": [],
        "cancelled_ask_prices": [],
        "cancelled_ask_sizes": [],
    }

    async def test_status_endpoint_params(
        self, transport_deps: ReaderDeps, mock_transport: MockTransport
    ) -> None:
        from decibel.read._user_bulk_orders import UserBulkOrdersReader

        mock_transport.set_response(
            {"status": "Placed", "details": "", "bulk_order": self.BULK_ORDER}
        )
        status = await UserBulkOrdersReader(transport_deps).get_status(
            sub_addr="0xuser", market="0xmarket", sequence_number=7
        )

        req = mock_transport.captured_requests[0]
        assert "/api/v1/bulk_order_status" in req.url
        assert req.params == {
            "account": "0xuser",
            "market": "0xmarket",
            "sequence_number": "7",
            "asset_type": "perp",
        }
        assert status.bulk_order.sequence_number == 7

    async def test_fills_endpoint_params(
        self, transport_deps: ReaderDeps, mock_transport: MockTransport
    ) -> None:
        from decibel.read._user_bulk_orders import UserBulkOrdersReader

        mock_transport.set_response({"items": [], "total_count": 0})
        await UserBulkOrdersReader(transport_deps).get_fills(
            sub_addr="0xuser",
            market="0xmarket",
            start_sequence_number=1,
            end_sequence_number=9,
            limit=50,
            offset=10,
            asset_type="all",
        )

        req = mock_transport.captured_requests[0]
        assert "/api/v1/bulk_order_fills" in req.url
        assert req.params == {
            "account": "0xuser",
            "market": "0xmarket",
            "start_sequence_number": "1",
            "end_sequence_number": "9",
            "limit": "50",
            "offset": "10",
        }

    async def test_fills_minimal_params(
        self, transport_deps: ReaderDeps, mock_transport: MockTransport
    ) -> None:
        from decibel.read._user_bulk_orders import UserBulkOrdersReader

        mock_transport.set_response({"items": [], "total_count": 0})
        await UserBulkOrdersReader(transport_deps).get_fills(sub_addr="0xuser")

        assert mock_transport.captured_requests[0].params == {
            "account": "0xuser",
            "asset_type": "perp",
        }


# ---------------------------------------------------------------------------
# SPEC — GET /api/v1/user_fee_rates
# ---------------------------------------------------------------------------


class TestUserFeeRatesEndpoint:
    SCHEDULE: dict[str, Any] = {
        "taker": 0.00034,
        "maker": 0.00011,
        "tiers": {"vip": [], "market_maker": []},
        "referral_discount": 0.0,
    }
    RESPONSE: dict[str, Any] = {
        "account": "0xuser",
        "daily_user_volume": [],
        "fee_schedule": SCHEDULE,
        "user_taker_rate": 0.00034,
        "user_maker_rate": 0.00011,
        "fee_tier": 0,
        "active_referral_discount": 0.0,
    }

    async def test_endpoint_and_params(
        self, transport_deps: ReaderDeps, mock_transport: MockTransport
    ) -> None:
        from decibel.read._user_fees import UserFeesReader

        mock_transport.set_response(self.RESPONSE)
        fees = await UserFeesReader(transport_deps).get_by_addr("0xuser")

        req = mock_transport.captured_requests[0]
        assert "/api/v1/user_fee_rates" in req.url
        assert req.params == {"account": "0xuser"}
        assert fees.fee_tier == 0

    def test_per_product_blocks_are_optional(self) -> None:
        """The perp/spot split is still rolling out; legacy payloads SHALL still parse."""
        from decibel.read._user_fees import UserFees

        fees = UserFees.model_validate(self.RESPONSE)
        assert fees.perp is None
        assert fees.spot is None
        assert fees.volume_weights is None

    def test_cross_product_payload_parses(self) -> None:
        from decibel.read._user_fees import UserFees

        product = {
            "fee_tier": 2,
            "fee_schedule": self.SCHEDULE,
            "user_taker_rate": 0.0003,
            "user_maker_rate": 0.0001,
            "daily_user_volume": [],
            "total_window_volume_usd": "1000000",
            "active_referral_discount": 0.0,
        }
        fees = UserFees.model_validate(
            {
                **self.RESPONSE,
                "perp": product,
                # Spot's tier comes from weighted cross-product volume, so it can differ.
                "spot": {**product, "fee_tier": 1},
                "weighted_volume_usd": "1500000",
                "volume_weights": {"perp": 100.0, "spot": 50.0},
            }
        )
        assert fees.perp is not None
        assert fees.spot is not None
        assert fees.perp.fee_tier == 2
        assert fees.spot.fee_tier == 1
        assert fees.volume_weights is not None
        assert fees.volume_weights.spot == 50.0


# ---------------------------------------------------------------------------
# SPEC — points, streaks and campaign endpoints
# ---------------------------------------------------------------------------


class TestPointsEndpoints:
    async def test_tier_endpoint(
        self, transport_deps: ReaderDeps, mock_transport: MockTransport
    ) -> None:
        from decibel.read._tier import TierReader

        mock_transport.set_response({"owner": "0xowner", "total_amps": 5.0, "tiers": []})
        await TierReader(transport_deps).get_by_owner("0xowner")

        req = mock_transport.captured_requests[0]
        assert "/api/v1/points/tier" in req.url
        assert req.params == {"owner": "0xowner"}

    async def test_global_stats_endpoint(
        self, transport_deps: ReaderDeps, mock_transport: MockTransport
    ) -> None:
        from decibel.read._global_points_stats import GlobalPointsStatsReader

        mock_transport.set_response({"total_users": 10, "total_amps_distributed": 1.5})
        stats = await GlobalPointsStatsReader(transport_deps).get()

        req = mock_transport.captured_requests[0]
        assert req.url.endswith("/api/v1/points/global")
        assert req.params is None
        assert stats.total_users == 10

    async def test_streaks_endpoint_parses_camel_case(
        self, transport_deps: ReaderDeps, mock_transport: MockTransport
    ) -> None:
        """The streaks route is the one points endpoint serving camelCase keys."""
        from decibel.read._streaks import StreaksReader

        mock_transport.set_response(
            {
                "owner": "0xowner",
                "currentStreak": 5,
                "streakIpoints": 12.5,
                "streakAmpsEstimate": 3.0,
                "graceDaysAvailable": 2,
                "graceDaysUsed": 1,
                "qualifyingDates": ["2026-08-16"],
            }
        )
        streaks = await StreaksReader(transport_deps).get_by_owner("0xowner")

        req = mock_transport.captured_requests[0]
        assert "/api/v1/streaks/account" in req.url
        assert req.params == {"owner": "0xowner"}
        assert streaks.current_streak == 5
        assert streaks.qualifying_dates == ["2026-08-16"]


class TestCampaignAndWithdrawQueueEndpoints:
    async def test_active_campaigns_endpoint(
        self, transport_deps: ReaderDeps, mock_transport: MockTransport
    ) -> None:
        from decibel.read._campaigns import CampaignsReader

        mock_transport.set_response([])
        await CampaignsReader(transport_deps).get_active()

        req = mock_transport.captured_requests[0]
        assert req.url.endswith("/api/v1/campaigns/active")
        assert req.params is None

    async def test_campaign_summary_pagination(
        self, transport_deps: ReaderDeps, mock_transport: MockTransport
    ) -> None:
        from decibel.read._campaigns import CampaignsReader

        mock_transport.set_response(
            {
                "lifetime_earned": 0.0,
                "ready_to_claim": 0.0,
                "total_claimed": 0.0,
                "breakdown_by_type": [],
                "claims": [],
                "year_to_date": 0.0,
                "weekly_wow_bps": 0.0,
                "weekly_breakdown": [],
                "total_claims": 0,
            }
        )
        await CampaignsReader(transport_deps).get_summary(
            account_address="0xuser", limit=25, offset=50
        )

        req = mock_transport.captured_requests[0]
        assert "/api/v1/campaigns/account" in req.url
        assert req.params == {"account": "0xuser", "limit": "25", "offset": "50"}

    async def test_referral_code_is_url_encoded(
        self, transport_deps: ReaderDeps, mock_transport: MockTransport
    ) -> None:
        from decibel.read._referrals import ReferralsReader

        mock_transport.set_response(
            {"referral_code": "a/b c", "is_valid": False, "is_active": False}
        )
        await ReferralsReader(transport_deps).validate_code("a/b c")

        assert "/api/v1/referrals/code/a%2Fb%20c" in mock_transport.captured_requests[0].url

    async def test_withdraw_queue_endpoint(
        self, transport_deps: ReaderDeps, mock_transport: MockTransport
    ) -> None:
        from decibel.read._withdraw_queue import WithdrawQueueReader

        mock_transport.set_response({"items": [], "total_count": 0})
        await WithdrawQueueReader(transport_deps).get_by_addr(
            sub_addr="0xuser", status="Queued", limit=5
        )

        req = mock_transport.captured_requests[0]
        assert "/api/v1/withdraw_queue" in req.url
        assert req.params == {"account": "0xuser", "status": "Queued", "limit": "5"}


# ---------------------------------------------------------------------------
# Model validation: account overview spot / secondary-collateral blocks
# ---------------------------------------------------------------------------


class TestAccountOverviewSpotBlocks:
    """The spot and secondary-collateral blocks SHALL be optional and parse when present."""

    def test_spot_block_absent_by_default(self) -> None:
        overview = AccountOverview.model_validate(TestAccountOverviewValidation.MINIMAL_VALID)
        assert overview.spot is None
        assert overview.secondary_collateral is None
        assert overview.cross_available_to_trade is None

    def test_spot_block_parses(self) -> None:
        overview = AccountOverview.model_validate(
            {
                **TestAccountOverviewValidation.MINIMAL_VALID,
                "spot": {
                    "positions": [
                        {
                            "asset_addr": "0xa",
                            "asset_symbol": "APT",
                            "amount": 10.0,
                            "usd_value": 125.0,
                            "entry_notional_usd": 120.0,
                            "unrealized_pnl_usd": 5.0,
                        }
                    ],
                    "total_usd": 125.0,
                    "in_flight_orders": [
                        {
                            "market_addr": "0xmarket",
                            "order_id": "1",
                            "is_bid": True,
                            "reserved_asset": "0xusdc",
                            "reserved_amount": 50.0,
                            "reserved_usd_value": 50.0,
                        }
                    ],
                },
                "cross_available_to_trade": 42.0,
            }
        )
        assert overview.spot is not None
        assert overview.spot.positions[0].asset_symbol == "APT"
        assert overview.spot.in_flight_orders[0].is_bid is True
        # metrics is absent until the subaccount has traded spot.
        assert overview.spot.metrics is None
        assert overview.cross_available_to_trade == 42.0

    def test_secondary_collateral_parses(self) -> None:
        overview = AccountOverview.model_validate(
            {
                **TestAccountOverviewValidation.MINIMAL_VALID,
                "secondary_collateral": [
                    {
                        "asset_type": "0xdlp",
                        "amount": 3.0,
                        "value_in_usdc": 30.0,
                        "nav_per_unit": 11.0,
                        "haircut_bps": 900.0,
                        "withdrawable_amount": 1.0,
                    }
                ],
            }
        )
        assert overview.secondary_collateral is not None
        assert overview.secondary_collateral[0].haircut_bps == 900.0
