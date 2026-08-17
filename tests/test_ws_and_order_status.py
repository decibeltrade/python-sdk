from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from decibel._constants import (
    CompatVersion,
    DecibelConfig,
    Deployment,
    Network,
)
from decibel._gas_price_manager import (
    GasPriceManager,
    GasPriceManagerOptions,
    GasPriceManagerSync,
    _build_auth_headers,
)
from decibel._order_status import OrderStatus, OrderStatusClient
from decibel.read._ws import DecibelWsSubscription

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_DEPLOYMENT = Deployment(
    package="0xabc",
    usdc="0xusdc",
    testc="0xtestc",
    perp_engine_global="0xperp",
    spot_engine_global="0xspot",
)


@pytest.fixture()
def config() -> DecibelConfig:
    return DecibelConfig(
        network=Network.TESTNET,
        fullnode_url="https://fullnode.example.com",
        trading_http_url="https://trading.example.com",
        trading_ws_url="wss://ws.example.com",
        gas_station_url=None,
        gas_station_api_key=None,
        deployment=_DEPLOYMENT,
        chain_id=1,
        compat_version=CompatVersion.V0_4,
    )


SAMPLE_ORDER_STATUS = {
    "parent": "0xparent",
    "market": "0xmarket",
    "order_id": "order-1",
    "status": "filled",
    "orig_size": 100.0,
    "remaining_size": 0.0,
    "size_delta": 100.0,
    "price": 50.5,
    "is_buy": True,
    "details": "ok",
    "transaction_version": 42,
    "unix_ms": 1700000000000,
}

# ===================================================================
# WebSocket (DecibelWsSubscription) tests
# ===================================================================


class TestWsSubscribe:
    """subscribe() stores callbacks, returns unsubscribe, auto-opens."""

    async def test_subscribe_stores_callback_and_returns_unsubscribe(
        self, config: DecibelConfig
    ) -> None:
        ws = DecibelWsSubscription(config)
        callback = MagicMock()

        with patch.object(ws, "_open", new_callable=AsyncMock):
            unsub = ws.subscribe("topic.a", MagicMock, callback)

        assert "topic.a" in ws._subscriptions
        assert len(ws._subscriptions["topic.a"]) == 1
        assert callable(unsub)

    async def test_subscribe_auto_opens_on_first_subscribe(self, config: DecibelConfig) -> None:
        ws = DecibelWsSubscription(config)
        assert ws._ws is None

        with patch.object(ws, "_open", new_callable=AsyncMock) as mock_open:
            ws.subscribe("topic.a", MagicMock, MagicMock())
            # _open is scheduled via asyncio.create_task; yield
            # to let the task execute.
            await asyncio.sleep(0)

        mock_open.assert_awaited_once()

    async def test_subscribe_cancels_close_timer(self, config: DecibelConfig) -> None:
        ws = DecibelWsSubscription(config)
        timer_task = MagicMock()
        ws._close_timer_task = timer_task

        with patch.object(ws, "_open", new_callable=AsyncMock):
            ws.subscribe("topic.b", MagicMock, MagicMock())

        timer_task.cancel.assert_called_once()
        assert ws._close_timer_task is None

    async def test_subscribe_sends_sub_msg_when_ws_open(self, config: DecibelConfig) -> None:
        ws = DecibelWsSubscription(config)
        mock_conn = AsyncMock()
        ws._ws = mock_conn

        ws.subscribe("topic.new", MagicMock, MagicMock())

        # The subscribe message is sent via asyncio.create_task
        await asyncio.sleep(0)
        mock_conn.send.assert_awaited()


class TestWsUnsubscribe:
    """_unsubscribe_listener / _unsubscribe_topic cleanup."""

    async def test_unsubscribe_removes_listener(self, config: DecibelConfig) -> None:
        ws = DecibelWsSubscription(config)
        callback = MagicMock()

        with patch.object(ws, "_open", new_callable=AsyncMock):
            unsub = ws.subscribe("t", MagicMock, callback)

        assert len(ws._subscriptions["t"]) == 1
        with patch.object(ws, "_delayed_close", new_callable=AsyncMock):
            unsub()
        assert "t" not in ws._subscriptions

    async def test_unsubscribe_keeps_other_listeners(self, config: DecibelConfig) -> None:
        ws = DecibelWsSubscription(config)

        with patch.object(ws, "_open", new_callable=AsyncMock):
            unsub1 = ws.subscribe("t", MagicMock, MagicMock())
            _ = ws.subscribe("t", MagicMock, MagicMock())

        assert len(ws._subscriptions["t"]) == 2
        unsub1()
        assert len(ws._subscriptions["t"]) == 1

    async def test_unsubscribe_topic_sends_unsub_message(self, config: DecibelConfig) -> None:
        ws = DecibelWsSubscription(config)
        mock_conn = AsyncMock()
        ws._ws = mock_conn

        with patch.object(ws, "_open", new_callable=AsyncMock):
            unsub = ws.subscribe("t", MagicMock, MagicMock())

        with patch.object(ws, "_delayed_close", new_callable=AsyncMock):
            unsub()
        # unsubscribe message sent via create_task
        await asyncio.sleep(0)
        mock_conn.send.assert_awaited()


class TestWsReset:
    """reset() and _reset_topic()."""

    async def test_reset_sends_unsub_then_sub(self, config: DecibelConfig) -> None:
        ws = DecibelWsSubscription(config)
        mock_conn = AsyncMock()
        ws._ws = mock_conn
        ws._subscriptions["t"] = {MagicMock()}

        ws.reset("t")
        # Let the task run
        await asyncio.sleep(0)

        calls = mock_conn.send.await_args_list
        assert len(calls) == 2
        assert "unsubscribe" in calls[0].args[0]
        assert "subscribe" in calls[1].args[0]

    async def test_reset_noop_for_unknown_topic(self, config: DecibelConfig) -> None:
        ws = DecibelWsSubscription(config)
        mock_conn = AsyncMock()
        ws._ws = mock_conn
        ws.reset("unknown")
        await asyncio.sleep(0)
        mock_conn.send.assert_not_awaited()


class TestWsReadyState:
    """ready_state() returns correct integers."""

    def test_closed_when_no_ws(self, config: DecibelConfig) -> None:
        ws = DecibelWsSubscription(config)
        assert ws.ready_state() == 3

    def test_open_state(self, config: DecibelConfig) -> None:
        ws = DecibelWsSubscription(config)
        mock_conn = MagicMock()
        mock_conn.state.name = "OPEN"
        ws._ws = mock_conn
        assert ws.ready_state() == 1

    def test_closing_state(self, config: DecibelConfig) -> None:
        ws = DecibelWsSubscription(config)
        mock_conn = MagicMock()
        mock_conn.state.name = "CLOSING"
        ws._ws = mock_conn
        assert ws.ready_state() == 2

    def test_connecting_state(self, config: DecibelConfig) -> None:
        ws = DecibelWsSubscription(config)
        mock_conn = MagicMock()
        mock_conn.state.name = "CONNECTING"
        ws._ws = mock_conn
        assert ws.ready_state() == 0


class TestWsScheduleReconnect:
    """_schedule_reconnect exponential backoff."""

    async def test_backoff_increases(self, config: DecibelConfig) -> None:
        ws = DecibelWsSubscription(config)
        ws._subscriptions["t"] = {MagicMock()}

        with (
            patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
            patch.object(ws, "_open", new_callable=AsyncMock),
        ):
            ws._reconnect_attempts = 0
            await ws._schedule_reconnect()
            # 1.5^0 = 1.0
            mock_sleep.assert_awaited_once_with(1.0)

        with (
            patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
            patch.object(ws, "_open", new_callable=AsyncMock),
        ):
            # attempts was incremented to 1 by the first call
            await ws._schedule_reconnect()
            # 1.5^1 = 1.5
            mock_sleep.assert_awaited_once_with(1.5)

    async def test_backoff_capped_at_60(self, config: DecibelConfig) -> None:
        ws = DecibelWsSubscription(config)
        ws._subscriptions["t"] = {MagicMock()}
        ws._reconnect_attempts = 100

        with (
            patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
            patch.object(ws, "_open", new_callable=AsyncMock),
        ):
            await ws._schedule_reconnect()
            mock_sleep.assert_awaited_once_with(60.0)

    async def test_no_reconnect_without_subscriptions(self, config: DecibelConfig) -> None:
        ws = DecibelWsSubscription(config)

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await ws._schedule_reconnect()
            mock_sleep.assert_not_awaited()


# ===================================================================
# OrderStatusClient tests
# ===================================================================


class TestParseOrderStatusType:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("acknowledged", "Acknowledged"),
            ("ACKNOWLEDGED", "Acknowledged"),
            ("order_acknowledged", "Acknowledged"),
            ("filled", "Filled"),
            ("FILLED", "Filled"),
            ("partially_filled", "Filled"),
            ("cancelled", "Cancelled"),
            ("Cancelled", "Cancelled"),
            ("rejected", "Rejected"),
            ("REJECTED", "Rejected"),
            ("pending", "Unknown"),
            ("", "Unknown"),
            (None, "Unknown"),
        ],
    )
    def test_parse(self, raw: str | None, expected: str) -> None:
        assert OrderStatusClient.parse_order_status_type(raw) == expected


class TestOrderStatusHelpers:
    @pytest.mark.parametrize(
        ("status", "expected"),
        [
            ("filled", True),
            ("cancelled", False),
            ("rejected", False),
            ("acknowledged", False),
            (None, False),
        ],
    )
    def test_is_success(self, status: str | None, expected: bool) -> None:
        assert OrderStatusClient.is_success_status(status) is expected

    @pytest.mark.parametrize(
        ("status", "expected"),
        [
            ("filled", False),
            ("cancelled", True),
            ("rejected", True),
            ("acknowledged", False),
            (None, False),
        ],
    )
    def test_is_failure(self, status: str | None, expected: bool) -> None:
        assert OrderStatusClient.is_failure_status(status) is expected

    @pytest.mark.parametrize(
        ("status", "expected"),
        [
            ("filled", True),
            ("cancelled", True),
            ("rejected", True),
            ("acknowledged", False),
            (None, False),
        ],
    )
    def test_is_final(self, status: str | None, expected: bool) -> None:
        assert OrderStatusClient.is_final_status(status) is expected


class TestGetOrderStatus:
    async def test_async_returns_parsed_order(self, config: DecibelConfig) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_response.json.return_value = SAMPLE_ORDER_STATUS

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get.return_value = mock_response

        client = OrderStatusClient(config)
        result = await client.get_order_status("order-1", "0xmarket", "0xuser", client=mock_client)

        assert isinstance(result, OrderStatus)
        assert result.order_id == "order-1"
        assert result.status == "filled"
        assert result.price == 50.5

    async def test_async_returns_none_on_404(self, config: DecibelConfig) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.is_success = False

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get.return_value = mock_response

        client = OrderStatusClient(config)
        result = await client.get_order_status("order-1", "0xmarket", "0xuser", client=mock_client)
        assert result is None

    async def test_async_returns_none_on_error(self, config: DecibelConfig) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.is_success = False
        mock_response.text = "Internal Server Error"
        mock_response.reason_phrase = "Internal Server Error"

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get.return_value = mock_response

        client = OrderStatusClient(config)
        result = await client.get_order_status("order-1", "0xmarket", "0xuser", client=mock_client)
        # FetchError is caught and logged, returns None
        assert result is None

    def test_sync_returns_parsed_order(self, config: DecibelConfig) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_response.json.return_value = SAMPLE_ORDER_STATUS

        mock_client = MagicMock(spec=httpx.Client)
        mock_client.get.return_value = mock_response

        client = OrderStatusClient(config)
        result = client.get_order_status_sync("order-1", "0xmarket", "0xuser", client=mock_client)

        assert isinstance(result, OrderStatus)
        assert result.order_id == "order-1"

    def test_sync_returns_none_on_404(self, config: DecibelConfig) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.is_success = False

        mock_client = MagicMock(spec=httpx.Client)
        mock_client.get.return_value = mock_response

        client = OrderStatusClient(config)
        result = client.get_order_status_sync("order-1", "0xmarket", "0xuser", client=mock_client)
        assert result is None

    def test_sync_returns_none_on_error(self, config: DecibelConfig) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.is_success = False
        mock_response.text = "Internal Server Error"
        mock_response.reason_phrase = "Internal Server Error"

        mock_client = MagicMock(spec=httpx.Client)
        mock_client.get.return_value = mock_response

        client = OrderStatusClient(config)
        result = client.get_order_status_sync("order-1", "0xmarket", "0xuser", client=mock_client)
        assert result is None


# ===================================================================
# GasPriceManager tests
# ===================================================================


class TestBuildAuthHeaders:
    def test_with_api_key(self) -> None:
        assert _build_auth_headers("my-key") == {"x-api-key": "my-key"}

    def test_without_api_key(self) -> None:
        assert _build_auth_headers(None) == {}

    def test_with_empty_string(self) -> None:
        assert _build_auth_headers("") == {}


class TestGasPriceManagerAsync:
    async def test_get_gas_price_returns_none_initially(self, config: DecibelConfig) -> None:
        mgr = GasPriceManager(config)
        assert mgr.get_gas_price() is None

    async def test_fetch_gas_price_estimation(self, config: DecibelConfig) -> None:
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.json.return_value = {"gas_estimate": 100}

        with patch("decibel._gas_price_manager.httpx.AsyncClient") as mock_cls:
            ctx = AsyncMock()
            ctx.get.return_value = mock_response
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=ctx)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            mgr = GasPriceManager(config)
            result = await mgr.fetch_gas_price_estimation()

        # default multiplier is 2.0
        assert result == 200

    async def test_fetch_gas_price_estimation_custom_multiplier(
        self, config: DecibelConfig
    ) -> None:
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.json.return_value = {"gas_estimate": 100}

        opts = GasPriceManagerOptions(multiplier=3.0)

        with patch("decibel._gas_price_manager.httpx.AsyncClient") as mock_cls:
            ctx = AsyncMock()
            ctx.get.return_value = mock_response
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=ctx)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            mgr = GasPriceManager(config, opts)
            result = await mgr.fetch_gas_price_estimation()

        assert result == 300

    async def test_fetch_gas_price_estimation_failure(self, config: DecibelConfig) -> None:
        mock_response = MagicMock()
        mock_response.is_success = False
        mock_response.status_code = 500
        mock_response.text = "error"

        with patch("decibel._gas_price_manager.httpx.AsyncClient") as mock_cls:
            ctx = AsyncMock()
            ctx.get.return_value = mock_response
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=ctx)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            mgr = GasPriceManager(config)
            with pytest.raises(ValueError, match="Failed to fetch"):
                await mgr.fetch_gas_price_estimation()

    async def test_fetch_and_set_gas_price(self, config: DecibelConfig) -> None:
        mgr = GasPriceManager(config)

        with patch.object(
            mgr,
            "fetch_gas_price_estimation",
            new_callable=AsyncMock,
            return_value=500,
        ):
            result = await mgr.fetch_and_set_gas_price()

        assert result == 500
        assert mgr.get_gas_price() == 500

    async def test_fetch_and_set_raises_on_zero(self, config: DecibelConfig) -> None:
        mgr = GasPriceManager(config)

        with (
            patch.object(
                mgr,
                "fetch_gas_price_estimation",
                new_callable=AsyncMock,
                return_value=0,
            ),
            pytest.raises(ValueError, match="no gas estimate"),
        ):
            await mgr.fetch_and_set_gas_price()

    async def test_fetch_gas_price_with_api_key(self, config: DecibelConfig) -> None:
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.json.return_value = {"gas_estimate": 50}

        opts = GasPriceManagerOptions(node_api_key="secret-key")

        with patch("decibel._gas_price_manager.httpx.AsyncClient") as mock_cls:
            ctx = AsyncMock()
            ctx.get.return_value = mock_response
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=ctx)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            mgr = GasPriceManager(config, opts)
            result = await mgr.fetch_gas_price_estimation()

        assert result == 100
        ctx.get.assert_awaited_once_with(
            f"{config.fullnode_url}/estimate_gas_price",
            headers={"x-api-key": "secret-key"},
            timeout=5.0,
        )


class TestGasPriceManagerSync:
    def test_get_gas_price_returns_none_initially(self, config: DecibelConfig) -> None:
        mgr = GasPriceManagerSync(config)
        assert mgr.get_gas_price() is None

    def test_fetch_gas_price_estimation(self, config: DecibelConfig) -> None:
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.json.return_value = {"gas_estimate": 100}

        with patch("decibel._gas_price_manager.httpx.Client") as mock_cls:
            ctx = MagicMock()
            ctx.get.return_value = mock_response
            mock_cls.return_value.__enter__ = MagicMock(return_value=ctx)
            mock_cls.return_value.__exit__ = MagicMock(return_value=False)

            mgr = GasPriceManagerSync(config)
            result = mgr.fetch_gas_price_estimation()

        assert result == 200

    def test_fetch_gas_price_estimation_failure(self, config: DecibelConfig) -> None:
        mock_response = MagicMock()
        mock_response.is_success = False
        mock_response.status_code = 500
        mock_response.text = "error"

        with patch("decibel._gas_price_manager.httpx.Client") as mock_cls:
            ctx = MagicMock()
            ctx.get.return_value = mock_response
            mock_cls.return_value.__enter__ = MagicMock(return_value=ctx)
            mock_cls.return_value.__exit__ = MagicMock(return_value=False)

            mgr = GasPriceManagerSync(config)
            with pytest.raises(ValueError, match="Failed to fetch"):
                mgr.fetch_gas_price_estimation()

    def test_fetch_and_set_gas_price(self, config: DecibelConfig) -> None:
        mgr = GasPriceManagerSync(config)

        with patch.object(
            mgr,
            "fetch_gas_price_estimation",
            return_value=500,
        ):
            result = mgr.fetch_and_set_gas_price()

        assert result == 500
        assert mgr.get_gas_price() == 500

    def test_fetch_and_set_raises_on_zero(self, config: DecibelConfig) -> None:
        mgr = GasPriceManagerSync(config)

        with (
            patch.object(
                mgr,
                "fetch_gas_price_estimation",
                return_value=0,
            ),
            pytest.raises(ValueError, match="no gas estimate"),
        ):
            mgr.fetch_and_set_gas_price()

    def test_fetch_gas_price_with_api_key(self, config: DecibelConfig) -> None:
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.json.return_value = {"gas_estimate": 50}

        opts = GasPriceManagerOptions(node_api_key="secret-key")

        with patch("decibel._gas_price_manager.httpx.Client") as mock_cls:
            ctx = MagicMock()
            ctx.get.return_value = mock_response
            mock_cls.return_value.__enter__ = MagicMock(return_value=ctx)
            mock_cls.return_value.__exit__ = MagicMock(return_value=False)

            mgr = GasPriceManagerSync(config, opts)
            result = mgr.fetch_gas_price_estimation()

        assert result == 100
        ctx.get.assert_called_once_with(
            f"{config.fullnode_url}/estimate_gas_price",
            headers={"x-api-key": "secret-key"},
            timeout=5.0,
        )
