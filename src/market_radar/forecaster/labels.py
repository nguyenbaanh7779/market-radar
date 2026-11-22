"""Direction labels: UP, DOWN or SIDEWAY after ``h`` sessions.

The return from the close of session ``t`` to the close of session
``t + h`` is labelled UP above ``+band``, DOWN below ``-band`` and SIDEWAY
otherwise. With ``h = 1`` and a 0.2% band this is the rule Arena uses to
score direction predictions.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

CLASSES = ("DOWN", "SIDEWAY", "UP")
PROBA_COLUMNS = ("p_down", "p_sideway", "p_up")


def classify_return(ret_pct: pd.Series, band_pct: float) -> pd.Series:
    """Map returns in percent to direction labels.

    Args:
        ret_pct: Returns in percent.
        band_pct: Half-width of the sideways band in percent.

    Returns:
        ``UP``, ``DOWN`` or ``SIDEWAY``; missing where the return is.
    """
    labels = np.select(
        [ret_pct > band_pct, ret_pct < -band_pct, ret_pct.notna()],
        ["UP", "DOWN", "SIDEWAY"],
        default="",
    )
    out = pd.Series(labels, index=ret_pct.index, dtype="object")
    return out.where(out != "", None)


def add_labels(
    panel: pd.DataFrame,
    horizons: tuple[int, ...],
    band_pct: float,
    suspect: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Add forward returns and direction labels for each horizon.

    Labels whose window ``(t, t + h]`` contains a suspect bar (a jump
    beyond the price limit, usually an unadjusted corporate action, or a
    bar copied from the previous session) are set to missing so they are
    neither trained on nor scored.

    Args:
        panel: Rows ``symbol``, ``date``, ``close`` sorted by symbol, date.
        horizons: Horizons in sessions, e.g. ``(1, 5)``.
        band_pct: Sideways band in percent.
        suspect: Rows ``symbol`` and ``date`` of suspect bars, or None.

    Returns:
        A copy of ``panel`` with ``fwd_ret_<h>`` (percent) and
        ``label_<h>`` columns.
    """
    out = panel.copy()
    grouped = out.groupby("symbol", sort=False)["close"]
    flag = _suspect_flag(out, suspect)
    for horizon in horizons:
        future = grouped.shift(-horizon)
        ret_pct = (future / out["close"] - 1.0) * 100.0
        tainted = flag.groupby(out["symbol"], sort=False).transform(
            lambda values, h=horizon: _any_in_next(values, h))
        ret_pct = ret_pct.mask(tainted > 0)
        out[f"fwd_ret_{horizon}"] = ret_pct
        out[f"label_{horizon}"] = classify_return(ret_pct, band_pct)
    return out


def _suspect_flag(
    panel: pd.DataFrame, suspect: pd.DataFrame | None
) -> pd.Series:
    """Mark rows of the panel that are suspect moves.

    Args:
        panel: Rows with ``symbol`` and ``date``.
        suspect: Suspect ``symbol``/``date`` pairs, or None.

    Returns:
        1.0 on suspect rows, 0.0 elsewhere, aligned with ``panel``.
    """
    if suspect is None or suspect.empty:
        return pd.Series(0.0, index=panel.index)
    keys = pd.MultiIndex.from_frame(suspect[["symbol", "date"]])
    rows = pd.MultiIndex.from_frame(panel[["symbol", "date"]])
    return pd.Series(rows.isin(keys).astype(float), index=panel.index)


def _any_in_next(values: pd.Series, horizon: int) -> pd.Series:
    """For each row, the maximum of the next ``horizon`` values.

    Args:
        values: Flags of one symbol in date order.
        horizon: Number of following rows to look at.

    Returns:
        ``max(values[i + 1 : i + 1 + horizon])`` for every row ``i``.
    """
    reversed_max = values[::-1].rolling(horizon, min_periods=1).max()
    return reversed_max[::-1].shift(-1).fillna(0.0)
