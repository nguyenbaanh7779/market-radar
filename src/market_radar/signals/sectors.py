"""Sector baskets and an RRG-style view of sector rotation.

The relative rotation view follows the idea of Relative Rotation Graphs:
each sector's strength relative to VNINDEX (RS-ratio) and the change of
that strength (RS-momentum). The formulas here are a transparent
approximation, not the proprietary JdK indicators.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

import numpy as np
import pandas as pd

QUADRANTS = ("leading", "weakening", "lagging", "improving")


def basket_bars(
    bars: pd.DataFrame, members: Iterable[str], min_members: int = 2
) -> pd.DataFrame:
    """Build daily OHLC of an equal-weight basket (index base 100).

    Each session the basket moves by the average return of the members
    that traded; open, high and low use the members' average gap from
    their previous close, so the basket bars stay internally consistent.

    Args:
        bars: Long bars sorted by symbol and date.
        members: Basket constituents.
        min_members: Members needed on a session for it to count.

    Returns:
        Frame with ``date``, ``open``, ``high``, ``low``, ``close``,
        ``volume`` (NaN) and ``n_members``.
    """
    frame = bars[bars["symbol"].isin(set(members))]
    previous = frame.groupby("symbol", sort=False)["close"].shift(1)
    relative = pd.DataFrame({
        "date": frame["date"],
        "r_open": frame["open"] / previous,
        "r_high": frame["high"] / previous,
        "r_low": frame["low"] / previous,
        "r_close": frame["close"] / previous,
    }).dropna(subset=["r_close"])
    daily = relative.groupby("date").agg(
        r_open=("r_open", "mean"),
        r_high=("r_high", "mean"),
        r_low=("r_low", "mean"),
        r_close=("r_close", "mean"),
        n_members=("r_close", "size"),
    )
    daily = daily[daily["n_members"] >= min_members].sort_index()
    if daily.empty:
        return pd.DataFrame(
            columns=["date", "open", "high", "low", "close", "volume",
                     "n_members"])
    close = 100.0 * daily["r_close"].cumprod()
    base = close.shift(1).fillna(100.0)
    out = pd.DataFrame({
        "date": daily.index,
        "open": (base * daily["r_open"].fillna(1.0)).to_numpy(),
        "high": (base * daily["r_high"]).to_numpy(),
        "low": (base * daily["r_low"]).to_numpy(),
        "close": close.to_numpy(),
        "volume": np.nan,
        "n_members": daily["n_members"].to_numpy(),
    })
    out["high"] = out[["high", "open", "close"]].max(axis=1)
    out["low"] = out[["low", "open", "close"]].min(axis=1)
    return out


def sector_closes(
    bars: pd.DataFrame, sectors: Mapping[str, Iterable[str]]
) -> pd.DataFrame:
    """Equal-weight index of every sector.

    Args:
        bars: Long bars sorted by symbol and date.
        sectors: Sector name to member symbols.

    Returns:
        Basket closes, dates by sectors.
    """
    columns = {}
    for sector, members in sectors.items():
        basket = basket_bars(bars, members)
        if not basket.empty:
            columns[sector] = basket.set_index("date")["close"]
    return pd.DataFrame(columns).sort_index()


def relative_rotation(
    closes: pd.DataFrame,
    benchmark: pd.Series,
    window: int = 50,
    momentum_lag: int = 10,
) -> pd.DataFrame:
    """Compute RS-ratio, RS-momentum, quadrant and rank of each sector.

    ``rs = sector / benchmark``; ``rs_ratio = 100 * rs / mean(rs over
    window)``; ``rs_momentum = 100 * rs_ratio / rs_ratio(momentum_lag
    sessions ago)``. Scores above 100 mean stronger than usual.

    Args:
        closes: Sector closes, dates by sectors.
        benchmark: Benchmark closes (VNINDEX) indexed by date.
        window: Sessions in the RS-ratio average.
        momentum_lag: Sessions used for RS-momentum.

    Returns:
        Long frame ``date``, ``sector``, ``rs_ratio``, ``rs_momentum``,
        ``quadrant``, ``score`` and ``rank`` (1 = strongest).
    """
    aligned = closes.reindex(benchmark.index)
    rs = aligned.div(benchmark, axis=0)
    ratio = 100.0 * rs / rs.rolling(window, min_periods=window).mean()
    momentum = 100.0 * ratio / ratio.shift(momentum_lag)
    long = _melt(ratio, "rs_ratio").merge(
        _melt(momentum, "rs_momentum"), on=["date", "sector"])
    long = long.dropna(subset=["rs_ratio", "rs_momentum"])
    strong = long["rs_ratio"] >= 100.0
    rising = long["rs_momentum"] >= 100.0
    long["quadrant"] = np.select(
        [strong & rising, strong & ~rising, ~strong & ~rising],
        ["leading", "weakening", "lagging"],
        "improving",
    )
    long["score"] = (long["rs_ratio"] - 100.0) + (long["rs_momentum"] - 100.0)
    long["rank"] = long.groupby("date")["score"].rank(
        ascending=False, method="min").astype(int)
    return long.sort_values(["date", "rank"]).reset_index(drop=True)


def _melt(frame: pd.DataFrame, name: str) -> pd.DataFrame:
    """Turn a dates-by-sectors frame into long format.

    Args:
        frame: Values, dates by sectors.
        name: Name of the value column.

    Returns:
        Columns ``date``, ``sector`` and ``name``.
    """
    long = frame.rename_axis("date").reset_index().melt(
        id_vars="date", var_name="sector", value_name=name)
    return long
