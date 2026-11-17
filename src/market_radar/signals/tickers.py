"""Rule-based technical flags per stock: strong, caution or neutral."""

from __future__ import annotations

import math

import pandas as pd

from market_radar.config import SignalSettings

FLAGS = ("strong", "neutral", "caution")


def ticker_flags(
    snapshot: pd.DataFrame, settings: SignalSettings
) -> pd.DataFrame:
    """Flag each stock from its indicators on one session.

    A stock is ``strong`` when it is in an uptrend (close above MA20 and
    MA20 above MA50) with a positive MACD histogram and RSI in the strong
    band. It gets ``caution`` when it is overbought, below MA50 with a
    negative MACD histogram, or below the lower Bollinger band. Caution
    wins when both apply.

    Args:
        snapshot: One row per symbol (index) with ``rsi_14``,
            ``macd_hist_norm``, ``dist_ma20``, ``dist_ma50``, ``ma20_ma50``,
            ``bb_pct_b`` and optionally ``vol_ratio_20``.
        settings: Signal thresholds.

    Returns:
        Columns ``flag`` and ``reasons`` (``; ``-separated), by symbol.
    """
    rows = {
        symbol: _flag_one(row, settings)
        for symbol, row in snapshot.iterrows()
    }
    return pd.DataFrame.from_dict(
        rows, orient="index", columns=["flag", "reasons"])


def _flag_one(row: pd.Series, settings: SignalSettings) -> tuple[str, str]:
    """Apply the flag rules to one stock.

    Args:
        row: Indicator values of the stock.
        settings: Signal thresholds.

    Returns:
        The flag and the reasons behind it.
    """
    rsi = row.get("rsi_14", math.nan)
    hist = row.get("macd_hist_norm", math.nan)
    uptrend = row.get("dist_ma20", math.nan) > 0 and (
        row.get("ma20_ma50", math.nan) > 0)
    caution = []
    if rsi >= settings.rsi_overbought:
        caution.append(f"overbought (RSI {rsi:.0f})")
    if row.get("dist_ma50", math.nan) < 0 and hist < 0:
        caution.append("below MA50 with negative MACD")
    if row.get("bb_pct_b", math.nan) < 0:
        caution.append("below lower Bollinger band")
    if caution:
        return "caution", "; ".join(caution)
    in_band = settings.rsi_strong_low <= rsi <= settings.rsi_strong_high
    if uptrend and hist > 0 and in_band:
        reasons = ["uptrend (close > MA20 > MA50)", "MACD histogram > 0",
                   f"RSI {rsi:.0f}"]
        spike = row.get("vol_ratio_20", math.nan)
        if spike >= settings.volume_spike_ratio:
            reasons.append(f"volume {spike:.1f}x 20-day average")
        return "strong", "; ".join(reasons)
    return "neutral", ""
