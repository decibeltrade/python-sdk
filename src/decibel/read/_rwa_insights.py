"""RWA (real-world asset) fundamentals DTOs.

These mirror the shapes served by the Decibel BFF, which proxies the Massive REST API. They are
shared types only — there is deliberately no ``DecibelReadDex`` reader for them, because the data
comes from the BFF rather than ``trading_http_url``.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

__all__ = [
    "RWA_TICKERS",
    "RwaAfterHours",
    "RwaAnalystRatings",
    "RwaDateStatus",
    "RwaEarningsQuarter",
    "RwaInsights",
    "RwaKeyStatistics",
    "RwaSession",
    "is_rwa_ticker",
]

RWA_TICKERS: tuple[str, ...] = (
    "NVDA",
    "NFLX",
    "AAPL",
    "TSLA",
    "AMZN",
    "GOOGL",
    "MSFT",
    "META",
    # Recent IPO (listed 2026-06-12). "SPCX" is a reused ticker, so the provider clips its price
    # history to the listing date to keep the prior instrument's bars out of the volume /
    # 52-week stats; the 52-week range stays unavailable until a full year of real trading exists.
    "SPCX",
    # Crypto-adjacent and fintech equities
    "MSTR",
    "COIN",
    "CRCL",
    "HOOD",
    # Semiconductors and hardware
    "AMD",
    "INTC",
    "ARM",
    "MRVL",
    "QCOM",
    "MU",
    # Enterprise tech
    "IBM",
    # International ADRs on US exchanges
    "ASML",
    "BABA",
)
"""Allowlist of tickers backed by RWA fundamentals.

Shared by the web app (to gate the Insights tab / after-hours stat) and the BFF (to reject
requests for unsupported tickers before proxying the metered upstream).
"""

_RWA_TICKER_SET = frozenset(RWA_TICKERS)

RwaDateStatus = Literal["projected", "confirmed"]

RwaSession = Literal["pre-market", "after-hours", "closed"]


def is_rwa_ticker(ticker: str) -> bool:
    """Whether ``ticker`` is a supported RWA market ticker (case-sensitive, uppercase)."""
    return ticker in _RWA_TICKER_SET


class RwaEarningsQuarter(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    fiscal_period: str
    fiscal_year: int
    estimated_eps: float | None
    actual_eps: float | None
    eps_surprise_pct: float | None
    report_date: str
    date_status: RwaDateStatus


class RwaAnalystRatings(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    total_analysts: int
    strong_buy: int
    buy: int
    hold: int
    sell: int
    strong_sell: int
    consensus_price_target: float
    high_price_target: float
    low_price_target: float


class RwaKeyStatistics(BaseModel):
    """Every field is nullable: an account may not be entitled to every upstream endpoint (e.g.
    the real-time snapshot), so consumers render what's missing as unavailable rather than
    failing the whole panel."""

    model_config = ConfigDict(populate_by_name=True)

    market_cap: float | None
    volume: float | None
    average_volume: float | None
    pe_ratio: float | None
    week52_high: float | None
    week52_low: float | None


class RwaInsights(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    ticker: str
    earnings: list[RwaEarningsQuarter]
    analyst_ratings: RwaAnalystRatings
    key_statistics: RwaKeyStatistics


class RwaAfterHours(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    ticker: str
    price: float
    previous_close: float
    change: float
    change_pct: float
    session: RwaSession
