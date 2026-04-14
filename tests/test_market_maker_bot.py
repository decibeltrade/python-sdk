from __future__ import annotations

import argparse
import asyncio
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


def _load_market_maker_module():
    file_path = Path(__file__).resolve().parents[1] / "examples" / "write" / "market_maker_bot.py"
    spec = importlib.util.spec_from_file_location("market_maker_bot", file_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("failed to load market maker bot module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _fake_market():
    return SimpleNamespace(
        market_name="BTC/USD",
        market_addr="0xabc",
        tick_size=100,
        lot_size=1000,
        min_size=100,
        px_decimals=2,
        sz_decimals=4,
    )


def test_cancel_market_orders_dry_run_without_write(capsys: pytest.CaptureFixture[str]) -> None:
    mm = _load_market_maker_module()
    cancelled, failed = asyncio.run(
        mm._cancel_market_orders(
            write=None,
            market_name="BTC/USD",
            order_ids=["1", "2"],
            subaccount_addr="0xsub",
            dry_run=True,
        )
    )
    out = capsys.readouterr().out
    assert "would cancel 1" in out
    assert "would cancel 2" in out
    assert cancelled == 2
    assert failed == 0


def test_compute_quotes_size_invalid_status() -> None:
    mm = _load_market_maker_module()
    market = _fake_market()
    settings = mm.MMSettings(order_size=0.0)
    decision = mm._compute_quotes(
        mid=100000.0,
        inventory=0.0,
        market=market,
        settings=settings,
    )
    assert decision.status is mm.QuoteStatus.PAUSE_SIZE_INVALID


def test_compute_quotes_negative_size_invalid_status() -> None:
    mm = _load_market_maker_module()
    market = _fake_market()
    settings = mm.MMSettings(order_size=-0.001)
    decision = mm._compute_quotes(
        mid=100000.0,
        inventory=0.0,
        market=market,
        settings=settings,
    )
    assert decision.status is mm.QuoteStatus.PAUSE_SIZE_INVALID


def test_compute_quotes_inventory_limit_status() -> None:
    mm = _load_market_maker_module()
    market = _fake_market()
    settings = mm.MMSettings(max_inventory=0.01, order_size=0.001)
    decision = mm._compute_quotes(
        mid=100000.0,
        inventory=0.01,
        market=market,
        settings=settings,
    )
    assert decision.status is mm.QuoteStatus.PAUSE_INVENTORY_LIMIT


def test_compute_quotes_spread_too_tight_raises() -> None:
    mm = _load_market_maker_module()
    market = _fake_market()
    settings = mm.MMSettings(spread=0.000001)
    with pytest.raises(ValueError):
        mm._compute_quotes(
            mid=100000.0,
            inventory=0.0,
            market=market,
            settings=settings,
        )


@pytest.mark.parametrize("spread", [float("nan"), float("inf")])
def test_compute_quotes_non_finite_spread_raises(spread: float) -> None:
    mm = _load_market_maker_module()
    market = _fake_market()
    settings = mm.MMSettings(spread=spread)
    with pytest.raises(ValueError, match="spread must be a finite value > 0"):
        mm._compute_quotes(
            mid=100000.0,
            inventory=0.0,
            market=market,
            settings=settings,
        )


def test_compute_quotes_extreme_skew_raises() -> None:
    mm = _load_market_maker_module()
    market = _fake_market()
    settings = mm.MMSettings(skew_per_unit=2.0, max_inventory=10.0)
    with pytest.raises(ValueError, match="adjust --skew-per-unit or --max-inventory"):
        mm._compute_quotes(
            mid=100000.0,
            inventory=1.0,
            market=market,
            settings=settings,
        )


def test_parse_args_accepts_named_config_network_key(monkeypatch: pytest.MonkeyPatch) -> None:
    mm = _load_market_maker_module()
    network_key = "local" if "local" in mm.NAMED_CONFIGS else next(iter(mm.NAMED_CONFIGS))
    monkeypatch.setattr(sys, "argv", ["market_maker_bot.py", "--network", network_key])
    args = mm._parse_args()
    assert args.network == network_key


def test_place_quote_dry_run_uses_price_x_size(capsys: pytest.CaptureFixture[str]) -> None:
    mm = _load_market_maker_module()
    market = _fake_market()
    asyncio.run(
        mm._place_quote(
            write=None,
            market=market,
            subaccount_addr="0xsub",
            is_buy=True,
            price=100.5,
            size=0.002,
            dry_run=True,
        )
    )
    out = capsys.readouterr().out
    assert "would place bid: 100.5 x 0.002" in out


def test_sync_state_uses_mid_px_without_falsy_fallback() -> None:
    mm = _load_market_maker_module()
    market = _fake_market()

    class _FakeAccountOverview:
        async def get_by_addr(self, sub_addr):
            return SimpleNamespace(cross_margin_ratio=0.1)

    class _FakeUserPositions:
        async def get_by_addr(self, sub_addr, limit):
            return [SimpleNamespace(market=market.market_addr, size=0.0)]

    class _FakeUserOpenOrders:
        async def get_by_addr(self, sub_addr, limit):
            return SimpleNamespace(items=[])

    class _FakeMarketPrices:
        async def get_by_name(self, market_name):
            assert market_name == market.market_name
            return [SimpleNamespace(market=market.market_addr, mid_px=0.0, mark_px=12345.0)]

    class _FakeRead:
        account_overview = _FakeAccountOverview()
        user_positions = _FakeUserPositions()
        user_open_orders = _FakeUserOpenOrders()
        market_prices = _FakeMarketPrices()

    mid, *_ = asyncio.run(mm._sync_state(_FakeRead(), market, "0xsub"))
    assert mid == 0.0


def test_main_returns_nonzero_for_value_error(monkeypatch: pytest.MonkeyPatch) -> None:
    mm = _load_market_maker_module()
    market = _fake_market()

    class _FakeMarkets:
        async def get_all(self):
            return [market]

    class _FakeWs:
        async def close(self):
            return None

    class _FakeReadDex:
        def __init__(self, config, api_key=None):
            self.markets = _FakeMarkets()
            self.ws = _FakeWs()

    async def _fake_run_cycle(*args, **kwargs):
        raise ValueError("bad spread")

    monkeypatch.setattr(
        mm,
        "_parse_args",
        lambda: argparse.Namespace(
            network="testnet",
            market="BTC/USD",
            spread=0.001,
            order_size=0.001,
            max_inventory=0.005,
            skew_per_unit=0.0001,
            max_margin_usage=0.5,
            refresh_interval=0.01,
            cooldown=0.0,
            cancel_resync=0.0,
            max_cycles=1,
            dry_run=True,
        ),
    )
    monkeypatch.setattr(mm, "DecibelReadDex", _FakeReadDex)
    monkeypatch.setattr(mm, "_resolve_market", lambda markets, requested: market)
    monkeypatch.setattr(mm, "_run_cycle", _fake_run_cycle)
    monkeypatch.setenv("SUBACCOUNT_ADDRESS", "0xsub")
    monkeypatch.delenv("PRIVATE_KEY", raising=False)
    monkeypatch.delenv("APTOS_NODE_API_KEY", raising=False)

    exit_code = asyncio.run(mm.main())
    assert exit_code == 2


@pytest.mark.parametrize(
    ("mid", "margin_usage"),
    [
        (100000.0, 0.9),  # margin guard
        (None, 0.1),  # no-price guard
    ],
)
def test_run_cycle_pause_guards_cancel_resting_orders(
    monkeypatch: pytest.MonkeyPatch, mid: float | None, margin_usage: float
) -> None:
    mm = _load_market_maker_module()
    market = _fake_market()
    settings = mm.MMSettings(dry_run=True, max_margin_usage=0.5)

    async def _fake_sync_state(read, market_arg, subaccount_addr):
        assert market_arg is market
        assert subaccount_addr == "0xsub"
        return mid, 0.0, margin_usage, ["oid-1", "oid-2"]

    calls: list[list[str]] = []

    async def _fake_cancel_market_orders(
        write, market_name, order_ids, subaccount_addr, dry_run
    ) -> tuple[int, int]:
        assert write is None
        assert market_name == "BTC/USD"
        assert subaccount_addr == "0xsub"
        assert dry_run is True
        calls.append(order_ids)
        return len(order_ids), 0

    monkeypatch.setattr(mm, "_sync_state", _fake_sync_state)
    monkeypatch.setattr(mm, "_cancel_market_orders", _fake_cancel_market_orders)

    asyncio.run(
        mm._run_cycle(
            1,
            read=SimpleNamespace(),
            write=None,
            market=market,
            subaccount_addr="0xsub",
            settings=settings,
        )
    )
    assert calls == [["oid-1", "oid-2"]]
