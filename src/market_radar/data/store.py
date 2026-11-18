"""Parquet store of daily bars, one file per symbol."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import duckdb
import pandas as pd

from market_radar.data.sources import BAR_COLUMNS, empty_bars

STORE_COLUMNS = ["symbol", *BAR_COLUMNS, "source", "fetched_at"]


class BarStore:
    """Daily bars stored as ``<root>/<SYMBOL>.parquet``.

    Args:
        root: Folder holding the Parquet files (created on first write).
    """

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def path(self, symbol: str) -> Path:
        """Return the file of a symbol.

        Args:
            symbol: Instrument symbol.

        Returns:
            Path of its Parquet file.
        """
        return self.root / f"{symbol}.parquet"

    def symbols(self) -> list[str]:
        """List the symbols that have a file.

        Returns:
            Sorted symbols.
        """
        if not self.root.is_dir():
            return []
        return sorted(path.stem for path in self.root.glob("*.parquet"))

    def read(self, symbol: str) -> pd.DataFrame:
        """Read the bars of one symbol.

        Args:
            symbol: Instrument symbol.

        Returns:
            Stored bars sorted by date (empty frame if none).
        """
        path = self.path(symbol)
        if not path.is_file():
            frame = empty_bars()
            frame.insert(0, "symbol", pd.Series([], dtype="str"))
            frame["fetched_at"] = pd.Series([], dtype="str")
            return frame
        return pd.read_parquet(path).sort_values("date").reset_index(
            drop=True
        )

    def last_date(self, symbol: str) -> pd.Timestamp | None:
        """Return the latest stored date of a symbol.

        Args:
            symbol: Instrument symbol.

        Returns:
            The last date, or None if nothing is stored.
        """
        frame = self.read(symbol)
        return None if frame.empty else frame["date"].max()

    def upsert(
        self, symbol: str, bars: pd.DataFrame, fetched_at: str
    ) -> pd.DataFrame:
        """Merge new bars into a symbol's file; new rows win on equal dates.

        Args:
            symbol: Instrument symbol.
            bars: Canonical bars from a source.
            fetched_at: UTC timestamp of the download (ISO text).

        Returns:
            The merged bars that were written.
        """
        new = bars.copy()
        new.insert(0, "symbol", symbol)
        new["fetched_at"] = fetched_at
        old = self.read(symbol)
        frames = [frame for frame in (old, new) if not frame.empty]
        if not frames:
            return old
        merged = pd.concat(frames, ignore_index=True)
        merged = merged.drop_duplicates(subset="date", keep="last")
        merged = merged.sort_values("date").reset_index(drop=True)
        merged = merged[STORE_COLUMNS]
        self.root.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path(symbol).with_suffix(".parquet.tmp")
        merged.to_parquet(tmp_path, index=False)
        tmp_path.replace(self.path(symbol))
        return merged

    def load(self, symbols: Iterable[str] | None = None) -> pd.DataFrame:
        """Load the bars of many symbols in one long frame via DuckDB.

        Args:
            symbols: Symbols to load (default: every stored symbol).

        Returns:
            Long frame sorted by symbol and date.
        """
        wanted = list(symbols) if symbols is not None else self.symbols()
        files = [
            str(self.path(symbol))
            for symbol in wanted
            if self.path(symbol).is_file()
        ]
        if not files:
            return self.read("__none__")
        frame = duckdb.read_parquet(files, union_by_name=True).df()
        frame["date"] = pd.to_datetime(frame["date"])
        return frame.sort_values(["symbol", "date"]).reset_index(drop=True)
