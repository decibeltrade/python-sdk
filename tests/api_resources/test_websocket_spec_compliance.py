"""Behavioral tests verifying the SDK matches the WebSocket API specification.

These tests verify:
1. Subscribe/unsubscribe message JSON format (SPEC-WEBSOCKET Section 2)
2. Actual reader topic construction matches spec (Section 9.3)
3. Data message parsing into Pydantic models (Sections 3-7)
4. Negative cases — bad data is rejected
5. Connection protocol details (Section 1)
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from decibel._constants import TESTNET_CONFIG
from decibel._utils import get_market_addr
from decibel.read._base import ReaderDeps
from decibel.read._ws import DecibelWsSubscription

# ---------------------------------------------------------------------------
# SPEC Section 1 — Connection Protocol
# ---------------------------------------------------------------------------


class TestConnectionProtocol:
    """SPEC-WEBSOCKET.md Section 1: Connection Protocol."""

    def test_testnet_ws_url_uses_wss(self) -> None:
        """Server URL SHALL use wss:// protocol."""
        assert TESTNET_CONFIG.trading_ws_url.startswith("wss://")

    def test_testnet_ws_url_ends_with_ws_path(self) -> None:
        """Server path SHALL end with /ws."""
        assert TESTNET_CONFIG.trading_ws_url.endswith("/ws")


# ---------------------------------------------------------------------------
# SPEC Section 2 — Subscribe/Unsubscribe Messages
# ---------------------------------------------------------------------------


class TestSubscriptionMessages:
    """SPEC-WEBSOCKET.md Section 2: Subscription Protocol message format."""

    @pytest.fixture
    def ws(self) -> DecibelWsSubscription:
        return DecibelWsSubscription(TESTNET_CONFIG, api_key="test-key")

    def test_subscribe_message_has_method_and_topic(self, ws: DecibelWsSubscription) -> None:
        """Subscribe SHALL produce {"method": "subscribe", "topic": "..."}."""
        msg = json.loads(ws._get_subscribe_message("all_market_prices"))
        assert msg["method"] == "subscribe"
        assert msg["topic"] == "all_market_prices"
        assert set(msg.keys()) == {"method", "topic"}

    def test_unsubscribe_message_has_method_and_topic(self, ws: DecibelWsSubscription) -> None:
        """Unsubscribe SHALL produce {"method": "unsubscribe", "topic": "..."}."""
        msg = json.loads(ws._get_unsubscribe_message("all_market_prices"))
        assert msg["method"] == "unsubscribe"
        assert msg["topic"] == "all_market_prices"

    def test_subscribe_preserves_parameterized_topic(self, ws: DecibelWsSubscription) -> None:
        """Topic string with parameters SHALL be preserved verbatim."""
        topic = "user_open_orders:0x1234abcd"
        msg = json.loads(ws._get_subscribe_message(topic))
        assert msg["topic"] == topic


# ---------------------------------------------------------------------------
# SPEC Section 9.3 — Topic strings constructed by actual readers
# ---------------------------------------------------------------------------


class TestReaderTopicConstruction:
    """Verify actual readers construct correct topic strings per spec Section 9.3."""

    @pytest.fixture
    def mock_ws(self) -> MagicMock:
        """Mock WS that captures subscribe calls."""
        ws = MagicMock(spec=DecibelWsSubscription)
        ws.subscribe = MagicMock(return_value=lambda: None)
        return ws

    @pytest.fixture
    def deps(self, mock_ws: MagicMock) -> ReaderDeps:
        return ReaderDeps(
            config=TESTNET_CONFIG,
            ws=mock_ws,
            aptos=AsyncMock(),
            api_key="k",
        )

    def test_market_price_subscribe_topic(self, deps: ReaderDeps, mock_ws: MagicMock) -> None:
        """MarketPricesReader SHALL subscribe to 'market_price:{addr}'."""
        from decibel.read._market_prices import MarketPricesReader

        reader = MarketPricesReader(deps)
        reader.subscribe_by_address("0xmarket123", lambda _: None)

        mock_ws.subscribe.assert_called_once()
        topic = mock_ws.subscribe.call_args[0][0]
        assert topic == "market_price:0xmarket123"

    def test_all_market_prices_subscribe_topic(self, deps: ReaderDeps, mock_ws: MagicMock) -> None:
        """subscribe_all SHALL use topic 'all_market_prices' (no parameters)."""
        from decibel.read._market_prices import MarketPricesReader

        reader = MarketPricesReader(deps)
        reader.subscribe_all(lambda _: None)

        topic = mock_ws.subscribe.call_args[0][0]
        assert topic == "all_market_prices"

    def test_market_depth_subscribe_topic_with_aggregation(
        self, deps: ReaderDeps, mock_ws: MagicMock
    ) -> None:
        """MarketDepthReader SHALL subscribe to 'depth:{addr}:{aggregation}'."""
        from decibel.read._market_depth import MarketDepthReader

        reader = MarketDepthReader(deps)
        reader.subscribe_by_name("BTC-PERP", 10, lambda _: None)

        topic = mock_ws.subscribe.call_args[0][0]
        expected_addr = get_market_addr("BTC-PERP", TESTNET_CONFIG.deployment.perp_engine_global)
        assert topic == f"depth:{expected_addr}:10"

    def test_user_positions_subscribe_topic(self, deps: ReaderDeps, mock_ws: MagicMock) -> None:
        """UserPositionsReader SHALL subscribe to 'account_positions:{addr}'."""
        from decibel.read._user_positions import UserPositionsReader

        reader = UserPositionsReader(deps)
        reader.subscribe_by_addr("0xuser456", lambda _: None)

        topic = mock_ws.subscribe.call_args[0][0]
        assert topic == "account_positions:0xuser456"

    def test_order_updates_subscribe_topic(self, deps: ReaderDeps, mock_ws: MagicMock) -> None:
        """UserOrderHistoryReader SHALL subscribe to 'order_updates:{addr}'."""
        from decibel.read._user_order_history import UserOrderHistoryReader

        reader = UserOrderHistoryReader(deps)
        reader.subscribe_by_addr("0xuser789", lambda _: None)

        topic = mock_ws.subscribe.call_args[0][0]
        assert topic == "order_updates:0xuser789"

    def test_notifications_subscribe_topic(self, deps: ReaderDeps, mock_ws: MagicMock) -> None:
        """UserNotificationsReader SHALL subscribe to 'notifications:{addr}'."""
        from decibel.read._user_notifications import UserNotificationsReader

        reader = UserNotificationsReader(deps)
        reader.subscribe_by_addr("0xnotif", lambda _: None)

        topic = mock_ws.subscribe.call_args[0][0]
        assert topic == "notifications:0xnotif"

    def test_user_active_twaps_subscribe_topic(self, deps: ReaderDeps, mock_ws: MagicMock) -> None:
        """UserActiveTwapsReader SHALL subscribe to 'user_active_twaps:{addr}'."""
        from decibel.read._user_active_twaps import UserActiveTwapsReader

        reader = UserActiveTwapsReader(deps)
        reader.subscribe_by_addr("0xtwap", lambda _: None)

        topic = mock_ws.subscribe.call_args[0][0]
        assert topic == "user_active_twaps:0xtwap"

    def test_candlestick_subscribe_topic(self, deps: ReaderDeps, mock_ws: MagicMock) -> None:
        """CandlesticksReader SHALL subscribe to 'market_candlestick:{addr}:{interval}'."""
        from decibel.read._candlesticks import CandlestickInterval, CandlesticksReader

        reader = CandlesticksReader(deps)
        reader.subscribe_by_name("ETH-PERP", CandlestickInterval.ONE_HOUR, lambda _: None)

        topic = mock_ws.subscribe.call_args[0][0]
        expected_addr = get_market_addr("ETH-PERP", TESTNET_CONFIG.deployment.perp_engine_global)
        assert topic == f"market_candlestick:{expected_addr}:1h"


# ---------------------------------------------------------------------------
# SPEC Section 3 — Market data WS message parsing
# ---------------------------------------------------------------------------


class TestMarketDataMessages:
    """Verify WS market data messages parse correctly."""

    def test_all_market_prices_message(self) -> None:
        """AllMarketPricesWsMessage SHALL parse prices array."""
        from decibel.read._market_prices import AllMarketPricesWsMessage

        msg = AllMarketPricesWsMessage.model_validate(
            {
                "prices": [
                    {
                        "market": "0x" + "a" * 64,
                        "oracle_px": 100.0,
                        "mark_px": 99.0,
                        "mid_px": 99.5,
                        "funding_rate_bps": 1.0,
                        "is_funding_positive": True,
                        "transaction_unix_ms": 1000,
                        "open_interest": 50.0,
                    },
                ]
            }
        )
        assert len(msg.prices) == 1
        assert msg.prices[0].oracle_px == 100.0

    def test_all_market_prices_empty_array(self) -> None:
        """Empty prices array SHALL be valid."""
        from decibel.read._market_prices import AllMarketPricesWsMessage

        msg = AllMarketPricesWsMessage.model_validate({"prices": []})
        assert msg.prices == []

    def test_all_market_prices_missing_prices_field_raises(self) -> None:
        """Missing 'prices' key SHALL raise ValidationError."""
        from decibel.read._market_prices import AllMarketPricesWsMessage

        with pytest.raises(ValidationError):
            AllMarketPricesWsMessage.model_validate({"wrong_key": []})

    def test_market_depth_message(self) -> None:
        """MarketDepth SHALL parse bids/asks arrays of {price, size}."""
        from decibel.read._market_depth import MarketDepth

        depth = MarketDepth.model_validate(
            {
                "market": "0x" + "a" * 64,
                "unix_ms": 1000,
                "bids": [{"price": 100.0, "size": 10.0}],
                "asks": [{"price": 101.0, "size": 5.0}],
            }
        )
        assert depth.bids[0].price == 100.0
        assert depth.asks[0].size == 5.0

    def test_market_depth_empty_book(self) -> None:
        """Empty bids/asks SHALL be valid (thin market)."""
        from decibel.read._market_depth import MarketDepth

        depth = MarketDepth.model_validate(
            {
                "market": "0x" + "a" * 64,
                "unix_ms": 1000,
                "bids": [],
                "asks": [],
            }
        )
        assert depth.bids == []
        assert depth.asks == []


# ---------------------------------------------------------------------------
# SPEC Section 4 — Account WS message parsing
# ---------------------------------------------------------------------------


class TestAccountMessages:
    """Verify WS account data messages parse correctly."""

    def test_user_positions_message(self) -> None:
        """UserPositionsWsMessage SHALL parse positions array."""
        from decibel.read._user_positions import UserPositionsWsMessage

        msg = UserPositionsWsMessage.model_validate(
            {
                "positions": [
                    {
                        "market": "0x" + "a" * 64,
                        "user": "0x" + "b" * 64,
                        "size": 2.5,
                        "user_leverage": 10,
                        "entry_price": 100.0,
                        "is_isolated": False,
                        "is_deleted": False,
                        "unrealized_funding": -1.0,
                        "estimated_liquidation_price": 50.0,
                        "transaction_version": 1,
                        "has_fixed_sized_tpsls": False,
                        "tp_order_id": None,
                        "tp_trigger_price": None,
                        "tp_limit_price": None,
                        "sl_order_id": None,
                        "sl_trigger_price": None,
                        "sl_limit_price": None,
                    }
                ]
            }
        )
        assert len(msg.positions) == 1
        assert msg.positions[0].size == 2.5

    def test_user_open_orders_message(self) -> None:
        """UserOpenOrdersWsMessage SHALL parse orders array."""
        from decibel.read._user_open_orders import UserOpenOrdersWsMessage

        msg = UserOpenOrdersWsMessage.model_validate(
            {
                "orders": [
                    {
                        "parent": "0x" + "0" * 64,
                        "market": "0x" + "a" * 64,
                        "order_id": "123",
                        "client_order_id": "c1",
                        "is_buy": True,
                        "is_tpsl": False,
                        "details": "",
                        "transaction_version": 1,
                        "unix_ms": 1000,
                        "tp_trigger_price": None,
                        "tp_limit_price": None,
                        "sl_trigger_price": None,
                        "sl_limit_price": None,
                        "orig_size": 1.0,
                        "remaining_size": 1.0,
                        "size_delta": None,
                        "price": 100.0,
                    }
                ]
            }
        )
        assert msg.orders[0].order_id == "123"

    def test_order_update_nested_structure(self) -> None:
        """OrderUpdate WS message SHALL have nested {status, details, order} structure."""
        from decibel.read._user_order_history import UserOrdersWsMessage

        msg = UserOrdersWsMessage.model_validate(
            {
                "order": {
                    "status": "Filled",
                    "details": "",
                    "order": {
                        "parent": "0x" + "0" * 64,
                        "market": "0x" + "a" * 64,
                        "client_order_id": "c1",
                        "order_id": "456",
                        "status": "Filled",
                        "order_type": "Market",
                        "trigger_condition": "None",
                        "order_direction": "Close Short",
                        "orig_size": 2.0,
                        "remaining_size": 0.0,
                        "size_delta": None,
                        "price": 100.0,
                        "is_buy": False,
                        "is_reduce_only": False,
                        "is_tpsl": False,
                        "details": "",
                        "tp_order_id": None,
                        "tp_trigger_price": None,
                        "tp_limit_price": None,
                        "sl_order_id": None,
                        "sl_trigger_price": None,
                        "sl_limit_price": None,
                        "transaction_version": 1,
                        "unix_ms": 1000,
                    },
                }
            }
        )
        assert msg.order.status == "Filled"
        assert msg.order.order.remaining_size == 0.0


# ---------------------------------------------------------------------------
# SPEC Section 7.1 — NotificationType enum completeness
# ---------------------------------------------------------------------------


class TestNotificationTypes:
    """SPEC-WEBSOCKET.md Section 7.1: Notification types."""

    def test_all_spec_notification_types_exist_in_enum(self) -> None:
        """SDK NotificationType enum SHALL contain all values from the spec."""
        from decibel.read._user_notifications import NotificationType

        spec_types = [
            "MarketOrderPlaced",
            "LimitOrderPlaced",
            "StopMarketOrderPlaced",
            "StopMarketOrderTriggered",
            "StopLimitOrderPlaced",
            "StopLimitOrderTriggered",
            "OrderPartiallyFilled",
            "OrderFilled",
            "OrderSizeReduced",
            "OrderCancelled",
            "OrderRejected",
            "OrderErrored",
            "TwapOrderPlaced",
            "TwapOrderTriggered",
            "TwapOrderCompleted",
            "TwapOrderCancelled",
            "TwapOrderErrored",
            "AccountDeposit",
            "AccountWithdrawal",
            "TpSlSet",
            "TpHit",
            "SlHit",
            "TpCancelled",
            "SlCancelled",
        ]
        enum_values = {e.value for e in NotificationType}
        for expected in spec_types:
            assert expected in enum_values, f"NotificationType missing: {expected}"


# ---------------------------------------------------------------------------
# SPEC Section 9.2 — BigInt and JSON parsing
# ---------------------------------------------------------------------------


class TestWsMessageParsing:
    """Verify _parse_message handles data messages and rejects non-data ones."""

    def test_data_message_extracts_topic(self) -> None:
        """Messages with 'topic' field SHALL return (topic, data) tuple."""
        ws = DecibelWsSubscription(TESTNET_CONFIG, api_key="test")
        raw = json.dumps({"topic": "all_market_prices", "prices": []})
        result = ws._parse_message(raw)
        assert result is not None
        topic, data = result
        assert topic == "all_market_prices"
        assert "prices" in data

    def test_non_topic_message_raises(self) -> None:
        """Messages without 'topic' field SHALL raise ValueError."""
        ws = DecibelWsSubscription(TESTNET_CONFIG, api_key="test")
        raw = json.dumps({"success": True, "message": "Subscribed"})
        with pytest.raises(ValueError, match="missing topic field"):
            ws._parse_message(raw)

    def test_invalid_json_raises(self) -> None:
        """Malformed JSON SHALL raise ValueError."""
        ws = DecibelWsSubscription(TESTNET_CONFIG, api_key="test")
        with pytest.raises(ValueError, match="failed to parse JSON"):
            ws._parse_message("not valid json{{{")

    def test_bigint_in_message(self) -> None:
        """Messages with $bigint values SHALL parse to Python int."""
        ws = DecibelWsSubscription(TESTNET_CONFIG, api_key="test")
        raw = json.dumps(
            {
                "topic": "test_topic",
                "event_uid": {"$bigint": "999999999999999999999"},
            }
        )
        result = ws._parse_message(raw)
        assert result is not None
        _, data = result
        assert data["event_uid"] == 999999999999999999999


# ---------------------------------------------------------------------------
# SPEC: Market depth aggregation levels
# ---------------------------------------------------------------------------


class TestMarketDepthAggregation:
    """Verify MarketDepthReader exposes correct aggregation levels."""

    def test_get_aggregation_sizes_returns_spec_values(self) -> None:
        """get_aggregation_sizes SHALL return (1, 2, 5, 10, 100, 1000)."""
        from decibel.read._market_depth import MarketDepthReader

        reader = MarketDepthReader.__new__(MarketDepthReader)
        sizes = reader.get_aggregation_sizes()
        assert sizes == (1, 2, 5, 10, 100, 1000)
