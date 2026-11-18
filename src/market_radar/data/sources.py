"""Daily OHLCV sources: the Arena public API and vnstock v6 (optional)."""

from __future__ import annotations

import datetime as dt
import time
from collections.abc import Callable, Iterable
from typing import Any, Protocol

import pandas as pd
import requests

from market_radar import __version__
from market_radar.config import ArenaSettings, Settings, VnstockSettings

BAR_COLUMNS = ["date", "open", "high", "low", "close", "volume"]
USER_AGENT = f"market-radar/{__version__} (research prototype)"


class SourceError(RuntimeError):
    """Raised when a source cannot deliver bars for a symbol."""


class BarSource(Protocol):
    """Anything that returns daily bars for one symbol."""

    name: str

    def fetch(
        self, symbol: str, start: dt.date, end: dt.date
    ) -> pd.DataFrame:
        """Return daily bars with :data:`BAR_COLUMNS` plus ``source``."""
        ...


def empty_bars() -> pd.DataFrame:
    """Return an empty frame with the canonical bar columns.

    Returns:
        A frame with :data:`BAR_COLUMNS` and ``source``, no rows.
    """
    frame = pd.DataFrame({column: [] for column in BAR_COLUMNS})
    frame["date"] = pd.to_datetime(frame["date"])
    frame["source"] = pd.Series([], dtype="str")
    return frame


def normalize_bars(frame: pd.DataFrame, source: str) -> pd.DataFrame:
    """Coerce raw bars to the canonical layout.

    Dates become midnight timestamps, prices and volume floats; rows are
    sorted by date and duplicate dates keep their last occurrence.

    Args:
        frame: Raw bars with at least ``date`` and ``close``.
        source: Name of the source, stored in a ``source`` column.

    Returns:
        Bars with :data:`BAR_COLUMNS` and ``source``.
    """
    if frame.empty:
        return empty_bars()
    out = pd.DataFrame(index=frame.index)
    dates = pd.to_datetime(frame["date"])
    if dates.dt.tz is not None:
        dates = dates.dt.tz_localize(None)
    out["date"] = dates.dt.normalize()
    for column in BAR_COLUMNS[1:]:
        if column in frame:
            values = pd.to_numeric(frame[column], errors="coerce")
            out[column] = values.astype(float)
        else:
            out[column] = float("nan")
    out["source"] = source
    out = out.dropna(subset=["close"])
    out = out.drop_duplicates(subset="date", keep="last")
    return out.sort_values("date").reset_index(drop=True)


class ArenaSource:
    """Daily bars from the Arena (ckai.vn) public ``eod/market-bars`` API.

    The API needs no key and returns OHLC in thousand VND for stocks and
    points for indices; volume is not provided.

    Args:
        settings: API location, timeout, pause and retry count.
        session: HTTP session (injected in tests).
        sleep: Sleep function (injected in tests).
    """

    name = "arena"

    def __init__(
        self,
        settings: ArenaSettings,
        session: requests.Session | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._settings = settings
        self._session = session or requests.Session()
        self._session.headers.setdefault("User-Agent", USER_AGENT)
        self._sleep = sleep

    def fetch(
        self, symbol: str, start: dt.date, end: dt.date
    ) -> pd.DataFrame:
        """Download daily bars for one symbol.

        Args:
            symbol: Ticker or index symbol, e.g. ``VCB`` or ``VNINDEX``.
            start: First date (inclusive).
            end: Last date (inclusive).

        Returns:
            Canonical bars; empty when Arena has none in the range.

        Raises:
            SourceError: If the request keeps failing or Arena reports an
                error.
        """
        params = {
            "symbol": symbol,
            "from": start.isoformat(),
            "to": end.isoformat(),
            "interval": "1d",
        }
        payload = self._get_json("/eod/market-bars", params)
        if not payload.get("success"):
            raise SourceError(f"Arena error for {symbol}: {payload}")
        items = (payload.get("data") or {}).get("items") or []
        self._sleep(self._settings.pause_s)
        if not items:
            return empty_bars()
        frame = pd.DataFrame(items).rename(columns={"session_date": "date"})
        return normalize_bars(frame, self.name)

    def _get_json(self, path: str, params: dict[str, str]) -> dict[str, Any]:
        """GET a JSON document, retrying transient failures.

        Args:
            path: Endpoint path below the base URL.
            params: Query parameters.

        Returns:
            The decoded JSON body.

        Raises:
            SourceError: After the last failed attempt.
        """
        url = self._settings.base_url.rstrip("/") + path
        last_error: Exception | None = None
        for attempt in range(1, self._settings.retries + 1):
            try:
                response = self._session.get(
                    url, params=params, timeout=self._settings.timeout_s
                )
                response.raise_for_status()
                return response.json()
            except (requests.RequestException, ValueError) as error:
                last_error = error
                if attempt < self._settings.retries:
                    self._sleep(2.0 * attempt)
        raise SourceError(
            f"GET {url} {params} failed after {self._settings.retries} "
            f"attempts: {last_error}"
        )


class VnstockSource:
    """Daily bars from vnstock v6 (needs your own broker API key).

    vnstock v6 is installed from its own package index and reads the key
    registered with ``vnstock keys set <provider>``; see
    ``docs/guide/README.md``. Unlike Arena it provides volume.

    Args:
        settings: Provider (``ssi``, ``dnse``, ``tcbs`` or ``fhsc``) and the
            pause between calls.
        index_symbols: Symbols to request as indices rather than equities.
        market_factory: Callable returning a vnstock ``Market`` for a
            provider (injected in tests).
        sleep: Sleep function (injected in tests).
    """

    name = "vnstock"

    def __init__(
        self,
        settings: VnstockSettings,
        index_symbols: Iterable[str] = ("VNINDEX", "VN30"),
        market_factory: Callable[[str], Any] | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if market_factory is None:
            market_factory = _import_vnstock_market()
        self._market = market_factory(settings.provider)
        self._indices = frozenset(index_symbols)
        self._pause = settings.pause_s
        self._sleep = sleep

    def fetch(
        self, symbol: str, start: dt.date, end: dt.date
    ) -> pd.DataFrame:
        """Download daily bars for one symbol.

        Args:
            symbol: Ticker or index symbol.
            start: First date (inclusive).
            end: Last date (inclusive).

        Returns:
            Canonical bars.

        Raises:
            SourceError: If vnstock raises for this symbol.
        """
        group = self._market.index if symbol in self._indices else (
            self._market.equity
        )
        try:
            raw = group(symbol).ohlcv(
                start=start.isoformat(), end=end.isoformat(), interval="1D"
            )
        except Exception as error:  # vnstock raises many custom errors
            raise SourceError(f"vnstock failed for {symbol}: {error}") from (
                error
            )
        finally:
            self._sleep(self._pause)
        frame = pd.DataFrame(raw).rename(columns={"time": "date"})
        return normalize_bars(frame, self.name)


def _import_vnstock_market() -> Callable[[str], Any]:
    """Import vnstock's ``Market`` class lazily.

    Returns:
        The ``vnstock.Market`` class.

    Raises:
        SourceError: If vnstock v6 is not installed.
    """
    try:
        from vnstock import Market
    except ImportError as error:
        raise SourceError(
            "vnstock v6 is not installed; see docs/guide/README.md"
        ) from error
    return Market


def make_source(settings: Settings, name: str | None = None) -> BarSource:
    """Create the configured bar source.

    Args:
        settings: Run settings.
        name: Source name overriding ``settings.data.source``.

    Returns:
        A ready-to-use source.

    Raises:
        ValueError: For an unknown source name.
    """
    name = name or settings.data.source
    if name == "arena":
        return ArenaSource(settings.data.arena)
    if name == "vnstock":
        return VnstockSource(
            settings.data.vnstock, index_symbols=settings.universe.indices
        )
    raise ValueError(f"Unknown data source: {name!r}")
