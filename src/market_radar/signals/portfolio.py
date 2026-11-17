"""Status of the user's own holdings (never committed to git)."""

from __future__ import annotations

import dataclasses
import datetime as dt
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from market_radar.calendar import to_day

WEAK_QUADRANTS = ("lagging", "weakening")


@dataclasses.dataclass(frozen=True)
class Holding:
    """One position the user holds.

    Attributes:
        symbol: Stock symbol.
        quantity: Number of shares.
        avg_price: Average cost in thousand VND per share.
    """

    symbol: str
    quantity: int
    avg_price: float


def load_holdings(path: Path) -> tuple[list[Holding], dt.date | None]:
    """Read holdings from a YAML file shaped like portfolio.example.yaml.

    Args:
        path: Portfolio file.

    Returns:
        The holdings and the optional ``since`` date; no holdings when the
        file does not exist.
    """
    if not path.is_file():
        return [], None
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    holdings = [
        Holding(str(item["symbol"]).upper(), int(item["quantity"]),
                float(item["avg_price"]))
        for item in raw.get("holdings") or []
    ]
    since = raw.get("since")
    return holdings, (to_day(since).date() if since else None)


def portfolio_status(
    holdings: list[Holding],
    closes: pd.DataFrame,
    asof: pd.Timestamp,
    sector_of: Callable[[str], str | None],
    sector_quadrant: dict[str, str],
    flags: pd.DataFrame,
    benchmark: str,
    since: dt.date | None,
    price_unit_vnd: float,
) -> dict[str, Any] | None:
    """Summarise holdings: value, P&L, allocation and warnings.

    Args:
        holdings: User positions.
        closes: Closes, dates by symbols (must include the benchmark).
        asof: Session to value the portfolio on.
        sector_of: Maps a symbol to its sector.
        sector_quadrant: Latest rotation quadrant per sector.
        flags: Ticker flags by symbol (column ``flag``).
        benchmark: Benchmark symbol, e.g. ``VN30``.
        since: Start date for the benchmark comparison.
        price_unit_vnd: VND per price unit (1000 for thousand VND).

    Returns:
        Positions, totals, sector weights, concentration (HHI), the
        benchmark return since ``since`` and warnings; None if there are
        no holdings.
    """
    if not holdings:
        return None
    last = closes.loc[:asof].ffill().iloc[-1]
    positions = []
    for holding in holdings:
        close = float(last.get(holding.symbol, float("nan")))
        sector = sector_of(holding.symbol) or "other"
        flag = flags["flag"].get(holding.symbol, "n/a")
        positions.append({
            "symbol": holding.symbol,
            "quantity": holding.quantity,
            "avg_price": holding.avg_price,
            "close": close,
            "value_vnd": holding.quantity * close * price_unit_vnd,
            "cost_vnd": holding.quantity * holding.avg_price * price_unit_vnd,
            "sector": sector,
            "flag": flag,
            "warnings": _warnings(flag, sector_quadrant.get(sector)),
        })
    table = pd.DataFrame(positions)
    table["pnl_vnd"] = table["value_vnd"] - table["cost_vnd"]
    table["pnl_pct"] = 100.0 * table["pnl_vnd"] / table["cost_vnd"]
    total_value = float(table["value_vnd"].sum())
    total_cost = float(table["cost_vnd"].sum())
    table["weight"] = table["value_vnd"] / total_value
    sectors = table.groupby("sector")["weight"].sum().sort_values(
        ascending=False)
    return {
        "positions": table.sort_values("weight", ascending=False).to_dict(
            "records"),
        "value_vnd": total_value,
        "pnl_vnd": total_value - total_cost,
        "pnl_pct": 100.0 * (total_value / total_cost - 1.0),
        "sector_weights": sectors.round(4).to_dict(),
        "hhi": float((table["weight"] ** 2).sum()),
        "top_contributor": table.loc[table["pnl_vnd"].idxmax(), "symbol"],
        "benchmark": benchmark,
        "benchmark_return_pct": _return_since(
            closes.get(benchmark), since, asof),
        "warnings": [
            f"{row['symbol']}: {', '.join(row['warnings'])}"
            for row in positions if row["warnings"]
        ],
    }


def _warnings(flag: str, quadrant: str | None) -> list[str]:
    """List the reasons a holding needs attention.

    Args:
        flag: Technical flag of the stock.
        quadrant: Rotation quadrant of its sector.

    Returns:
        Warning texts (empty when nothing stands out).
    """
    found = []
    if flag == "caution":
        found.append("weak technical signal")
    if quadrant in WEAK_QUADRANTS:
        found.append(f"sector is {quadrant}")
    return found


def _return_since(
    series: pd.Series | None, since: dt.date | None, asof: pd.Timestamp
) -> float | None:
    """Percent change of a series from a start date to ``asof``.

    Args:
        series: Closes indexed by date.
        since: Start date (the first session on or after it is used).
        asof: End session.

    Returns:
        The return in percent, or None without data.
    """
    if series is None or since is None:
        return None
    window = series.loc[to_day(since):asof].dropna()
    if len(window) < 2:
        return None
    return float(100.0 * (window.iloc[-1] / window.iloc[0] - 1.0))
