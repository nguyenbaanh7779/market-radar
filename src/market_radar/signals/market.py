"""Market state: index trend, volatility, breadth and liquidity."""

from __future__ import annotations

import numpy as np
import pandas as pd

from market_radar.config import SignalSettings
from market_radar.signals.indicators import (
    realized_vol,
    rolling_percentile,
    sma,
)

REGIMES = ("uptrend", "sideways", "downtrend")


def market_state(
    index_close: pd.Series,
    stock_closes: pd.DataFrame,
    settings: SignalSettings,
    traded_value: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Describe the market on every session.

    Args:
        index_close: VNINDEX closes indexed by date.
        stock_closes: Stock closes, dates by symbols.
        settings: Signal thresholds and windows.
        traded_value: Traded value (close x volume), dates by symbols, or
            None when the data source has no volume.

    Returns:
        Frame indexed by date with index returns, distances to MA20/MA50,
        20-day volatility and its percentile, breadth, liquidity ratio,
        ``regime`` and ``high_vol``.
    """
    close = index_close.sort_index()
    out = pd.DataFrame(index=close.index)
    out["idx_close"] = close
    for lag in (1, 5, 20):
        out[f"idx_ret_{lag}"] = close / close.shift(lag) - 1.0
    ma20, ma50 = sma(close, 20), sma(close, 50)
    out["idx_dist_ma20"] = close / ma20 - 1.0
    out["idx_dist_ma50"] = close / ma50 - 1.0
    out["idx_ma20_ma50"] = ma20 / ma50 - 1.0
    out["idx_vol_20"] = realized_vol(close, 20)
    out["idx_vol_pctile"] = rolling_percentile(
        out["idx_vol_20"], settings.vol_pctile_window)
    out = out.join(breadth(stock_closes.reindex(close.index)))
    out["liquidity_ratio"] = liquidity_ratio(traded_value, close.index)
    out["regime"] = classify_regime(close, ma20, ma50)
    out["high_vol"] = out["idx_vol_pctile"] >= settings.high_vol_pctile
    return out


def breadth(stock_closes: pd.DataFrame) -> pd.DataFrame:
    """Share of stocks rising and of stocks above their 20-day average.

    Args:
        stock_closes: Closes, dates by symbols.

    Returns:
        Columns ``breadth_up`` and ``breadth_above_ma20``.
    """
    returns = stock_closes / stock_closes.shift(1) - 1.0
    counted = returns.notna().sum(axis=1).replace(0, np.nan)
    ma20 = stock_closes.rolling(20, min_periods=20).mean()
    with_ma = ma20.notna().sum(axis=1).replace(0, np.nan)
    above = ((stock_closes > ma20) & ma20.notna()).sum(axis=1)
    return pd.DataFrame({
        "breadth_up": (returns > 0).sum(axis=1) / counted,
        "breadth_above_ma20": above / with_ma,
    })


def liquidity_ratio(
    traded_value: pd.DataFrame | None, dates: pd.DatetimeIndex
) -> pd.Series:
    """Market traded value relative to its previous 20-session average.

    Args:
        traded_value: Traded value, dates by symbols, or None.
        dates: Sessions to report on.

    Returns:
        The ratio, or NaN everywhere when there is no volume.
    """
    if traded_value is None:
        return pd.Series(np.nan, index=dates)
    total = traded_value.reindex(dates).sum(axis=1, min_count=1)
    average = total.rolling(20, min_periods=20).mean().shift(1)
    return total / average.replace(0.0, np.nan)


def classify_regime(
    close: pd.Series, ma20: pd.Series, ma50: pd.Series
) -> pd.Series:
    """Label the trend of the index.

    Args:
        close: Index closes.
        ma20: 20-session moving average.
        ma50: 50-session moving average.

    Returns:
        ``uptrend`` when close > MA20 > MA50, ``downtrend`` when
        close < MA20 < MA50, ``sideways`` otherwise (and before MA50).
    """
    up = (close > ma20) & (ma20 > ma50)
    down = (close < ma20) & (ma20 < ma50)
    labels = np.select([up, down], ["uptrend", "downtrend"], "sideways")
    return pd.Series(labels, index=close.index, dtype="str")
