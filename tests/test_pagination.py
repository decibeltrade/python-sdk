"""Tests for decibel._pagination module."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from decibel._pagination import (
    PaginatedResponse,
    construct_known_query_params,
)


class _Item(BaseModel):
    name: str
    value: int


class TestPaginatedResponse:
    def test_basic_model_validation(self) -> None:
        data = {"items": [{"name": "foo", "value": 1}], "total_count": 1}
        response = PaginatedResponse[_Item].model_validate(data)
        assert response.total_count == 1
        assert len(response.items) == 1
        assert response.items[0].name == "foo"

    def test_empty_items_list(self) -> None:
        data = {"items": [], "total_count": 0}
        response = PaginatedResponse[_Item].model_validate(data)
        assert response.total_count == 0
        assert response.items == []

    def test_multiple_items(self) -> None:
        data = {
            "items": [
                {"name": "a", "value": 1},
                {"name": "b", "value": 2},
                {"name": "c", "value": 3},
            ],
            "total_count": 3,
        }
        response = PaginatedResponse[_Item].model_validate(data)
        assert len(response.items) == 3
        assert response.items[1].name == "b"

    def test_total_count_can_differ_from_items_length(self) -> None:
        data = {"items": [{"name": "a", "value": 1}], "total_count": 100}
        response = PaginatedResponse[_Item].model_validate(data)
        assert response.total_count == 100
        assert len(response.items) == 1

    def test_missing_items_raises(self) -> None:
        with pytest.raises(ValidationError):
            PaginatedResponse[_Item].model_validate({"total_count": 0})

    def test_missing_total_count_raises(self) -> None:
        with pytest.raises(ValidationError):
            PaginatedResponse[_Item].model_validate({"items": []})


class TestConstructKnownQueryParams:
    def test_full_params(self) -> None:
        result = construct_known_query_params(
            {
                "limit": 10,
                "offset": 5,
                "sort_key": "volume",
                "sort_dir": "ASC",
                "search_term": "btc",
            }
        )
        assert result == {
            "limit": "10",
            "offset": "5",
            "sort_key": "volume",
            "sort_dir": "ASC",
            "search_term": "btc",
        }

    def test_partial_params_limit_only(self) -> None:
        result = construct_known_query_params({"limit": 20})
        assert result == {"limit": "20"}
        assert "offset" not in result

    def test_partial_params_sort_only(self) -> None:
        result = construct_known_query_params({"sort_key": "realized_pnl", "sort_dir": "DESC"})
        assert result == {"sort_key": "realized_pnl", "sort_dir": "DESC"}

    def test_empty_dict_returns_empty(self) -> None:
        result = construct_known_query_params({})
        assert result == {}

    def test_none_values_are_skipped(self) -> None:
        result = construct_known_query_params({"limit": 10, "sort_dir": None})  # type: ignore[typeddict-item]
        assert "sort_dir" not in result
        assert result["limit"] == "10"

    def test_empty_string_search_term_is_skipped(self) -> None:
        result = construct_known_query_params({"search_term": "   "})
        assert "search_term" not in result

    def test_empty_string_exactly_is_skipped(self) -> None:
        result = construct_known_query_params({"search_term": ""})
        assert "search_term" not in result

    def test_non_empty_search_term_is_included(self) -> None:
        result = construct_known_query_params({"search_term": "eth"})
        assert result["search_term"] == "eth"

    def test_integer_values_are_stringified(self) -> None:
        result = construct_known_query_params({"limit": 100, "offset": 0})
        assert result["limit"] == "100"
        assert result["offset"] == "0"

    def test_sort_dir_asc(self) -> None:
        result = construct_known_query_params({"sort_dir": "ASC"})
        assert result["sort_dir"] == "ASC"

    def test_sort_dir_desc(self) -> None:
        result = construct_known_query_params({"sort_dir": "DESC"})
        assert result["sort_dir"] == "DESC"

    def test_all_values_returned_as_strings(self) -> None:
        result = construct_known_query_params({"limit": 5, "offset": 0, "search_term": "market"})
        for v in result.values():
            assert isinstance(v, str)
