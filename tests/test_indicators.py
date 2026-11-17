import numpy as np
import pandas as pd
import pytest

from market_radar.signals import indicators as ind


def series(values):
    return pd.Series(values, dtype=float,
                     index=pd.bdate_range("2026-01-05", periods=len(values)))


def test_sma_and_ema_warm_up():
    s = series(range(1, 11))
    assert ind.sma(s, 3).iloc[2] == pytest.approx(2.0)
    assert ind.sma(s, 3).iloc[:2].isna().all()
    assert ind.ema(s, 3).iloc[:2].isna().all()


def test_rsi_extremes_and_bounds():
    rising = series(np.arange(1, 40))
    flat = series(np.full(40, 5.0))
    noisy = series(np.random.default_rng(1).normal(100, 1, 200))
    assert ind.rsi(rising).iloc[-1] == 100.0
    assert ind.rsi(flat).iloc[-1] == 50.0
    values = ind.rsi(noisy).dropna()
    assert values.between(0, 100).all()


def test_macd_of_constant_series_is_zero():
    out = ind.macd(series(np.full(60, 10.0)))
    assert out["hist"].dropna().abs().max() == pytest.approx(0.0)


def test_bollinger_pct_b_at_the_mean():
    s = series([1.0, 2.0, 3.0, 2.0, 1.0, 2.0, 3.0, 2.0])
    pct_b = ind.bollinger_pct_b(s, window=4)
    # close equals the 4-session mean -> %B = 0.5
    assert pct_b.iloc[3] == pytest.approx(0.5)


def test_atr_and_realized_vol_are_positive():
    rng = np.random.default_rng(2)
    close = series(100 * np.cumprod(1 + rng.normal(0, 0.01, 80)))
    high, low = close * 1.01, close * 0.99
    assert (ind.atr(high, low, close).dropna() > 0).all()
    assert (ind.realized_vol(close).dropna() > 0).all()


def test_volume_ratio_uses_previous_sessions_only():
    vol = series([10.0] * 20 + [30.0])
    assert ind.volume_ratio(vol).iloc[-1] == pytest.approx(3.0)


def test_rolling_percentile():
    s = series(range(1, 101))
    pct = ind.rolling_percentile(s, window=50, min_periods=10)
    assert pct.iloc[-1] == 1.0
    assert pct.iloc[:9].isna().all()
