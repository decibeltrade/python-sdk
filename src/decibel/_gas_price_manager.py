from __future__ import annotations

import asyncio
import contextlib
import logging
import threading
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from ._constants import DecibelConfig

__all__ = [
    "GasPriceInfo",
    "GasPriceManager",
    "GasPriceManagerOptions",
    "GasPriceManagerSync",
]

logger = logging.getLogger(__name__)


@dataclass
class GasPriceInfo:
    gas_estimate: int
    timestamp: float


@dataclass
class GasPriceManagerOptions:
    node_api_key: str | None = None
    multiplier: float = 2.0
    refresh_interval_seconds: float = 60.0


def _build_auth_headers(api_key: str | None) -> dict[str, str]:
    if not api_key:
        return {}
    return {"x-api-key": api_key}


class GasPriceManager:
    def __init__(
        self,
        config: DecibelConfig,
        opts: GasPriceManagerOptions | None = None,
    ) -> None:
        self._config = config
        self._opts = opts or GasPriceManagerOptions()
        self._gas_price: GasPriceInfo | None = None
        self._refresh_task: asyncio.Task[None] | None = None
        self._pending_refresh_task: asyncio.Task[None] | None = None
        self._is_initialized = False
        self._refresh_interval_seconds = self._opts.refresh_interval_seconds
        self._multiplier = self._opts.multiplier

    @property
    def gas_price(self) -> int | None:
        if self._gas_price is None:
            return None
        return self._gas_price.gas_estimate

    @property
    def is_initialized(self) -> bool:
        return self._is_initialized

    async def initialize(self) -> None:
        if self._is_initialized:
            return

        try:
            await self.fetch_and_set_gas_price()
            self._refresh_task = asyncio.create_task(self._refresh_loop())
            self._is_initialized = True
        except Exception as e:
            logger.error("Failed to initialize gas price manager: %s", e)

    async def destroy(self) -> None:
        if self._refresh_task is not None:
            self._refresh_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._refresh_task
            self._refresh_task = None

        self._is_initialized = False
        self._gas_price = None

    def get_gas_price(self) -> int | None:
        return self.gas_price

    def refresh(self) -> None:
        if self._pending_refresh_task is None or self._pending_refresh_task.done():
            self._pending_refresh_task = asyncio.create_task(self._safe_fetch())

    async def fetch_gas_price_estimation(self) -> int:
        url = f"{self._config.fullnode_url}/estimate_gas_price"
        headers = _build_auth_headers(self._opts.node_api_key)

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)

        if not response.is_success:
            raise ValueError(f"Failed to fetch gas price: {response.status_code} - {response.text}")

        data = response.json()
        gas_estimate = data.get("gas_estimate", 0)

        return int(gas_estimate * self._multiplier)

    async def fetch_and_set_gas_price(self) -> int:
        try:
            gas_estimate = await self.fetch_gas_price_estimation()

            if not gas_estimate:
                raise ValueError("Gas estimation returned no gas estimate")

            self._gas_price = GasPriceInfo(
                gas_estimate=gas_estimate,
                timestamp=time.time(),
            )

            return gas_estimate
        except Exception as e:
            logger.error("Failed to fetch gas price: %s", e)
            raise

    async def _refresh_loop(self) -> None:
        while True:
            await asyncio.sleep(self._refresh_interval_seconds)
            try:
                await self.fetch_and_set_gas_price()
            except Exception as e:
                logger.warning("Failed to fetch gas price during refresh: %s", e)

    async def _safe_fetch(self) -> None:
        try:
            await self.fetch_and_set_gas_price()
        except Exception as e:
            logger.warning("Failed to fetch gas price: %s", e)

    async def __aenter__(self) -> GasPriceManager:
        await self.initialize()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        await self.destroy()


class GasPriceManagerSync:
    def __init__(
        self,
        config: DecibelConfig,
        opts: GasPriceManagerOptions | None = None,
    ) -> None:
        self._config = config
        self._opts = opts or GasPriceManagerOptions()
        self._gas_price: GasPriceInfo | None = None
        self._refresh_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._is_initialized = False
        self._refresh_interval_seconds = self._opts.refresh_interval_seconds
        self._multiplier = self._opts.multiplier

    @property
    def gas_price(self) -> int | None:
        if self._gas_price is None:
            return None
        return self._gas_price.gas_estimate

    @property
    def is_initialized(self) -> bool:
        return self._is_initialized

    def initialize(self) -> None:
        if self._is_initialized:
            return

        try:
            self.fetch_and_set_gas_price()
            self._stop_event.clear()
            self._refresh_thread = threading.Thread(target=self._refresh_loop, daemon=True)
            self._refresh_thread.start()
            self._is_initialized = True
        except Exception as e:
            logger.error("Failed to initialize gas price manager: %s", e)

    def destroy(self) -> None:
        if self._refresh_thread is not None:
            self._stop_event.set()
            self._refresh_thread.join(timeout=2.0)
            self._refresh_thread = None

        self._is_initialized = False
        self._gas_price = None

    def get_gas_price(self) -> int | None:
        return self.gas_price

    def refresh(self) -> None:
        try:
            self.fetch_and_set_gas_price()
        except Exception as e:
            logger.warning("Failed to fetch gas price: %s", e)

    def fetch_gas_price_estimation(self) -> int:
        url = f"{self._config.fullnode_url}/estimate_gas_price"
        headers = _build_auth_headers(self._opts.node_api_key)

        with httpx.Client() as client:
            response = client.get(url, headers=headers)

        if not response.is_success:
            raise ValueError(f"Failed to fetch gas price: {response.status_code} - {response.text}")

        data = response.json()
        gas_estimate = data.get("gas_estimate", 0)

        return int(gas_estimate * self._multiplier)

    def fetch_and_set_gas_price(self) -> int:
        try:
            gas_estimate = self.fetch_gas_price_estimation()

            if not gas_estimate:
                raise ValueError("Gas estimation returned no gas estimate")

            self._gas_price = GasPriceInfo(
                gas_estimate=gas_estimate,
                timestamp=time.time(),
            )

            return gas_estimate
        except Exception as e:
            logger.error("Failed to fetch gas price: %s", e)
            raise

    def _refresh_loop(self) -> None:
        while not self._stop_event.wait(self._refresh_interval_seconds):
            try:
                self.fetch_and_set_gas_price()
            except Exception as e:
                logger.warning("Failed to fetch gas price during refresh: %s", e)

    def __enter__(self) -> GasPriceManagerSync:
        self.initialize()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        self.destroy()
