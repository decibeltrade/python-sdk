from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypeVar

from pydantic import BaseModel

from .._utils import (
    get_request,
    get_request_sync,
    patch_request,
    patch_request_sync,
    post_request,
    post_request_sync,
)

if TYPE_CHECKING:
    from aptos_sdk.async_client import RestClient

    from .._constants import DecibelConfig
    from ._ws import DecibelWsSubscription

__all__ = [
    "ReaderDeps",
    "BaseReader",
]

T = TypeVar("T", bound=BaseModel)


@dataclass
class ReaderDeps:
    config: DecibelConfig
    ws: DecibelWsSubscription
    aptos: RestClient
    api_key: str | None = None


class BaseReader:
    def __init__(self, deps: ReaderDeps) -> None:
        self._deps = deps

    @property
    def config(self) -> DecibelConfig:
        return self._deps.config

    @property
    def ws(self) -> DecibelWsSubscription:
        return self._deps.ws

    @property
    def aptos(self) -> RestClient:
        return self._deps.aptos

    async def get_request(
        self,
        model: type[T],
        url: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> tuple[T, int, str]:
        return await get_request(
            model=model,
            url=url,
            params=params,
            api_key=self._deps.api_key,
        )

    async def post_request(
        self,
        model: type[T],
        url: str,
        *,
        body: Any | None = None,
    ) -> tuple[T, int, str]:
        return await post_request(
            model=model,
            url=url,
            body=body,
            api_key=self._deps.api_key,
        )

    async def patch_request(
        self,
        model: type[T],
        url: str,
        *,
        body: Any | None = None,
    ) -> tuple[T, int, str]:
        return await patch_request(
            model=model,
            url=url,
            body=body,
            api_key=self._deps.api_key,
        )

    def get_request_sync(
        self,
        model: type[T],
        url: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> tuple[T, int, str]:
        return get_request_sync(
            model=model,
            url=url,
            params=params,
            api_key=self._deps.api_key,
        )

    def post_request_sync(
        self,
        model: type[T],
        url: str,
        *,
        body: Any | None = None,
    ) -> tuple[T, int, str]:
        return post_request_sync(
            model=model,
            url=url,
            body=body,
            api_key=self._deps.api_key,
        )

    def patch_request_sync(
        self,
        model: type[T],
        url: str,
        *,
        body: Any | None = None,
    ) -> tuple[T, int, str]:
        return patch_request_sync(
            model=model,
            url=url,
            body=body,
            api_key=self._deps.api_key,
        )
