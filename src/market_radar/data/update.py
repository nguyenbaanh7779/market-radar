"""Incremental download of daily bars into the store."""

from __future__ import annotations

import datetime as dt
import logging
from collections.abc import Iterable

import pandas as pd

from market_radar.data.sources import BarSource, SourceError
from market_radar.data.store import BarStore

logger = logging.getLogger(__name__)


def update_bars(
    store: BarStore,
    source: BarSource,
    symbols: Iterable[str],
    start: dt.date,
    end: dt.date,
    overlap_days: int,
) -> pd.DataFrame:
    """Fetch new bars for each symbol and merge them into the store.

    A symbol with stored bars is re-fetched from ``overlap_days`` before
    its last date, so late corrections by the source are picked up.

    Args:
        store: Destination store.
        source: Where bars come from.
        symbols: Symbols to update.
        start: First date for symbols without stored bars.
        end: Last date to request.
        overlap_days: Calendar days re-fetched before the last stored date.

    Returns:
        One row per symbol: status (``ok``, ``empty`` or ``error``), rows
        added, total rows, first and last date, and the error message.
    """
    fetched_at = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    rows = []
    for symbol in symbols:
        rows.append(
            _update_one(store, source, symbol, start, end, overlap_days,
                        fetched_at)
        )
    report = pd.DataFrame(rows)
    counts = report["status"].value_counts().to_dict()
    logger.info("Updated %d symbols from %s: %s", len(report), source.name,
                counts)
    return report


def _update_one(
    store: BarStore,
    source: BarSource,
    symbol: str,
    start: dt.date,
    end: dt.date,
    overlap_days: int,
    fetched_at: str,
) -> dict[str, object]:
    """Update a single symbol.

    Args:
        store: Destination store.
        source: Where bars come from.
        symbol: Symbol to update.
        start: First date when nothing is stored yet.
        end: Last date to request.
        overlap_days: Calendar days re-fetched before the last stored date.
        fetched_at: Download timestamp written with the bars.

    Returns:
        The report row for this symbol.
    """
    before = store.read(symbol)
    last = None if before.empty else before["date"].max()
    begin = start
    if last is not None:
        begin = max(start, (last - pd.Timedelta(days=overlap_days)).date())
    row: dict[str, object] = {"symbol": symbol, "status": "ok",
                              "new_rows": 0, "message": ""}
    try:
        bars = source.fetch(symbol, begin, end)
    except SourceError as error:
        logger.warning("%s: %s", symbol, error)
        row.update(status="error", message=str(error))
        return _with_range(row, before)
    if bars.empty:
        row["status"] = "empty" if before.empty else "ok"
        return _with_range(row, before)
    merged = store.upsert(symbol, bars, fetched_at)
    row["new_rows"] = len(merged) - len(before)
    return _with_range(row, merged)


def _with_range(row: dict[str, object], bars: pd.DataFrame) -> dict:
    """Add the row count and date range of stored bars to a report row.

    Args:
        row: Report row being built.
        bars: Bars stored for the symbol.

    Returns:
        The completed row.
    """
    row["total_rows"] = len(bars)
    row["first_date"] = None if bars.empty else bars["date"].min().date()
    row["last_date"] = None if bars.empty else bars["date"].max().date()
    return row
