"""Point-in-time features: each row uses data up to its own date only."""

from __future__ import annotations

import pandas as pd

from market_radar.config import Universe
from market_radar.signals import indicators as ind

FEATURE_GROUPS: dict[str, tuple[str, ...]] = {
    "returns": ("ret_1", "ret_2", "ret_3", "ret_5", "ret_10", "ret_20"),
    "trend": ("dist_ma20", "dist_ma50", "ma20_ma50"),
    "oscillators": ("rsi_14", "macd_hist_norm", "bb_pct_b"),
    "volatility": ("vol_20", "atr_14_norm", "range_1"),
    "volume": ("vol_ratio_20",),
    "relative": ("rel_ret_5", "rel_ret_20"),
    "market": ("idx_dist_ma20", "idx_dist_ma50", "idx_vol_20",
               "idx_vol_pctile", "breadth_up", "breadth_above_ma20",
               "liquidity_ratio"),
    "sector": ("sec_rs_ratio", "sec_rs_momentum"),
    "instrument": ("is_index",),
}
RETURN_LAGS = (1, 2, 3, 5, 10, 20)
MARKET_COLUMNS = FEATURE_GROUPS["market"] + ("idx_ret_5", "idx_ret_20")


def price_features(bars: pd.DataFrame) -> pd.DataFrame:
    """Price and volume features of one instrument.

    Args:
        bars: Bars of a single symbol sorted by date.

    Returns:
        Feature columns aligned with ``bars``.
    """
    close, high, low = bars["close"], bars["high"], bars["low"]
    out = pd.DataFrame(index=bars.index)
    for lag in RETURN_LAGS:
        out[f"ret_{lag}"] = close / close.shift(lag) - 1.0
    ma20, ma50 = ind.sma(close, 20), ind.sma(close, 50)
    out["dist_ma20"] = close / ma20 - 1.0
    out["dist_ma50"] = close / ma50 - 1.0
    out["ma20_ma50"] = ma20 / ma50 - 1.0
    out["rsi_14"] = ind.rsi(close, 14)
    out["macd_hist_norm"] = ind.macd(close)["hist"] / close
    out["bb_pct_b"] = ind.bollinger_pct_b(close)
    out["vol_20"] = ind.realized_vol(close, 20)
    out["atr_14_norm"] = ind.atr(high, low, close, 14) / close
    out["range_1"] = (high - low) / close
    out["vol_ratio_20"] = ind.volume_ratio(bars["volume"], 20)
    return out


def build_features(
    bars: pd.DataFrame,
    market: pd.DataFrame,
    rotation: pd.DataFrame,
    universe: Universe,
    include_volume: bool,
) -> pd.DataFrame:
    """Assemble the feature panel of every instrument.

    Args:
        bars: Long bars (stocks, indices and baskets) sorted by symbol
            and date.
        market: Market state by date (see ``signals.market``).
        rotation: Sector rotation in long format (see ``signals.sectors``).
        universe: Maps symbols to sectors and flags indices/baskets.
        include_volume: Whether volume features are usable.

    Returns:
        Rows ``date``, ``symbol``, ``close`` plus every feature column.
    """
    parts = [
        pd.concat([frame[["date", "symbol", "close"]],
                   price_features(frame)], axis=1)
        for _, frame in bars.groupby("symbol", sort=False)
    ]
    panel = pd.concat(parts, ignore_index=True)
    market_cols = [col for col in MARKET_COLUMNS if col in market.columns]
    panel = panel.merge(market[market_cols], left_on="date",
                        right_index=True, how="left")
    panel["rel_ret_5"] = panel["ret_5"] - panel.pop("idx_ret_5")
    panel["rel_ret_20"] = panel["ret_20"] - panel.pop("idx_ret_20")
    panel["sector"] = panel["symbol"].map(
        lambda symbol: universe.baskets.get(symbol)
        or universe.sector_of(symbol))
    sector_feats = rotation.rename(columns={
        "rs_ratio": "sec_rs_ratio", "rs_momentum": "sec_rs_momentum"})
    panel = panel.merge(
        sector_feats[["date", "sector", "sec_rs_ratio", "sec_rs_momentum"]],
        on=["date", "sector"], how="left")
    panel["is_index"] = panel["symbol"].map(universe.is_index_like).astype(
        float)
    if not include_volume:
        panel = panel.drop(columns=list(FEATURE_GROUPS["volume"]))
    return panel.sort_values(["symbol", "date"]).reset_index(drop=True)


def feature_columns(panel: pd.DataFrame) -> list[str]:
    """List the usable feature columns of a panel, in group order.

    Columns that are missing or entirely empty (e.g. liquidity without
    volume data) are left out.

    Args:
        panel: Feature panel.

    Returns:
        Feature column names.
    """
    return [
        column
        for group in FEATURE_GROUPS.values()
        for column in group
        if column in panel.columns and panel[column].notna().any()
    ]
