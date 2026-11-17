"""Data-quality checks on stored bars and cross-source comparison."""

from __future__ import annotations

import numpy as np
import pandas as pd

from market_radar.config import Universe

PRICE_EPS = 1e-9


def close_returns_pct(bars: pd.DataFrame) -> pd.Series:
    """Compute close-to-close returns per symbol, in percent.

    Args:
        bars: Long bars sorted by symbol and date.

    Returns:
        Returns aligned with ``bars`` (NaN on each symbol's first row).
    """
    previous = bars.groupby("symbol", sort=False)["close"].shift(1)
    return (bars["close"] / previous - 1.0) * 100.0


def suspect_moves(
    bars: pd.DataFrame, universe: Universe, tolerance_pct: float = 0.5
) -> pd.DataFrame:
    """Find daily moves larger than the exchange price limit allows.

    Such jumps usually come from a corporate action that the price series
    is not adjusted for, so labels spanning them are not trustworthy.

    Args:
        bars: Long bars sorted by symbol and date.
        universe: Gives each symbol's exchange price limit.
        tolerance_pct: Slack added to the limit, in percentage points.

    Returns:
        Rows ``symbol``, ``date``, ``ret_pct`` and ``limit_pct``.
    """
    returns = close_returns_pct(bars)
    limits = bars["symbol"].map(universe.price_limit_pct).astype(float)
    mask = returns.abs() > limits + tolerance_pct
    out = bars.loc[mask, ["symbol", "date"]].copy()
    out["ret_pct"] = returns[mask].round(2)
    out["limit_pct"] = limits[mask]
    return out.reset_index(drop=True)


def quality_report(
    bars: pd.DataFrame, sessions: pd.DatetimeIndex, universe: Universe
) -> pd.DataFrame:
    """Summarise data quality per symbol.

    Args:
        bars: Long bars sorted by symbol and date.
        sessions: Realised trading sessions (e.g. VNINDEX dates).
        universe: Gives each symbol's exchange price limit.

    Returns:
        One row per symbol with row count, first/last date, sessions
        missing between them, duplicate dates, inconsistent OHLC rows,
        moves beyond the price limit and the share of bars with volume.
    """
    breaches = suspect_moves(bars, universe)["symbol"].value_counts()
    rows = []
    for symbol, frame in bars.groupby("symbol", sort=True):
        dates = pd.DatetimeIndex(frame["date"])
        span = sessions[(sessions >= dates.min()) & (sessions <= dates.max())]
        rows.append({
            "symbol": symbol,
            "rows": len(frame),
            "first_date": dates.min().date(),
            "last_date": dates.max().date(),
            "missing_sessions": int((~span.isin(dates)).sum()),
            "duplicate_dates": int(dates.duplicated().sum()),
            "bad_ohlc": int(_bad_ohlc(frame).sum()),
            "limit_breaches": int(breaches.get(symbol, 0)),
            "volume_coverage": round(float(frame["volume"].notna().mean()),
                                     3),
        })
    return pd.DataFrame(rows)


def _bad_ohlc(frame: pd.DataFrame) -> pd.Series:
    """Flag bars whose OHLC values are inconsistent.

    Args:
        frame: Bars of one symbol.

    Returns:
        Boolean mask: non-positive prices, a high below the open or close,
        or a low above the open or close.
    """
    prices = frame[["open", "high", "low", "close"]]
    body_high = frame[["open", "close"]].max(axis=1)
    body_low = frame[["open", "close"]].min(axis=1)
    non_positive = (prices <= 0).any(axis=1)
    high_bad = frame["high"] < body_high - PRICE_EPS
    low_bad = frame["low"] > body_low + PRICE_EPS
    return non_positive | high_bad.fillna(False) | low_bad.fillna(False)


def compare_closes(left: pd.DataFrame, right: pd.DataFrame) -> pd.DataFrame:
    """Compare closing prices of two sources on their common dates.

    Args:
        left: Long bars from the first source.
        right: Long bars from the second source.

    Returns:
        One row per common symbol: common dates, median and maximum
        absolute difference in basis points, and the share of dates that
        differ by more than 50 bps.
    """
    merged = left[["symbol", "date", "close"]].merge(
        right[["symbol", "date", "close"]],
        on=["symbol", "date"],
        suffixes=("_left", "_right"),
    )
    diff_bps = (merged["close_left"] / merged["close_right"] - 1.0) * 1e4
    merged["abs_bps"] = np.abs(diff_bps)
    summary = merged.groupby("symbol")["abs_bps"].agg(
        common_dates="size",
        median_abs_bps="median",
        max_abs_bps="max",
        share_over_50bps=lambda values: float((values > 50).mean()),
    )
    return summary.round(3).reset_index()
