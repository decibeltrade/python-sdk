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
