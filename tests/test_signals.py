import datetime as dt

import numpy as np
import pandas as pd
import pytest

from market_radar.config import SignalSettings
from market_radar.signals.market import market_state
from market_radar.signals.portfolio import (
    Holding,
    load_holdings,
    portfolio_status,
)
from market_radar.signals.sectors import (
    basket_bars,
    relative_rotation,
    sector_closes,
)
from market_radar.signals.tickers import ticker_flags


def pivot(bars, column="close"):
    return bars.pivot(index="date", columns="symbol", values=column)


def test_market_state_columns_and_ranges(bars, universe):
    closes = pivot(bars)
    state = market_state(closes["VNINDEX"], closes[list(universe.stocks)],
                         SignalSettings())
    assert state["breadth_up"].dropna().between(0, 1).all()
    assert set(state["regime"].unique()) <= {
        "uptrend", "sideways", "downtrend"}
    assert state["liquidity_ratio"].isna().all()
    assert state["idx_vol_pctile"].dropna().between(0, 1).all()


def test_market_state_with_volume(bars, universe):
    closes = pivot(bars)
    value = closes * pivot(bars, "volume")
    state = market_state(closes["VNINDEX"], closes[list(universe.stocks)],
                         SignalSettings(), traded_value=value)
    assert state["liquidity_ratio"].notna().sum() > 300


def test_basket_follows_average_member_return():
    dates = pd.bdate_range("2026-01-05", periods=3)
    frame = pd.DataFrame({
        "symbol": ["A"] * 3 + ["B"] * 3,
        "date": list(dates) * 2,
        "open": [10, 11, 12, 20, 20, 18],
        "high": [10, 11, 12, 20, 20, 18],
        "low": [10, 11, 12, 20, 20, 18],
        "close": [10.0, 11.0, 12.1, 20.0, 20.0, 18.0],
    })
    basket = basket_bars(frame, ["A", "B"])
    # day 2: (+10% + 0%) / 2 = +5%; day 3: (+10% - 10%) / 2 = 0%
    assert basket["close"].round(6).tolist() == [105.0, 105.0]
    assert (basket["high"] >= basket[["open", "close"]].max(axis=1)).all()
    assert (basket["low"] <= basket[["open", "close"]].min(axis=1)).all()


def test_relative_rotation_quadrants(bars, universe):
    closes = sector_closes(bars, universe.sectors)
    assert set(closes.columns) == {"banking", "technology"}  # energy has 1
    rrg = relative_rotation(closes, pivot(bars)["VNINDEX"], window=20,
                            momentum_lag=5)
    assert set(rrg["quadrant"]) <= {
        "leading", "weakening", "lagging", "improving"}
    last = rrg[rrg["date"] == rrg["date"].max()]
    assert sorted(last["rank"]) == [1, 2]
    leading = rrg[(rrg["rs_ratio"] >= 100) & (rrg["rs_momentum"] >= 100)]
    assert (leading["quadrant"] == "leading").all()


def test_ticker_flags_rules():
    snapshot = pd.DataFrame({
        "rsi_14": [60.0, 80.0, 55.0],
        "macd_hist_norm": [0.01, 0.01, -0.01],
        "dist_ma20": [0.02, 0.05, -0.03],
        "dist_ma50": [0.04, 0.08, -0.05],
        "ma20_ma50": [0.01, 0.02, -0.01],
        "bb_pct_b": [0.7, 1.1, 0.2],
        "vol_ratio_20": [2.0, 1.0, 1.0],
    }, index=["UP", "HOT", "DOWN"])
    flags = ticker_flags(snapshot, SignalSettings())
    assert flags["flag"].to_dict() == {
        "UP": "strong", "HOT": "caution", "DOWN": "caution"}
    assert "volume 2.0x" in flags.loc["UP", "reasons"]
    assert "overbought" in flags.loc["HOT", "reasons"]


def test_load_holdings(tmp_path):
    path = tmp_path / "portfolio.yaml"
    path.write_text("since: '2026-11-02'\nholdings:\n"
                    "  - {symbol: aaa, quantity: 100, avg_price: 10}\n")
    holdings, since = load_holdings(path)
    assert holdings == [Holding("AAA", 100, 10.0)]
    assert since == dt.date(2026, 11, 2)
    assert load_holdings(tmp_path / "missing.yaml") == ([], None)


def test_portfolio_status(universe):
    dates = pd.bdate_range("2026-11-02", periods=3)
    closes = pd.DataFrame({"AAA": [10.0, 11.0, 12.0],
                           "BBB": [20.0, 19.0, 18.0],
                           "VN30": [100.0, 101.0, 102.0]}, index=dates)
    flags = pd.DataFrame({"flag": ["strong", "caution"]},
                         index=["AAA", "BBB"])
    status = portfolio_status(
        [Holding("AAA", 100, 10.0), Holding("BBB", 100, 20.0)],
        closes, dates[-1], universe.sector_of,
        {"technology": "leading", "banking": "lagging"}, flags, "VN30",
        dt.date(2026, 11, 2), 1000.0)
    assert status["value_vnd"] == pytest.approx(3_000_000)
    assert status["pnl_vnd"] == pytest.approx(0.0)
    assert status["benchmark_return_pct"] == pytest.approx(2.0)
    assert status["top_contributor"] == "AAA"
    assert status["warnings"] == [
        "BBB: weak technical signal, sector is lagging"]
    assert np.isclose(sum(status["sector_weights"].values()), 1.0)
    assert portfolio_status([], closes, dates[-1], universe.sector_of, {},
                            flags, "VN30", None, 1000.0) is None
