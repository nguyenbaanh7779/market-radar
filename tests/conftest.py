"""Shared fixtures: a small universe and synthetic market data."""

from __future__ import annotations

import dataclasses
import datetime as dt
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from market_radar.config import Settings, Universe, load_settings

REPO_ROOT = Path(__file__).resolve().parents[1]

STOCKS = ("AAA", "BBB", "CCC", "DDD", "EEE", "FFF")


def make_universe() -> Universe:
    """Build a small universe used across tests."""
    return Universe(
        as_of=dt.date(2026, 11, 17),
        indices=("VNINDEX", "VN30"),
        baskets={"BANKS": "banking"},
        vn30=("AAA", "BBB", "CCC"),
        vn30_verified=True,
        banks=("BBB", "CCC", "DDD"),
        sectors={
            "banking": ("BBB", "CCC", "DDD"),
            "technology": ("AAA", "EEE"),
            "energy": ("FFF",),
        },
        exchanges={"FFF": "HNX"},
        price_limits_pct={"HOSE": 7.0, "HNX": 10.0, "UPCOM": 15.0},
    )


def make_bars(
    symbols=("VNINDEX", "VN30", *STOCKS),
    sessions: int = 420,
    start: str = "2022-01-03",
    seed: int = 7,
    with_volume: bool = True,
) -> pd.DataFrame:
    """Generate consistent random-walk OHLCV bars on business days."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(start=start, periods=sessions)
    market = rng.normal(0.0004, 0.01, sessions)
    frames = []
    for i, symbol in enumerate(symbols):
        own = rng.normal(0.0, 0.012, sessions)
        returns = np.clip(market + own, -0.065, 0.065)
        base = 1000.0 if symbol in ("VNINDEX", "VN30") else 20.0 + 5 * i
        close = base * np.cumprod(1.0 + returns)
        previous = np.concatenate([[base], close[:-1]])
        opening = previous * (1.0 + rng.normal(0.0, 0.003, sessions))
        high = np.maximum(opening, close) * (
            1.0 + np.abs(rng.normal(0, 0.004, sessions))
        )
        low = np.minimum(opening, close) * (
            1.0 - np.abs(rng.normal(0, 0.004, sessions))
        )
        volume = (
            rng.integers(100_000, 1_000_000, sessions).astype(float)
            if with_volume
            else np.full(sessions, np.nan)
        )
        frames.append(pd.DataFrame({
            "symbol": symbol,
            "date": dates,
            "open": opening,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
            "source": "synthetic",
        }))
    return pd.concat(frames, ignore_index=True)


@pytest.fixture
def universe() -> Universe:
    """Small test universe."""
    return make_universe()


@pytest.fixture
def bars() -> pd.DataFrame:
    """Synthetic bars for the test universe."""
    return make_bars()


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """Repository settings with a small universe and fast validation."""
    loaded = load_settings(
        REPO_ROOT,
        overrides={
            "data": {"fetch_start": "2022-01-01",
                     "sample_start": "2022-04-01"},
            "walk_forward": {"min_train_sessions": 120, "test_sessions": 40,
                             "embargo_sessions": 2},
            "models": {"gbdt": {"n_estimators": 30, "num_leaves": 7,
                                "min_child_samples": 20}},
        },
    )
    return dataclasses.replace(
        loaded, root=tmp_path, universe=make_universe(), holidays=frozenset()
    )
