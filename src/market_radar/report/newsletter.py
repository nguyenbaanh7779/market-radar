"""Build and render the daily newsletter."""

from __future__ import annotations

import functools
import math
from typing import Any

import jinja2
import pandas as pd

LANGUAGES = ("vi", "en")

# Terms produced by the signal, forecast and trading code, per language.
TERMS = {
    "vi": {
        "UP": "TĂNG", "DOWN": "GIẢM", "SIDEWAY": "ĐI NGANG",
        "uptrend": "xu hướng tăng", "downtrend": "xu hướng giảm",
        "sideways": "đi ngang",
        "leading": "dẫn dắt", "weakening": "suy yếu",
        "lagging": "tụt hậu", "improving": "cải thiện",
        "strong": "mạnh", "neutral": "trung tính", "caution": "cảnh giác",
        "buy": "mua", "sell": "bán", "entry": "mở vị thế",
        "add": "mua thêm", "exit": "đóng vị thế", "stop_loss": "cắt lỗ",
        "banking": "Ngân hàng", "real_estate": "Bất động sản",
        "securities": "Chứng khoán", "materials": "Vật liệu",
        "consumer": "Tiêu dùng – bán lẻ", "technology": "Công nghệ",
        "energy": "Năng lượng – dầu khí",
        "industrials": "Công nghiệp – xây dựng", "other": "Khác",
    },
    "en": {"stop_loss": "stop-loss", "real_estate": "real estate"},
}

# Fixed phrases inside reason texts, translated in this order.
PHRASES = {
    "vi": (
        ("uptrend (close > MA20 > MA50)", "xu hướng tăng (giá > MA20 > MA50)"),
        ("MACD histogram > 0", "MACD histogram dương"),
        ("overbought", "quá mua"),
        ("below MA50 with negative MACD", "dưới MA50, MACD âm"),
        ("below lower Bollinger band", "dưới dải Bollinger dưới"),
        ("x 20-day average", " lần trung bình 20 phiên"),
        ("volume ", "khối lượng "),
        ("weak technical signal", "tín hiệu kỹ thuật yếu"),
        ("sector is lagging", "ngành đang tụt hậu"),
        ("sector is weakening", "ngành đang suy yếu"),
    ),
    "en": (),
}


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
                 model: str) -> list[dict[str, Any]]:
    """Collect the 1- and 5-session outlook of key instruments.

    Args:
        forecasts: Today's forecasts of every model and horizon.
        symbols: Instruments to show, e.g. VNINDEX, VN30, BANKS.
        model: Model whose forecasts are shown.

    Returns:
        One row per symbol; ``h1`` and ``h5`` hold ``label``, ``p_up``,
        ``p_sideway`` and ``p_down``, or None without a forecast.
    """
    chosen = forecasts[forecasts["model"] == model]
    rows = []
    for symbol in symbols:
        row: dict[str, Any] = {"symbol": symbol}
        for horizon in (1, 5):
            match = chosen[(chosen["symbol"] == symbol)
                           & (chosen["horizon"] == horizon)]
            row[f"h{horizon}"] = None if match.empty else {
                "label": match.iloc[0]["label_pred"],
                "p_up": float(match.iloc[0]["p_up"]),
                "p_sideway": float(match.iloc[0]["p_sideway"]),
                "p_down": float(match.iloc[0]["p_down"]),
            }
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


def render(
    context: dict[str, Any],
    include_portfolio: bool = True,
    language: str = "vi",
) -> str:
    """Render the newsletter text.

    Args:
        context: Values for the template (see ``pipeline.daily``).
        include_portfolio: Whether to show the personal portfolio
            section; the copy saved to git leaves it out.
        language: ``vi`` or ``en``.

    Returns:
        The newsletter as plain text.

    Raises:
        ValueError: For an unsupported language.
    """
    if language not in LANGUAGES:
        raise ValueError(f"Unsupported newsletter language: {language!r}")
    environment = jinja2.Environment(
        loader=jinja2.PackageLoader("market_radar.report", "templates"),
        undefined=jinja2.StrictUndefined,
        keep_trailing_newline=True,
    )
    environment.filters.update({
        "num": functools.partial(format_number, language=language),
        "pct": functools.partial(format_percent, language=language),
        "day": functools.partial(format_day, language=language),
        "t": functools.partial(translate_term, language=language),
        "tr": functools.partial(translate_text, language=language),
    })
    values = dict(context)
    if not include_portfolio:
        values["portfolio"] = None
    template = environment.get_template(f"daily.{language}.md.j2")
    return template.render(**values)


def format_number(value: float, decimals: int = 0,
                  language: str = "en") -> str:
    """Format a number with thousands separators.

    Args:
        value: Number to format.
        decimals: Digits after the decimal mark.
        language: ``vi`` uses ``.`` for thousands and ``,`` for decimals.

    Returns:
        The formatted number.
    """
    text = f"{value:,.{decimals}f}"
    if language == "vi":
        text = text.replace(",", "_").replace(".", ",").replace("_", ".")
    return text


def format_percent(value: float, decimals: int = 2,
                   language: str = "en") -> str:
    """Format a signed percentage, e.g. ``+1.25%``.

    Args:
        value: Percentage points.
        decimals: Digits after the decimal mark.
        language: Number style (see :func:`format_number`).

    Returns:
        The formatted percentage.
    """
    sign = "+" if value >= 0 else "-"
    return sign + format_number(abs(value), decimals, language) + "%"


def format_day(iso_day: str, language: str = "en") -> str:
    """Format an ISO date for the reader.

    Args:
        iso_day: ``YYYY-MM-DD``.
        language: ``vi`` gives ``DD/MM/YYYY``.

    Returns:
        The formatted date.
    """
    if language != "vi":
        return iso_day
    year, month, day = iso_day.split("-")
    return f"{day}/{month}/{year}"


def translate_term(term: str, language: str = "en") -> str:
    """Translate a term such as a regime, quadrant, flag or sector.

    Args:
        term: Term as produced by the code.
        language: Target language.

    Returns:
        The translation, or the term itself when none is defined.
    """
    return TERMS[language].get(term, term)


def translate_text(text: str, language: str = "en") -> str:
    """Translate the fixed phrases inside a reason or warning text.

    Args:
        text: Text built by the signal code.
        language: Target language.

    Returns:
        The text with known phrases replaced.
    """
    for english, translated in PHRASES[language]:
        text = text.replace(english, translated)
    return text


def _none_if_nan(value: Any) -> float | None:
    """Convert NaN to None for the template.

    Args:
        value: A number or NaN.

    Returns:
        The float, or None.
    """
    value = float(value)
    return None if math.isnan(value) else value
