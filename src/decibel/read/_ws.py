from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, TypeVar, cast

from pydantic import BaseModel, ValidationError
from websockets import ConnectionClosed, Subprotocol
from websockets.asyncio.client import ClientConnection, connect

from .._utils import bigint_reviver, prettify_validation_error

if TYPE_CHECKING:
    from .._constants import DecibelConfig

__all__ = [
    "DecibelWsSubscription",
    "Unsubscribe",
]

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

Unsubscribe = Callable[[], None]


class DecibelWsSubscription:
    def __init__(
        self,
        config: DecibelConfig,
        api_key: str | None = None,
        on_error: Callable[[Exception], None] | None = None,
    ) -> None:
        self._config = config
        self._api_key = api_key
        self._on_error = on_error

        self._ws: ClientConnection | None = None
        self._subscriptions: dict[str, set[Callable[[Any], Any]]] = {}
        self._reconnect_attempts: int = 0
        self._running: bool = False
        self._receive_task: asyncio.Task[None] | None = None
        self._close_timer_task: asyncio.Task[None] | None = None

    def _get_subscribe_message(self, topic: str) -> str:
        return json.dumps({"method": "subscribe", "topic": topic})

    def _get_unsubscribe_message(self, topic: str) -> str:
        return json.dumps({"method": "unsubscribe", "topic": topic})

    def _parse_message(self, data: str) -> tuple[str, dict[str, Any]] | None:
        try:
            json_data: Any = json.loads(data, object_hook=bigint_reviver)
        except (json.JSONDecodeError, TypeError) as e:
            raise ValueError(f"Unhandled WebSocket message: failed to parse JSON: {data}") from e

        if (
            isinstance(json_data, dict)
            and "topic" in json_data
            and isinstance(json_data["topic"], str)
        ):
            # Filter out response messages (they have a "success" field; data payloads do not)
            if "success" in json_data:
                return None
            topic: str = json_data["topic"]
            json_dict = cast("dict[str, Any]", json_data)
            rest: dict[str, Any] = {k: v for k, v in json_dict.items() if k != "topic"}
            return (topic, rest)
        raise ValueError(f"Unhandled WebSocket message: missing topic field: {data}")

    async def _open(self) -> None:
        if self._ws is not None:
            return

        try:
            subprotocols = (
                [Subprotocol("decibel"), Subprotocol(self._api_key)] if self._api_key else None
            )
            self._ws = await connect(self._config.trading_ws_url, subprotocols=subprotocols)
            self._reconnect_attempts = 0
            self._running = True

            for topic in self._subscriptions:
                await self._ws.send(self._get_subscribe_message(topic))

            self._receive_task = asyncio.create_task(self._receive_loop())
        except Exception as e:
            logger.error("Failed to connect to WebSocket: %s", e)
            if self._on_error:
                self._on_error(e)
            self._ws = None
            await self._schedule_reconnect()

    async def _receive_loop(self) -> None:
        if self._ws is None:
            return

        try:
            async for message in self._ws:
                if not isinstance(message, str):
                    raise ValueError(
                        f"Unhandled WebSocket message: expected string data: {message}"
                    )

                parsed = self._parse_message(message)
                if parsed is None:
                    # Response messages (subscribe/unsubscribe confirmations) are silently ignored
                    continue

                topic, data = parsed
                listeners = self._subscriptions.get(topic)
                if listeners:
                    for listener in list(listeners):
                        try:
                            result = listener(data)
                            if asyncio.iscoroutine(result):
                                await result
                        except Exception as e:
                            logger.error("Error in WebSocket listener for topic %s: %s", topic, e)
        except ConnectionClosed:
            pass
        except Exception as e:
            logger.error("WebSocket receive loop error: %s", e)
            if self._on_error:
                self._on_error(e)
        finally:
            self._ws = None
            self._running = False
            if self._subscriptions:
                await self._schedule_reconnect()

    async def _schedule_reconnect(self) -> None:
        if not self._subscriptions:
            return

        delay = min((1.5**self._reconnect_attempts), 60.0)
        self._reconnect_attempts += 1
        logger.debug("Reconnecting in %.1f seconds (attempt %d)", delay, self._reconnect_attempts)
        await asyncio.sleep(delay)
        await self._open()

    def subscribe(
        self,
        topic: str,
        model: type[T],
        on_data: Callable[[T], None] | Callable[[T], Awaitable[None]],
    ) -> Unsubscribe:
        listeners: set[Callable[[Any], Any]] = self._subscriptions.get(topic, set())
        if topic not in self._subscriptions:
            self._subscriptions[topic] = listeners

        is_new_topic = len(listeners) == 0

        def listener(data: Any) -> Any:
            try:
                parsed_data = model.model_validate(data)
                result = on_data(parsed_data)
                return result
            except ValidationError as e:
                raise ValueError(prettify_validation_error(e)) from e

        listeners.add(listener)

        if is_new_topic and self._ws is not None:
            asyncio.create_task(self._ws.send(self._get_subscribe_message(topic)))

        if self._ws is None:
            asyncio.create_task(self._open())

        if self._close_timer_task is not None:
            self._close_timer_task.cancel()
            self._close_timer_task = None

        def unsubscribe() -> None:
            self._unsubscribe_listener(topic, listener)

        return unsubscribe

    def _unsubscribe_listener(self, topic: str, listener: Callable[[Any], Any]) -> None:
        listeners = self._subscriptions.get(topic)
        if listeners is None:
            return

        listeners.discard(listener)

        if len(listeners) == 0:
            self._unsubscribe_topic(topic)

    def _unsubscribe_topic(self, topic: str) -> None:
        if topic not in self._subscriptions:
            return

        del self._subscriptions[topic]

        if self._ws is not None:
            asyncio.create_task(self._ws.send(self._get_unsubscribe_message(topic)))

        if len(self._subscriptions) == 0:
            self._close_timer_task = asyncio.create_task(self._delayed_close())

    async def _delayed_close(self) -> None:
        await asyncio.sleep(0.5)
        if len(self._subscriptions) == 0 and self._ws is not None:
            await self._ws.close()
            self._ws = None

    def reset(self, topic: str) -> None:
        if topic not in self._subscriptions:
            return

        if self._ws is not None:
            asyncio.create_task(self._reset_topic(topic))

    async def _reset_topic(self, topic: str) -> None:
        if self._ws is None:
            return
        await self._ws.send(self._get_unsubscribe_message(topic))
        await self._ws.send(self._get_subscribe_message(topic))

    async def close(self) -> None:
        self._subscriptions.clear()
        if self._close_timer_task is not None:
            self._close_timer_task.cancel()
            self._close_timer_task = None
        if self._receive_task is not None:
            self._receive_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._receive_task
            self._receive_task = None
        if self._ws is not None:
            await self._ws.close()
            self._ws = None

    def ready_state(self) -> int:
        if self._ws is None:
            return 3  # CLOSED
        if self._ws.state.name == "OPEN":
            return 1  # OPEN
        if self._ws.state.name == "CLOSING":
            return 2  # CLOSING
        return 0  # CONNECTING
