"""Build and render the daily newsletter."""

from __future__ import annotations

import math
from typing import Any

import jinja2
import pandas as pd

TEMPLATE = "daily.md.j2"


def market_summary(market: pd.DataFrame, closes: pd.DataFrame,
                   asof: pd.Timestamp) -> dict[str, Any]:
    """Collect the market numbers of one session.

    Args:
        market: Market state by date.
        closes: Closes, dates by symbols (with VN30).
        asof: Session to describe.

    Returns:
        Index levels and changes, regime, volatility, breadth, liquidity.
    """
    row = market.loc[asof]
    vn30 = closes["VN30"].dropna().loc[:asof]
    return {
        "close": float(row["idx_close"]),
        "change_pct": 100.0 * float(row["idx_ret_1"]),
        "vn30_close": float(vn30.iloc[-1]),
        "vn30_change_pct": 100.0 * float(vn30.iloc[-1] / vn30.iloc[-2] - 1),
        "regime": row["regime"],
        "vol_pct": 100.0 * float(row["idx_vol_20"]),
        "vol_pctile": _none_if_nan(row["idx_vol_pctile"]),
        "breadth_up": float(row["breadth_up"]),
        "breadth_above_ma20": float(row["breadth_above_ma20"]),
        "liquidity_ratio": _none_if_nan(row["liquidity_ratio"]),
    }


def outlook_rows(forecasts: pd.DataFrame, symbols: list[str],
                 model: str) -> list[dict[str, str]]:
    """Format the 1- and 5-session outlook of key instruments.

    Args:
        forecasts: Today's forecasts of every model and horizon.
        symbols: Instruments to show, e.g. VNINDEX, VN30, BANKS.
        model: Model whose forecasts are shown.

    Returns:
        One row per symbol with ``h1`` and ``h5`` texts.
    """
    chosen = forecasts[forecasts["model"] == model]
    rows = []
    for symbol in symbols:
        row = {"symbol": symbol}
        for horizon in (1, 5):
            match = chosen[(chosen["symbol"] == symbol)
                           & (chosen["horizon"] == horizon)]
            row[f"h{horizon}"] = (_proba_text(match.iloc[0])
                                  if not match.empty else "n/a")
        rows.append(row)
    return rows


def ranked_stocks(forecasts: pd.DataFrame, flags: pd.DataFrame,
                  stocks: list[str], model: str, horizon: int,
                  top_n: int) -> tuple[list[dict], list[dict]]:
    """Pick the strongest and the weakest stocks of the day.

    Args:
        forecasts: Today's forecasts of every model and horizon.
        flags: Technical flags by symbol (``flag``, ``reasons``).
        stocks: Tradable stocks.
        model: Model used for ranking.
        horizon: Horizon used for ranking.
        top_n: Rows per list.

    Returns:
        Stocks with the highest P(UP) that are not flagged caution, and
        stocks with the highest P(DOWN) or a caution flag.
    """
    chosen = forecasts[(forecasts["model"] == model)
                       & (forecasts["horizon"] == horizon)
                       & forecasts["symbol"].isin(stocks)]
    table = chosen.merge(flags, left_on="symbol", right_index=True,
                         how="left").fillna({"flag": "n/a", "reasons": ""})
    strong = table[table["flag"] != "caution"].nlargest(top_n, "p_up")
    weak = table[(table["p_down"] > table["p_up"])
                 | (table["flag"] == "caution")].nlargest(top_n, "p_down")
    return _stock_rows(strong), _stock_rows(weak)


def _stock_rows(frame: pd.DataFrame) -> list[dict[str, Any]]:
    """Convert ranked stocks to template rows.

    Args:
        frame: Forecasts merged with flags.

    Returns:
        One dict per stock.
    """
    return [
        {"symbol": r.symbol, "p_up": r.p_up, "p_down": r.p_down,
         "flag": r.flag, "reasons": r.reasons, "drivers": r.explanation}
        for r in frame.itertuples()
    ]


def sector_rows(rotation: pd.DataFrame, asof: pd.Timestamp
                ) -> tuple[list[dict], list[dict]]:
    """Return the three strongest and two weakest sectors on a session.

    Args:
        rotation: Sector rotation in long format.
        asof: Session to describe.

    Returns:
        Top and bottom sector rows.
    """
    today = rotation[rotation["date"] == asof].sort_values("rank")
    records = today.to_dict("records")
    return records[:3], records[3:][-2:]


def render(context: dict[str, Any], include_portfolio: bool = True) -> str:
    """Render the newsletter text.

    Args:
        context: Values for the template (see ``pipeline.daily``).
        include_portfolio: Whether to show the personal portfolio
            section; the copy saved to git leaves it out.

    Returns:
        The newsletter as plain text.
    """
    environment = jinja2.Environment(
        loader=jinja2.PackageLoader("market_radar.report", "templates"),
        undefined=jinja2.StrictUndefined,
        keep_trailing_newline=True,
    )
    values = dict(context)
    if not include_portfolio:
        values["portfolio"] = None
    return environment.get_template(TEMPLATE).render(**values)


def _proba_text(row: pd.Series) -> str:
    """Format a forecast as ``UP 52/9/39``.

    Args:
        row: Forecast with ``label_pred`` and the probabilities.

    Returns:
        The label followed by P(up)/P(sideways)/P(down) in percent.
    """
    return (f"{row['label_pred']} {100 * row['p_up']:.0f}/"
            f"{100 * row['p_sideway']:.0f}/{100 * row['p_down']:.0f}")


def _none_if_nan(value: Any) -> float | None:
    """Convert NaN to None for the template.

    Args:
        value: A number or NaN.

    Returns:
        The float, or None.
    """
    value = float(value)
    return None if math.isnan(value) else value
