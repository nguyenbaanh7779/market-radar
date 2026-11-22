"""Turn stored bars into everything the modules need, in one pass."""

from __future__ import annotations

import dataclasses
import logging

import pandas as pd

from market_radar.calendar import TradingCalendar
from market_radar.config import Settings
from market_radar.data.quality import suspect_bars
from market_radar.forecaster.features import build_features, feature_columns
from market_radar.forecaster.labels import add_labels
from market_radar.signals.market import market_state
from market_radar.signals.sectors import (
    basket_bars,
    relative_rotation,
    sector_closes,
)

logger = logging.getLogger(__name__)
INDEX_SYMBOL = "VNINDEX"


@dataclasses.dataclass
class MarketData:
    """Bars, signals and the modelling panel derived from them.

    Attributes:
        bars: Long bars of stocks, indices and baskets.
        closes: Closes, dates by symbols.
        calendar: Trading calendar (realised sessions from VNINDEX).
        market: Market state by date.
        rotation: Sector rotation in long format.
        suspect: Bars that void the labels spanning them (moves beyond
            the price limit, copied bars).
        panel: Features and labels per symbol and date.
        feature_cols: Usable feature columns.
        has_volume: Whether the source provides volume.
    """

    bars: pd.DataFrame
    closes: pd.DataFrame
    calendar: TradingCalendar
    market: pd.DataFrame
    rotation: pd.DataFrame
    suspect: pd.DataFrame
    panel: pd.DataFrame
    feature_cols: list[str]
    has_volume: bool

    @property
    def asof(self) -> pd.Timestamp:
        """Return the latest session with index bars."""
        return self.calendar.last


def assemble(raw_bars: pd.DataFrame, settings: Settings) -> MarketData:
    """Build baskets, signals, features and labels from stored bars.

    Args:
        raw_bars: Long bars as loaded from the store.
        settings: Run settings.

    Returns:
        The assembled market data.

    Raises:
        ValueError: If VNINDEX bars are missing.
    """
    universe = settings.universe
    stocks = raw_bars[raw_bars["symbol"].isin(universe.stocks)]
    index_bars = raw_bars[raw_bars["symbol"] == INDEX_SYMBOL]
    if index_bars.empty:
        raise ValueError("VNINDEX bars are required; run `update` first")
    calendar = TradingCalendar(index_bars["date"], settings.holidays)
    coverage = stocks["volume"].notna().mean() if not stocks.empty else 0.0
    has_volume = coverage >= settings.features.min_volume_coverage
    bars = pd.concat(
        [raw_bars, *_baskets(stocks, settings)], ignore_index=True
    ).sort_values(["symbol", "date"]).reset_index(drop=True)
    closes = bars.pivot(index="date", columns="symbol", values="close")
    stock_closes = closes[[s for s in universe.stocks if s in closes]]
    traded_value = None
    if has_volume:
        volume = stocks.pivot(index="date", columns="symbol",
                              values="volume")
        traded_value = stock_closes * volume * settings.trading.price_unit_vnd
    market = market_state(closes[INDEX_SYMBOL], stock_closes,
                          settings.signals, traded_value)
    rotation = relative_rotation(
        sector_closes(stocks, universe.sectors), closes[INDEX_SYMBOL],
        settings.signals.rrg_window, settings.signals.rrg_momentum_lag)
    suspect = suspect_bars(bars, universe)
    panel = build_features(bars, market, rotation, universe, has_volume)
    panel = add_labels(panel, settings.labels.horizons,
                       settings.labels.sideway_band_pct, suspect)
    logger.info("Assembled %d rows for %d symbols up to %s (volume: %s)",
                len(panel), panel["symbol"].nunique(),
                calendar.last.date(), has_volume)
    return MarketData(
        bars=bars, closes=closes, calendar=calendar, market=market,
        rotation=rotation, suspect=suspect, panel=panel,
        feature_cols=feature_columns(panel), has_volume=bool(has_volume),
    )


def _baskets(stocks: pd.DataFrame, settings: Settings) -> list[pd.DataFrame]:
    """Build the bars of every synthetic basket.

    Args:
        stocks: Long bars of the universe's stocks.
        settings: Run settings.

    Returns:
        One long frame per basket, with ``symbol`` and ``source`` set.
    """
    frames = []
    for symbol, sector in settings.universe.baskets.items():
        members = settings.universe.sectors[sector]
        basket = basket_bars(stocks, members)
        if basket.empty:
            continue
        basket = basket.drop(columns="n_members")
        basket.insert(0, "symbol", symbol)
        basket["source"] = "basket"
        frames.append(basket)
    return frames
