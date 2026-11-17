"""Technical indicators on a single price series (pandas only).

Every indicator at row ``t`` uses data up to and including ``t``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def sma(series: pd.Series, window: int) -> pd.Series:
    """Simple moving average.

    Args:
        series: Input values.
        window: Number of observations.

    Returns:
        The rolling mean (NaN until ``window`` values exist).
    """
    return series.rolling(window, min_periods=window).mean()


def ema(series: pd.Series, span: int) -> pd.Series:
    """Exponential moving average.

    Args:
        series: Input values.
        span: EMA span.

    Returns:
        The EMA (NaN until ``span`` values exist).
    """
    return series.ewm(span=span, adjust=False, min_periods=span).mean()


def rsi(close: pd.Series, window: int = 14) -> pd.Series:
    """Relative Strength Index with Wilder smoothing.

    Args:
        close: Closing prices.
        window: Smoothing window.

    Returns:
        RSI between 0 and 100 (100 when there are no losses, 50 when the
        price does not move).
    """
    delta = close.diff()
    alpha = 1.0 / window
    gain = delta.clip(lower=0).ewm(
        alpha=alpha, adjust=False, min_periods=window).mean()
    loss = (-delta.clip(upper=0)).ewm(
        alpha=alpha, adjust=False, min_periods=window).mean()
    ratio = gain / loss.replace(0.0, np.nan)
    value = 100.0 - 100.0 / (1.0 + ratio)
    value = value.mask((loss == 0) & (gain > 0), 100.0)
    return value.mask((loss == 0) & (gain == 0), 50.0)


def macd(
    close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> pd.DataFrame:
    """Moving Average Convergence Divergence.

    Args:
        close: Closing prices.
        fast: Fast EMA span.
        slow: Slow EMA span.
        signal: Signal-line EMA span.

    Returns:
        Columns ``macd``, ``signal`` and ``hist`` (macd minus signal).
    """
    line = ema(close, fast) - ema(close, slow)
    signal_line = ema(line, signal)
    return pd.DataFrame(
        {"macd": line, "signal": signal_line, "hist": line - signal_line}
    )


def bollinger_pct_b(
    close: pd.Series, window: int = 20, n_std: float = 2.0
) -> pd.Series:
    """Position of the close inside the Bollinger bands (%B).

    Args:
        close: Closing prices.
        window: Moving-average window.
        n_std: Band width in standard deviations.

    Returns:
        0 at the lower band, 0.5 at the mean, 1 at the upper band.
    """
    mid = sma(close, window)
    std = close.rolling(window, min_periods=window).std(ddof=0)
    lower = mid - n_std * std
    width = (2 * n_std * std).replace(0.0, np.nan)
    return (close - lower) / width


def true_range(
    high: pd.Series, low: pd.Series, close: pd.Series
) -> pd.Series:
    """True range of each bar.

    Args:
        high: Highs.
        low: Lows.
        close: Closes.

    Returns:
        The largest of high-low and the gaps to the previous close.
    """
    previous = close.shift(1)
    ranges = pd.concat(
        [high - low, (high - previous).abs(), (low - previous).abs()],
        axis=1,
    )
    return ranges.max(axis=1, skipna=True)


def atr(
    high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14
) -> pd.Series:
    """Average True Range with Wilder smoothing.

    Args:
        high: Highs.
        low: Lows.
        close: Closes.
        window: Smoothing window.

    Returns:
        The ATR in price units.
    """
    return true_range(high, low, close).ewm(
        alpha=1.0 / window, adjust=False, min_periods=window).mean()


def realized_vol(close: pd.Series, window: int = 20) -> pd.Series:
    """Annualised volatility of daily log returns.

    Args:
        close: Closing prices.
        window: Number of returns.

    Returns:
        Rolling standard deviation times sqrt(252).
    """
    log_returns = np.log(close / close.shift(1))
    std = log_returns.rolling(window, min_periods=window).std()
    return std * np.sqrt(TRADING_DAYS)


def volume_ratio(volume: pd.Series, window: int = 20) -> pd.Series:
    """Today's volume relative to the average of the previous sessions.

    Args:
        volume: Traded volume.
        window: Number of previous sessions averaged.

    Returns:
        Volume divided by the mean of the ``window`` sessions before it.
    """
    average = volume.rolling(window, min_periods=window).mean().shift(1)
    return volume / average.replace(0.0, np.nan)


def rolling_percentile(
    series: pd.Series, window: int, min_periods: int = 60
) -> pd.Series:
    """Percentile rank of each value within its trailing window.

    Args:
        series: Input values.
        window: Trailing window length.
        min_periods: Values needed before a rank is reported.

    Returns:
        Share of values in the window that are at or below the current one.
    """
    def rank_last(values: np.ndarray) -> float:
        """Rank the last value of a window among all its values."""
        valid = values[~np.isnan(values)]
        if valid.size == 0 or np.isnan(values[-1]):
            return np.nan
        return float((valid <= values[-1]).mean())

    return series.rolling(window, min_periods=min_periods).apply(
        rank_last, raw=True)
