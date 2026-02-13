from __future__ import annotations

from typing import Generic, Literal, TypedDict, TypeVar

from pydantic import BaseModel

__all__ = [
    "PageParams",
    "SearchTermParams",
    "SortDirection",
    "SortParams",
    "KnownQueryParams",
    "PaginatedResponse",
    "QUERY_PARAM_KEYS",
    "PARAM_MAP",
    "construct_known_query_params",
]

T = TypeVar("T")
SortKeyT = TypeVar("SortKeyT", bound=str)

SortDirection = Literal["ASC", "DESC"]


class PageParams(TypedDict, total=False):
    limit: int
    offset: int


class SearchTermParams(TypedDict, total=False):
    search_term: str


class SortParams(TypedDict, Generic[SortKeyT], total=False):
    sort_key: SortKeyT
    sort_dir: SortDirection | None


class KnownQueryParams(TypedDict, total=False):
    limit: int
    offset: int
    search_term: str
    sort_key: str
    sort_dir: SortDirection | None


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total_count: int


QUERY_PARAM_KEYS: dict[str, str] = {
    "offset": "offset",
    "limit": "limit",
    "sort_key": "sort_key",
    "sort_dir": "sort_dir",
    "search_term": "search_term",
}

PARAM_MAP: dict[str, str] = {
    "limit": QUERY_PARAM_KEYS["limit"],
    "offset": QUERY_PARAM_KEYS["offset"],
    "sort_key": QUERY_PARAM_KEYS["sort_key"],
    "sort_dir": QUERY_PARAM_KEYS["sort_dir"],
    "search_term": QUERY_PARAM_KEYS["search_term"],
}


def construct_known_query_params(args: KnownQueryParams) -> dict[str, str]:
    query_params: dict[str, str] = {}

    for arg_key, value in args.items():
        param_key = PARAM_MAP.get(arg_key)
        if param_key is None:
            continue
        if value is None:
            continue
        if isinstance(value, str) and value.strip() == "":
            continue
        query_params[param_key] = str(value)

    return query_params
