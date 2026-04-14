"""Tests for decibel.read._ws module (DecibelWsSubscription)."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

from decibel.read._ws import DecibelWsSubscription

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


class _TestMessage(BaseModel):
    value: int


@pytest.fixture
def ws_client(test_config: object) -> DecibelWsSubscription:
    return DecibelWsSubscription(config=test_config, api_key="test-key")  # type: ignore[arg-type]


@pytest.fixture
def ws_client_no_key(test_config: object) -> DecibelWsSubscription:
    return DecibelWsSubscription(config=test_config)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------


class TestDecibelWsSubscriptionInit:
    def test_stores_config(self, ws_client: DecibelWsSubscription, test_config: object) -> None:
        assert ws_client._config is test_config

    def test_stores_api_key(self, ws_client: DecibelWsSubscription) -> None:
        assert ws_client._api_key == "test-key"

    def test_api_key_defaults_to_none(self, ws_client_no_key: DecibelWsSubscription) -> None:
        assert ws_client_no_key._api_key is None

    def test_on_error_defaults_to_none(self, ws_client: DecibelWsSubscription) -> None:
        assert ws_client._on_error is None

    def test_on_error_stored(self, test_config: object) -> None:
        on_error = MagicMock()
        ws = DecibelWsSubscription(config=test_config, on_error=on_error)  # type: ignore[arg-type]
        assert ws._on_error is on_error

    def test_initial_state(self, ws_client: DecibelWsSubscription) -> None:
        assert ws_client._ws is None
        assert ws_client._subscriptions == {}
        assert ws_client._reconnect_attempts == 0
        assert not ws_client._running
        assert ws_client._receive_task is None
        assert ws_client._close_timer_task is None


# ---------------------------------------------------------------------------
# _get_subscribe_message / _get_unsubscribe_message
# ---------------------------------------------------------------------------


class TestMessageHelpers:
    def test_subscribe_message_format(self, ws_client: DecibelWsSubscription) -> None:
        msg = ws_client._get_subscribe_message("market_price:0xabc")
        data = json.loads(msg)
        assert data["method"] == "subscribe"
        assert data["topic"] == "market_price:0xabc"

    def test_unsubscribe_message_format(self, ws_client: DecibelWsSubscription) -> None:
        msg = ws_client._get_unsubscribe_message("depth:0xabc:1")
        data = json.loads(msg)
        assert data["method"] == "unsubscribe"
        assert data["topic"] == "depth:0xabc:1"

    def test_subscribe_message_is_valid_json(self, ws_client: DecibelWsSubscription) -> None:
        msg = ws_client._get_subscribe_message("any:topic")
        json.loads(msg)  # Should not raise

    def test_unsubscribe_message_is_valid_json(self, ws_client: DecibelWsSubscription) -> None:
        msg = ws_client._get_unsubscribe_message("any:topic")
        json.loads(msg)  # Should not raise


# ---------------------------------------------------------------------------
# _parse_message
# ---------------------------------------------------------------------------


class TestParseMessage:
    def test_valid_message_with_topic(self, ws_client: DecibelWsSubscription) -> None:
        raw = json.dumps({"topic": "market_price:0xabc", "value": 42})
        result = ws_client._parse_message(raw)
        assert result is not None
        topic, data = result
        assert topic == "market_price:0xabc"
        assert data["value"] == 42

    def test_response_message_with_success_returns_none(
        self, ws_client: DecibelWsSubscription
    ) -> None:
        raw = json.dumps({"topic": "market_price:0xabc", "success": True})
        result = ws_client._parse_message(raw)
        assert result is None

    def test_invalid_json_raises_value_error(self, ws_client: DecibelWsSubscription) -> None:
        with pytest.raises(ValueError, match="failed to parse JSON"):
            ws_client._parse_message("not-valid-json{")

    def test_missing_topic_raises_value_error(self, ws_client: DecibelWsSubscription) -> None:
        raw = json.dumps({"method": "subscribe"})
        with pytest.raises(ValueError, match="missing topic field"):
            ws_client._parse_message(raw)

    def test_topic_not_string_raises_value_error(self, ws_client: DecibelWsSubscription) -> None:
        raw = json.dumps({"topic": 123, "data": "something"})
        with pytest.raises(ValueError, match="missing topic field"):
            ws_client._parse_message(raw)

    def test_strips_topic_from_data(self, ws_client: DecibelWsSubscription) -> None:
        raw = json.dumps({"topic": "some:topic", "payload": "hello"})
        result = ws_client._parse_message(raw)
        assert result is not None
        _, data = result
        assert "topic" not in data
        assert data["payload"] == "hello"

    def test_bigint_reviver_applied(self, ws_client: DecibelWsSubscription) -> None:
        raw = json.dumps({"topic": "some:topic", "nested": {"$bigint": "9999999999999999"}})
        result = ws_client._parse_message(raw)
        assert result is not None
        _, data = result
        # The nested dict goes through bigint_reviver and should become an int
        assert data["nested"] == 9999999999999999


# ---------------------------------------------------------------------------
# ready_state
# ---------------------------------------------------------------------------


class TestReadyState:
    def test_closed_when_no_ws(self, ws_client: DecibelWsSubscription) -> None:
        assert ws_client.ready_state() == 3

    def test_open_state(self, ws_client: DecibelWsSubscription) -> None:
        mock_ws = MagicMock()
        mock_ws.state.name = "OPEN"
        ws_client._ws = mock_ws
        assert ws_client.ready_state() == 1

    def test_closing_state(self, ws_client: DecibelWsSubscription) -> None:
        mock_ws = MagicMock()
        mock_ws.state.name = "CLOSING"
        ws_client._ws = mock_ws
        assert ws_client.ready_state() == 2

    def test_connecting_state(self, ws_client: DecibelWsSubscription) -> None:
        mock_ws = MagicMock()
        mock_ws.state.name = "CONNECTING"
        ws_client._ws = mock_ws
        assert ws_client.ready_state() == 0


# ---------------------------------------------------------------------------
# subscribe
# ---------------------------------------------------------------------------


class TestSubscribe:
    async def test_subscribe_adds_listener_and_opens(
        self, ws_client: DecibelWsSubscription
    ) -> None:
        on_data = MagicMock()

        with patch.object(ws_client, "_open", new_callable=AsyncMock):
            unsubscribe = ws_client.subscribe("test:topic", _TestMessage, on_data)
            await asyncio.sleep(0)  # Let tasks run

        assert "test:topic" in ws_client._subscriptions
        assert len(ws_client._subscriptions["test:topic"]) == 1
        assert callable(unsubscribe)

    async def test_subscribe_sends_subscribe_when_ws_exists(
        self, ws_client: DecibelWsSubscription
    ) -> None:
        mock_ws = AsyncMock()
        mock_ws.send = AsyncMock()
        ws_client._ws = mock_ws

        on_data = MagicMock()
        ws_client.subscribe("new:topic", _TestMessage, on_data)
        await asyncio.sleep(0)  # Let tasks run

        mock_ws.send.assert_called()

    async def test_subscribe_returns_callable_unsubscribe(
        self, ws_client: DecibelWsSubscription
    ) -> None:
        on_data = MagicMock()
        with patch.object(ws_client, "_open", new_callable=AsyncMock):
            unsubscribe = ws_client.subscribe("test:topic", _TestMessage, on_data)
        assert callable(unsubscribe)

    async def test_subscribe_cancels_close_timer(self, ws_client: DecibelWsSubscription) -> None:
        mock_task = MagicMock()
        ws_client._close_timer_task = mock_task

        on_data = MagicMock()
        with patch.object(ws_client, "_open", new_callable=AsyncMock):
            ws_client.subscribe("test:topic", _TestMessage, on_data)

        mock_task.cancel.assert_called_once()
        assert ws_client._close_timer_task is None

    async def test_subscribe_multiple_listeners_same_topic(
        self, ws_client: DecibelWsSubscription
    ) -> None:
        on_data1 = MagicMock()
        on_data2 = MagicMock()

        with patch.object(ws_client, "_open", new_callable=AsyncMock):
            ws_client.subscribe("test:topic", _TestMessage, on_data1)
            ws_client.subscribe("test:topic", _TestMessage, on_data2)

        assert len(ws_client._subscriptions["test:topic"]) == 2


# ---------------------------------------------------------------------------
# _unsubscribe_listener / _unsubscribe_topic
# ---------------------------------------------------------------------------


class TestUnsubscribeListener:
    async def test_unsubscribe_removes_listener(self, ws_client: DecibelWsSubscription) -> None:
        on_data = MagicMock()
        with patch.object(ws_client, "_open", new_callable=AsyncMock):
            unsubscribe = ws_client.subscribe("test:topic", _TestMessage, on_data)
        assert len(ws_client._subscriptions["test:topic"]) == 1

        unsubscribe()
        assert "test:topic" not in ws_client._subscriptions

    async def test_unsubscribe_nonexistent_topic_is_safe(
        self, ws_client: DecibelWsSubscription
    ) -> None:
        # Should not raise
        ws_client._unsubscribe_listener("nonexistent:topic", MagicMock())

    async def test_unsubscribe_sends_unsub_message_when_ws_open(
        self, ws_client: DecibelWsSubscription
    ) -> None:
        mock_ws = AsyncMock()
        mock_ws.send = AsyncMock()
        ws_client._ws = mock_ws

        on_data = MagicMock()
        with patch.object(ws_client, "_open", new_callable=AsyncMock):
            unsubscribe = ws_client.subscribe("test:topic", _TestMessage, on_data)

        # Clear mock calls from subscribe
        mock_ws.send.reset_mock()

        unsubscribe()
        await asyncio.sleep(0)

        # Unsubscribe message should be sent
        mock_ws.send.assert_called()

    async def test_unsubscribe_topic_not_in_subs_is_safe(
        self, ws_client: DecibelWsSubscription
    ) -> None:
        # Should not raise
        ws_client._unsubscribe_topic("nonexistent:topic")


# ---------------------------------------------------------------------------
# _open
# ---------------------------------------------------------------------------


class TestOpen:
    async def test_open_connects_and_sets_ws(self, ws_client: DecibelWsSubscription) -> None:
        mock_ws = AsyncMock()
        mock_ws.send = AsyncMock()

        with patch("decibel.read._ws.connect", return_value=mock_ws) as mock_connect:
            mock_connect.__aenter__ = AsyncMock(return_value=mock_ws)

            # Make connect() awaitable returning mock_ws
            async def fake_connect(*args, **kwargs):  # noqa: ANN202
                return mock_ws

            with patch("decibel.read._ws.connect", side_effect=fake_connect):
                await ws_client._open()

        assert ws_client._ws is mock_ws
        assert ws_client._reconnect_attempts == 0
        assert ws_client._running

    async def test_open_noop_when_already_connected(self, ws_client: DecibelWsSubscription) -> None:
        existing_ws = AsyncMock()
        ws_client._ws = existing_ws

        with patch("decibel.read._ws.connect") as mock_connect:
            await ws_client._open()
            mock_connect.assert_not_called()

    async def test_open_subscribes_to_existing_topics(
        self, ws_client: DecibelWsSubscription
    ) -> None:
        mock_ws = AsyncMock()
        mock_ws.send = AsyncMock()
        # Pre-add a subscription topic (simulating state before connection)
        ws_client._subscriptions["existing:topic"] = set()

        async def fake_connect(*args, **kwargs):  # noqa: ANN202
            return mock_ws

        with patch("decibel.read._ws.connect", side_effect=fake_connect):
            await ws_client._open()

        mock_ws.send.assert_called()
        sent_msg = json.loads(mock_ws.send.call_args_list[0][0][0])
        assert sent_msg["topic"] == "existing:topic"

    async def test_open_handles_connection_failure(self, ws_client: DecibelWsSubscription) -> None:
        on_error = MagicMock()
        ws_client._on_error = on_error

        async def failing_connect(*args, **kwargs):  # noqa: ANN202
            raise ConnectionError("refused")

        with patch("decibel.read._ws.connect", side_effect=failing_connect):
            with patch.object(ws_client, "_schedule_reconnect", new_callable=AsyncMock):
                await ws_client._open()

        on_error.assert_called_once()
        assert ws_client._ws is None


# ---------------------------------------------------------------------------
# _schedule_reconnect (exponential backoff)
# ---------------------------------------------------------------------------


class TestScheduleReconnect:
    async def test_no_reconnect_when_no_subscriptions(
        self, ws_client: DecibelWsSubscription
    ) -> None:
        with patch("decibel.read._ws.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with patch.object(ws_client, "_open", new_callable=AsyncMock) as mock_open:
                await ws_client._schedule_reconnect()
        mock_sleep.assert_not_called()
        mock_open.assert_not_called()

    async def test_reconnect_with_subscriptions_uses_backoff(
        self, ws_client: DecibelWsSubscription
    ) -> None:
        ws_client._subscriptions["some:topic"] = set()
        ws_client._reconnect_attempts = 0

        with patch("decibel.read._ws.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with patch.object(ws_client, "_open", new_callable=AsyncMock):
                await ws_client._schedule_reconnect()

        # First attempt: delay = 1.5^0 = 1.0
        mock_sleep.assert_called_once_with(1.0)

    async def test_reconnect_increments_attempts(self, ws_client: DecibelWsSubscription) -> None:
        ws_client._subscriptions["some:topic"] = set()
        ws_client._reconnect_attempts = 2

        with patch("decibel.read._ws.asyncio.sleep", new_callable=AsyncMock):
            with patch.object(ws_client, "_open", new_callable=AsyncMock):
                await ws_client._schedule_reconnect()

        assert ws_client._reconnect_attempts == 3

    async def test_reconnect_delay_capped_at_60(self, ws_client: DecibelWsSubscription) -> None:
        ws_client._subscriptions["some:topic"] = set()
        ws_client._reconnect_attempts = 100  # Very high attempt count

        with patch("decibel.read._ws.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with patch.object(ws_client, "_open", new_callable=AsyncMock):
                await ws_client._schedule_reconnect()

        call_arg = mock_sleep.call_args[0][0]
        assert call_arg == 60.0

    async def test_exponential_backoff_formula(self, ws_client: DecibelWsSubscription) -> None:
        ws_client._subscriptions["some:topic"] = set()

        for attempt in range(5):
            ws_client._reconnect_attempts = attempt
            expected = min(1.5**attempt, 60.0)

            with patch("decibel.read._ws.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                with patch.object(ws_client, "_open", new_callable=AsyncMock):
                    await ws_client._schedule_reconnect()

            actual = mock_sleep.call_args[0][0]
            assert abs(actual - expected) < 0.0001, f"attempt={attempt}"
            ws_client._reconnect_attempts = attempt  # reset for next iteration


# ---------------------------------------------------------------------------
# close
# ---------------------------------------------------------------------------


class TestClose:
    async def test_close_clears_subscriptions(self, ws_client: DecibelWsSubscription) -> None:
        ws_client._subscriptions["topic:a"] = set()
        ws_client._subscriptions["topic:b"] = set()

        await ws_client.close()

        assert ws_client._subscriptions == {}

    async def test_close_cancels_close_timer(self, ws_client: DecibelWsSubscription) -> None:
        mock_task = MagicMock()
        ws_client._close_timer_task = mock_task

        await ws_client.close()

        mock_task.cancel.assert_called_once()
        assert ws_client._close_timer_task is None

    async def test_close_cancels_receive_task(self, ws_client: DecibelWsSubscription) -> None:
        # Create a real asyncio task that sleeps forever so we can cancel it
        async def _forever() -> None:
            await asyncio.sleep(9999)

        real_task = asyncio.create_task(_forever())
        ws_client._receive_task = real_task

        await ws_client.close()

        assert real_task.cancelled()
        assert ws_client._receive_task is None

    async def test_close_closes_ws(self, ws_client: DecibelWsSubscription) -> None:
        mock_ws = AsyncMock()
        mock_ws.close = AsyncMock()
        ws_client._ws = mock_ws

        await ws_client.close()

        mock_ws.close.assert_called_once()
        assert ws_client._ws is None

    async def test_close_with_no_ws_is_safe(self, ws_client: DecibelWsSubscription) -> None:
        # Should not raise
        await ws_client.close()


# ---------------------------------------------------------------------------
# reset
# ---------------------------------------------------------------------------


class TestReset:
    async def test_reset_sends_unsub_then_sub(self, ws_client: DecibelWsSubscription) -> None:
        mock_ws = AsyncMock()
        mock_ws.send = AsyncMock()
        ws_client._ws = mock_ws
        ws_client._subscriptions["test:topic"] = {MagicMock()}

        ws_client.reset("test:topic")
        await asyncio.sleep(0)

        # Both unsub and sub messages should have been sent
        assert mock_ws.send.call_count == 2
        first_msg = json.loads(mock_ws.send.call_args_list[0][0][0])
        second_msg = json.loads(mock_ws.send.call_args_list[1][0][0])
        assert first_msg["method"] == "unsubscribe"
        assert second_msg["method"] == "subscribe"
        assert first_msg["topic"] == "test:topic"
        assert second_msg["topic"] == "test:topic"

    def test_reset_noop_when_topic_not_subscribed(self, ws_client: DecibelWsSubscription) -> None:
        mock_ws = AsyncMock()
        ws_client._ws = mock_ws

        ws_client.reset("nonexistent:topic")
        # No tasks created - no assert needed, just confirm no error

    def test_reset_noop_when_no_ws(self, ws_client: DecibelWsSubscription) -> None:
        ws_client._subscriptions["test:topic"] = {MagicMock()}
        ws_client._ws = None

        # Should not raise and should not do anything
        ws_client.reset("test:topic")


# ---------------------------------------------------------------------------
# Listener invocation and error handling
# ---------------------------------------------------------------------------


class TestListenerInvocation:
    async def test_subscribe_listener_parses_model(self, ws_client: DecibelWsSubscription) -> None:
        received: list[_TestMessage] = []

        def on_data(msg: _TestMessage) -> None:
            received.append(msg)

        with patch.object(ws_client, "_open", new_callable=AsyncMock):
            ws_client.subscribe("test:topic", _TestMessage, on_data)

        # Directly call the internal listener with raw data
        listeners = list(ws_client._subscriptions["test:topic"])
        listener = listeners[0]
        listener({"value": 99})
        assert len(received) == 1
        assert received[0].value == 99

    async def test_subscribe_listener_raises_on_invalid_data(
        self, ws_client: DecibelWsSubscription
    ) -> None:
        def on_data(msg: _TestMessage) -> None:
            pass

        with patch.object(ws_client, "_open", new_callable=AsyncMock):
            ws_client.subscribe("test:topic", _TestMessage, on_data)

        listeners = list(ws_client._subscriptions["test:topic"])
        listener = listeners[0]

        with pytest.raises(ValueError, match="Validation error"):
            listener({"not_value": "bad"})


# ---------------------------------------------------------------------------
# _receive_loop
# ---------------------------------------------------------------------------


class TestReceiveLoop:
    async def test_receive_loop_exits_when_ws_is_none(
        self, ws_client: DecibelWsSubscription
    ) -> None:
        ws_client._ws = None
        # Should return immediately without error
        await ws_client._receive_loop()

    async def test_receive_loop_dispatches_to_listener(
        self, ws_client: DecibelWsSubscription
    ) -> None:
        """Test that _receive_loop dispatches valid messages to listeners."""
        received: list[dict] = []

        async def fake_aiter(msg_list: list[str]):  # noqa: ANN202
            for m in msg_list:
                yield m

        messages = [json.dumps({"topic": "test:topic", "value": 99})]
        mock_ws = MagicMock()
        mock_ws.__aiter__ = MagicMock(return_value=fake_aiter(messages).__aiter__())

        ws_client._ws = mock_ws
        ws_client._subscriptions["test:topic"] = {lambda d: received.append(d)}  # type: ignore[arg-type]

        with patch.object(ws_client, "_schedule_reconnect", new_callable=AsyncMock):
            await ws_client._receive_loop()

        assert len(received) == 1

    async def test_receive_loop_ignores_response_messages(
        self, ws_client: DecibelWsSubscription
    ) -> None:
        """Subscribe/unsubscribe confirmation messages (success field) are ignored."""

        async def fake_aiter(msg_list: list[str]):  # noqa: ANN202
            for m in msg_list:
                yield m

        messages = [json.dumps({"topic": "test:topic", "success": True})]
        mock_ws = MagicMock()
        mock_ws.__aiter__ = MagicMock(return_value=fake_aiter(messages).__aiter__())
        ws_client._ws = mock_ws

        received: list[dict] = []
        ws_client._subscriptions["test:topic"] = {lambda d: received.append(d)}  # type: ignore[arg-type]

        with patch.object(ws_client, "_schedule_reconnect", new_callable=AsyncMock):
            await ws_client._receive_loop()

        assert len(received) == 0

    async def test_receive_loop_handles_listener_exception(
        self, ws_client: DecibelWsSubscription
    ) -> None:
        """Listener exceptions are caught and logged without crashing the loop."""

        async def fake_aiter(msg_list: list[str]):  # noqa: ANN202
            for m in msg_list:
                yield m

        messages = [json.dumps({"topic": "test:topic", "value": 1})]
        mock_ws = MagicMock()
        mock_ws.__aiter__ = MagicMock(return_value=fake_aiter(messages).__aiter__())
        ws_client._ws = mock_ws

        def bad_listener(d: dict) -> None:
            raise RuntimeError("listener error")

        ws_client._subscriptions["test:topic"] = {bad_listener}

        # Should not raise
        with patch.object(ws_client, "_schedule_reconnect", new_callable=AsyncMock):
            await ws_client._receive_loop()

    async def test_receive_loop_handles_connection_closed(
        self, ws_client: DecibelWsSubscription
    ) -> None:
        """ConnectionClosed is silently swallowed."""
        from websockets import ConnectionClosed as WsConnectionClosed

        async def fake_aiter():  # noqa: ANN202
            raise WsConnectionClosed(None, None)  # type: ignore[arg-type]
            yield  # make it an async generator

        mock_ws = MagicMock()
        mock_ws.__aiter__ = MagicMock(return_value=fake_aiter().__aiter__())
        ws_client._ws = mock_ws

        with patch.object(ws_client, "_schedule_reconnect", new_callable=AsyncMock):
            await ws_client._receive_loop()  # Should not raise

    async def test_receive_loop_calls_on_error_on_exception(
        self, ws_client: DecibelWsSubscription
    ) -> None:
        on_error = MagicMock()
        ws_client._on_error = on_error

        async def fake_aiter():  # noqa: ANN202
            raise RuntimeError("connection error")
            yield

        mock_ws = MagicMock()
        mock_ws.__aiter__ = MagicMock(return_value=fake_aiter().__aiter__())
        ws_client._ws = mock_ws

        with patch.object(ws_client, "_schedule_reconnect", new_callable=AsyncMock):
            await ws_client._receive_loop()

        on_error.assert_called_once()

    async def test_receive_loop_handles_coroutine_listener(
        self, ws_client: DecibelWsSubscription
    ) -> None:
        """Async listener coroutines are awaited."""
        received: list[dict] = []

        async def async_listener(d: dict) -> None:
            received.append(d)

        async def fake_aiter(msg_list: list[str]):  # noqa: ANN202
            for m in msg_list:
                yield m

        messages = [json.dumps({"topic": "test:topic", "value": 1})]
        mock_ws = MagicMock()
        mock_ws.__aiter__ = MagicMock(return_value=fake_aiter(messages).__aiter__())
        ws_client._ws = mock_ws
        ws_client._subscriptions["test:topic"] = {async_listener}

        with patch.object(ws_client, "_schedule_reconnect", new_callable=AsyncMock):
            await ws_client._receive_loop()

        assert len(received) == 1

    async def test_receive_loop_reconnects_when_subscriptions_remain(
        self, ws_client: DecibelWsSubscription
    ) -> None:
        """After loop ends, if subs remain, _schedule_reconnect is called."""

        async def fake_aiter():  # noqa: ANN202
            return
            yield  # make it an async generator

        mock_ws = MagicMock()
        mock_ws.__aiter__ = MagicMock(return_value=fake_aiter().__aiter__())
        ws_client._ws = mock_ws
        ws_client._subscriptions["some:topic"] = set()

        with patch.object(
            ws_client, "_schedule_reconnect", new_callable=AsyncMock
        ) as mock_reconnect:
            await ws_client._receive_loop()

        mock_reconnect.assert_called_once()


# ---------------------------------------------------------------------------
# _delayed_close
# ---------------------------------------------------------------------------


class TestDelayedClose:
    async def test_delayed_close_closes_ws_when_no_subs(
        self, ws_client: DecibelWsSubscription
    ) -> None:
        mock_ws = AsyncMock()
        mock_ws.close = AsyncMock()
        ws_client._ws = mock_ws

        with patch("decibel.read._ws.asyncio.sleep", new_callable=AsyncMock):
            await ws_client._delayed_close()

        mock_ws.close.assert_called_once()
        assert ws_client._ws is None

    async def test_delayed_close_skips_close_when_subs_remain(
        self, ws_client: DecibelWsSubscription
    ) -> None:
        mock_ws = AsyncMock()
        mock_ws.close = AsyncMock()
        ws_client._ws = mock_ws
        # Add a subscription so close is skipped
        ws_client._subscriptions["active:topic"] = {MagicMock()}

        with patch("decibel.read._ws.asyncio.sleep", new_callable=AsyncMock):
            await ws_client._delayed_close()

        mock_ws.close.assert_not_called()

    async def test_delayed_close_skips_when_ws_already_none(
        self, ws_client: DecibelWsSubscription
    ) -> None:
        ws_client._ws = None
        # Should not raise
        with patch("decibel.read._ws.asyncio.sleep", new_callable=AsyncMock):
            await ws_client._delayed_close()
