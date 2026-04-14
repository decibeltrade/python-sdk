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
