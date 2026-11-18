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
        "dist_ma20_pct": 100.0 * float(row["idx_dist_ma20"]),
        "dist_ma50_pct": 100.0 * float(row["idx_dist_ma50"]),
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
        ``p_sideway``, ``p_down`` and ``p_max`` (probability of the
        label), or None without a forecast.
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
                "p_max": float(match.iloc[0][
                    ["p_up", "p_sideway", "p_down"]].max()),
            }
        rows.append(row)
    return rows


def ranked_stocks(forecasts: pd.DataFrame, flags: pd.DataFrame,
                  stocks: list[str], model: str, horizon: int,
                  top_n: int, features: pd.DataFrame | None = None,
                  language: str = "vi") -> tuple[list[dict], list[dict]]:
    """Pick the strongest and the weakest stocks of the day.

    Args:
        forecasts: Today's forecasts of every model and horizon.
        flags: Technical flags by symbol (``flag``, ``reasons``).
        stocks: Tradable stocks.
        model: Model used for ranking.
        horizon: Horizon used for ranking.
        top_n: Rows per list.
        features: Feature rows of the session by symbol, used to explain
            each forecast with real values (optional).
        language: Language of the explanations.

    Returns:
        Stocks with the highest P(UP) that are not flagged caution, and
        stocks with the highest P(DOWN) or a caution flag; each row has
        ``why`` and ``confidence`` in plain words.
    """
    chosen = forecasts[(forecasts["model"] == model)
                       & (forecasts["horizon"] == horizon)
                       & forecasts["symbol"].isin(stocks)]
    table = chosen.merge(flags, left_on="symbol", right_index=True,
                         how="left").fillna({"flag": "n/a", "reasons": ""})
    strong = table[table["flag"] != "caution"].nlargest(top_n, "p_up")
    weak = table[(table["p_down"] > table["p_up"])
                 | (table["flag"] == "caution")].nlargest(top_n, "p_down")
    return (_stock_rows(strong, "UP", features, language),
            _stock_rows(weak, "DOWN", features, language))


def _stock_rows(frame: pd.DataFrame, direction: str,
                features: pd.DataFrame | None,
                language: str) -> list[dict[str, Any]]:
    """Convert ranked stocks to template rows.

    Args:
        frame: Forecasts merged with flags.
        direction: ``UP`` for the strong list, ``DOWN`` for the weak one.
        features: Feature rows by symbol, or None.
        language: Language of the explanations.

    Returns:
        One dict per stock.
    """
    rows = []
    for r in frame.itertuples():
        values = (features.loc[r.symbol]
                  if features is not None and r.symbol in features.index
                  else None)
        p = r.p_up if direction == "UP" else r.p_down
        rows.append({
            "symbol": r.symbol, "p_up": r.p_up, "p_down": r.p_down,
            "flag": r.flag, "reasons": r.reasons, "drivers": r.explanation,
            "confidence": confidence_words(p, direction, language),
            "why": plain_drivers(r.explanation, values, language,
                                 top=DRIVERS_SHOWN),
            "reversal": _reversal_note(r.explanation, values, direction,
                                       language),
        })
    return rows


DRIVERS_SHOWN = 2
TREND_FEATURES = ("ret_", "rel_ret_", "dist_ma", "ma20_ma50")


def _reversal_note(explanation: str, values: pd.Series | None,
                   direction: str, language: str) -> str:
    """Point out a forecast that bets on a reversal.

    The model's drivers push towards the forecast, so a fall that
    supports an UP forecast (or a rise that supports DOWN) means the
    model expects the move to turn around.

    Args:
        explanation: Model drivers.
        values: Feature values of the stock, or None.
        direction: Forecast direction (``UP`` or ``DOWN``).
        language: Output language.

    Returns:
        A short note, or an empty string when the drivers follow the
        trend.
    """
    if not explanation or values is None:
        return ""
    names = [item.strip().split(" ")[0]
             for item in str(explanation).split(",")][:DRIVERS_SHOWN]
    against = [
        name for name in names
        if name.startswith(TREND_FEATURES) and name in values.index
        and not pd.isna(values[name])
        and (values[name] < 0 if direction == "UP" else values[name] > 0)
    ]
    if not against:
        return ""
    if direction == "UP":
        return _pick(language, "mô hình kỳ vọng hồi phục sau đợt giảm",
                     "the model expects a rebound after the fall")
    return _pick(language, "mô hình kỳ vọng điều chỉnh sau đợt tăng",
                 "the model expects a pullback after the rise")


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
        "conf": functools.partial(_confidence_filter, language=language),
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


# --- Plain-language explanations: words first, the number in brackets. ---

DIRECTION_WORDS = {
    "vi": {"UP": "tăng", "DOWN": "giảm", "SIDEWAY": "đi ngang"},
    "en": {"UP": "up", "DOWN": "down", "SIDEWAY": "sideways"},
}


def _pick(language: str, vi: str, en: str) -> str:
    """Choose the text of a language.

    Args:
        language: ``vi`` or ``en``.
        vi: Vietnamese text.
        en: English text.

    Returns:
        The text in ``language``.
    """
    return vi if language == "vi" else en


def confidence_words(p: float, direction: str, language: str = "vi") -> str:
    """Describe how sure a forecast is.

    Args:
        p: Probability of the forecast direction.
        direction: ``UP``, ``DOWN`` or ``SIDEWAY``.
        language: Output language.

    Returns:
        "Roughly even" below 0.55, "leaning" below 0.65, "clearly" above.
    """
    word = DIRECTION_WORDS[language].get(direction, direction)
    if p < 0.55:
        return _pick(language, "gần như ngang nhau", "roughly even")
    if p < 0.65:
        return _pick(language, f"hơi nghiêng về {word}", f"leaning {word}")
    return _pick(language, f"nghiêng rõ về {word}", f"clearly {word}")


def _confidence_filter(p: float, direction: str,
                       language: str = "vi") -> str:
    """Template filter wrapping :func:`confidence_words`.

    Args:
        p: Probability of the forecast direction.
        direction: Forecast direction.
        language: Output language.

    Returns:
        The confidence words.
    """
    return confidence_words(p, direction, language)


def market_plain(market: dict[str, Any],
                 language: str = "vi") -> dict[str, str | None]:
    """Explain the market numbers in plain words.

    Args:
        market: Output of :func:`market_summary`.
        language: Output language.

    Returns:
        ``trend``, ``volatility``, ``breadth`` and ``liquidity`` (None
        without volume) sentences, each with its numbers in brackets.
    """
    num = functools.partial(format_number, language=language)
    pct = functools.partial(format_percent, language=language)
    d20, d50 = pct(market["dist_ma20_pct"], 1), pct(market["dist_ma50_pct"], 1)
    regime = market["regime"]
    if regime == "uptrend":
        trend = _pick(language,
                      f"TĂNG — giá trên mức trung bình 20 phiên ({d20}) "
                      f"và 50 phiên ({d50})",
                      f"UP — price above its 20-session ({d20}) and "
                      f"50-session ({d50}) averages")
    elif regime == "downtrend":
        trend = _pick(language,
                      f"GIẢM — giá dưới mức trung bình 20 phiên ({d20}) "
                      f"và 50 phiên ({d50})",
                      f"DOWN — price below its 20-session ({d20}) and "
                      f"50-session ({d50}) averages")
    else:
        trend = _pick(language,
                      f"ĐI NGANG — chưa rõ xu hướng (so với trung bình 20 "
                      f"phiên {d20}, 50 phiên {d50})",
                      f"SIDEWAYS — no clear trend (vs 20-session average "
                      f"{d20}, 50-session {d50})")
    pctile = market["vol_pctile"]
    vol = num(market["vol_pct"], 1)
    if pctile is None:
        level = _pick(language, "chưa đủ dữ liệu", "not enough history")
        detail = _pick(language, f"{vol}%/năm", f"{vol}% a year")
    else:
        level = _vol_level(pctile, language)
        detail = _pick(
            language,
            f"{vol}%/năm, cao hơn {num(pctile * 100)}% số phiên trong 1 năm "
            f"qua",
            f"{vol}% a year, above {num(pctile * 100)}% of the past year's "
            f"sessions")
    volatility = _pick(language, f"Dao động {level} ({detail})",
                       f"Volatility {level} ({detail})")
    up = market["breadth_up"]
    above = num(market["breadth_above_ma20"] * 100)
    strength = (_pick(language, "yếu", "weak") if up < 0.4 else
                _pick(language, "trung bình", "average") if up < 0.6 else
                _pick(language, "tốt", "good"))
    breadth = _pick(
        language,
        f"Độ lan toả {strength} ({num(up * 100)}% cổ phiếu tăng giá, {above}% "
        f"còn trên trung bình 20 phiên)",
        f"Breadth {strength} ({num(up * 100)}% of stocks up, {above}% above "
        f"their 20-session average)")
    liquidity = None
    if market["liquidity_ratio"] is not None:
        ratio = market["liquidity_ratio"]
        word = (_pick(language, "cao hơn", "above") if ratio >= 1 else
                _pick(language, "thấp hơn", "below"))
        liquidity = _pick(
            language,
            f"Thanh khoản {word} bình thường (gấp {num(ratio, 2)} lần trung "
            f"bình 20 phiên)",
            f"Liquidity {word} normal ({num(ratio, 2)}x the 20-session "
            f"average)")
    return {"trend": trend, "volatility": volatility, "breadth": breadth,
            "liquidity": liquidity}


def _vol_level(pctile: float, language: str) -> str:
    """Name a volatility level from its percentile.

    Args:
        pctile: Percentile of the current volatility (0 to 1).
        language: Output language.

    Returns:
        Low, normal, high or very high.
    """
    if pctile < 0.3:
        return _pick(language, "thấp", "low")
    if pctile < 0.7:
        return _pick(language, "bình thường", "normal")
    if pctile < 0.9:
        return _pick(language, "cao", "high")
    return _pick(language, "rất cao", "very high")


def sector_plain(row: dict[str, Any], language: str = "vi") -> str:
    """Explain a sector's rotation quadrant with its scores.

    Args:
        row: Rotation row with ``quadrant``, ``rs_ratio``, ``rs_momentum``.
        language: Output language.

    Returns:
        The sentence, scores in brackets.
    """
    words = {
        "leading": ("mạnh hơn thị trường và đang tăng tốc",
                    "stronger than the market and accelerating"),
        "weakening": ("vẫn mạnh hơn thị trường nhưng đang chậm lại",
                      "still stronger than the market but slowing"),
        "lagging": ("yếu hơn thị trường, chưa có dấu hiệu hồi phục",
                    "weaker than the market, no sign of recovery yet"),
        "improving": ("còn yếu hơn thị trường nhưng đang hồi phục",
                      "still weaker than the market but recovering"),
    }[row["quadrant"]]
    num = functools.partial(format_number, language=language)
    scores = _pick(
        language,
        f"sức mạnh {num(row['rs_ratio'], 1)}; động lượng "
        f"{num(row['rs_momentum'], 1)}",
        f"strength {num(row['rs_ratio'], 1)}; momentum "
        f"{num(row['rs_momentum'], 1)}")
    return f"{_pick(language, *words)} ({scores})"


def describe_feature(name: str, value: float,
                     language: str = "vi") -> str | None:
    """Turn a model feature and its value into a short sentence.

    Args:
        name: Feature name, e.g. ``ret_20``.
        value: Its value on the session.
        language: Output language.

    Returns:
        Words with the number in brackets, None for NaN values and for
        features that need no explanation (``is_index``).
    """
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    if name == "is_index":
        return None
    num = functools.partial(format_number, language=language)
    pct = functools.partial(format_percent, language=language)
    v = float(value)
    up = v > 0
    if name.startswith("ret_"):
        k = name.split("_")[1]
        return _pick(
            language,
            f"{'tăng' if up else 'giảm'} gần đây ({pct(100 * v, 1)} trong {k} "
            f"phiên)",
            f"{'rose' if up else 'fell'} recently ({pct(100 * v, 1)} over {k} "
            f"sessions)")
    if name.startswith("rel_ret_"):
        k = name.split("_")[2]
        return _pick(
            language,
            f"{'mạnh' if up else 'yếu'} hơn VNINDEX ({pct(100 * v, 1)} trong "
            f"{k} phiên)",
            f"{'stronger' if up else 'weaker'} than VNINDEX "
            f"({pct(100 * v, 1)} over {k} sessions)")
    if name in ("dist_ma20", "dist_ma50"):
        k = name[-2:]
        return _pick(
            language,
            f"giá {'trên' if up else 'dưới'} mức trung bình {k} phiên "
            f"({pct(100 * v, 1)})",
            f"price {'above' if up else 'below'} its {k}-session average "
            f"({pct(100 * v, 1)})")
    if name == "ma20_ma50":
        return _pick(
            language,
            f"xu hướng trung hạn đi {'lên' if up else 'xuống'} (MA20 "
            f"{'cao' if up else 'thấp'} hơn MA50 {num(abs(100 * v), 1)}%)",
            f"medium-term trend {'up' if up else 'down'} (MA20 "
            f"{'above' if up else 'below'} MA50 by {num(abs(100 * v), 1)}%)")
    if name == "rsi_14":
        if v >= 70:
            state = _pick(language, "quá mua", "overbought")
        elif v <= 30:
            state = _pick(language, "quá bán", "oversold")
        elif v >= 50:
            state = _pick(language, "lực mua nhỉnh hơn", "buyers ahead")
        else:
            state = _pick(language, "lực bán nhỉnh hơn", "sellers ahead")
        return f"{state} (RSI {num(v)})"
    if name == "macd_hist_norm":
        return _pick(
            language,
            f"đà {'tăng' if up else 'giảm'} ngắn hạn (MACD histogram "
            f"{pct(100 * v, 2)} giá)",
            f"short-term momentum {'up' if up else 'down'} (MACD histogram "
            f"{pct(100 * v, 2)} of price)")
    if name == "bb_pct_b":
        where = (_pick(language, "vượt dải Bollinger trên", "above the upper "
                       "Bollinger band") if v > 1 else
                 _pick(language, "dưới dải Bollinger dưới", "below the lower "
                       "Bollinger band") if v < 0 else
                 _pick(language, "ở nửa trên dải Bollinger", "in the upper "
                       "half of the Bollinger band") if v >= 0.5 else
                 _pick(language, "ở nửa dưới dải Bollinger", "in the lower "
                       "half of the Bollinger band"))
        return _pick(language, f"giá {where} (vị trí {num(100 * v)}%)",
                     f"price {where} (position {num(100 * v)}%)")
    if name == "vol_20":
        x = num(100 * v, 1)
        return _pick(language, f"mức dao động của mã ({x}%/năm)",
                     f"the stock's volatility ({x}% a year)")
    if name == "atr_14_norm":
        x = num(100 * v, 1)
        return _pick(language, f"biên độ trung bình ({x}%/phiên)",
                     f"average range ({x}% a session)")
    if name == "range_1":
        return _pick(language, f"biên độ phiên gần nhất ({num(100 * v, 1)}%)",
                     f"last session's range ({num(100 * v, 1)}%)")
    if name == "vol_ratio_20":
        return _pick(language,
                     f"khối lượng so với bình thường (gấp {num(v, 1)} lần "
                     f"trung bình 20 phiên)",
                     f"volume vs normal ({num(v, 1)}x the 20-session "
                     f"average)")
    if name == "sec_rs_ratio":
        return _pick(
            language,
            f"ngành {'mạnh' if v >= 100 else 'yếu'} hơn thị trường (sức mạnh "
            f"{num(v, 1)})",
            f"sector {'stronger' if v >= 100 else 'weaker'} than the market "
            f"(strength {num(v, 1)})")
    if name == "sec_rs_momentum":
        return _pick(
            language,
            f"ngành đang {'tăng tốc' if v >= 100 else 'chậm lại'} (động lượng "
            f"{num(v, 1)})",
            f"sector {'accelerating' if v >= 100 else 'slowing'} (momentum "
            f"{num(v, 1)})")
    if name in ("idx_dist_ma20", "idx_dist_ma50"):
        k = name[-2:]
        return _pick(
            language,
            f"VNINDEX {'trên' if up else 'dưới'} trung bình {k} phiên "
            f"({pct(100 * v, 1)})",
            f"VNINDEX {'above' if up else 'below'} its {k}-session average "
            f"({pct(100 * v, 1)})")
    if name == "idx_vol_20":
        return _pick(language,
                     f"dao động của thị trường ({num(100 * v, 1)}%/năm)",
                     f"market volatility ({num(100 * v, 1)}% a year)")
    if name == "idx_vol_pctile":
        return _pick(language,
                     f"dao động thị trường so với 1 năm qua (bách phân vị "
                     f"{num(100 * v)})",
                     f"market volatility vs the past year (percentile "
                     f"{num(100 * v)})")
    if name == "breadth_up":
        return _pick(language,
                     f"độ lan toả thị trường ({num(100 * v)}% mã tăng)",
                     f"market breadth ({num(100 * v)}% of stocks up)")
    if name == "breadth_above_ma20":
        return _pick(language,
                     f"tỷ lệ mã trên trung bình 20 phiên ({num(100 * v)}%)",
                     f"stocks above their 20-session average "
                     f"({num(100 * v)}%)")
    if name == "liquidity_ratio":
        return _pick(language,
                     f"thanh khoản thị trường (gấp {num(v, 2)} lần trung "
                     f"bình)",
                     f"market liquidity ({num(v, 2)}x the average)")
    return f"{name} ({num(v, 3)})"


def plain_drivers(explanation: str, values: pd.Series | None,
                  language: str = "vi", top: int | None = None) -> str:
    """Rewrite a model explanation with the features' real values.

    Args:
        explanation: Model drivers such as ``"ma20_ma50 +1.94, ret_20
            +0.73"``.
        values: Feature values of the stock on the session, or None.
        language: Output language.
        top: Keep only the first ``top`` drivers (all when None).

    Returns:
        The drivers as sentences joined by ``; `` (empty when unknown).
    """
    if not explanation or values is None:
        return ""
    sentences = []
    for item in str(explanation).split(","):
        name = item.strip().split(" ")[0]
        if not name or name not in values.index:
            continue
        sentence = describe_feature(name, values[name], language)
        if sentence:
            sentences.append(sentence)
        if top is not None and len(sentences) >= top:
            break
    return "; ".join(sentences)


def summary_lines(
    market: dict[str, Any],
    sectors_top: list[dict[str, Any]],
    sectors_bottom: list[dict[str, Any]],
    outlook: list[dict[str, Any]],
    language: str = "vi",
) -> list[str]:
    """Write the two or three summary sentences at the top.

    Args:
        market: Output of :func:`market_summary`.
        sectors_top: Strongest sectors (rotation rows).
        sectors_bottom: Weakest sectors (rotation rows).
        outlook: Output of :func:`outlook_rows` (VNINDEX is used).
        language: Output language.

    Returns:
        Sentences on the market, the money flow and the model's view.
    """
    num = functools.partial(format_number, language=language)
    pct = functools.partial(format_percent, language=language)
    up = market["breadth_up"]
    if market["regime"] == "uptrend" and up >= 0.5:
        mood = _pick(language, "đang khoẻ", "is healthy")
    elif market["regime"] == "downtrend" or up < 0.4:
        mood = _pick(language, "đang yếu", "is weak")
    else:
        mood = _pick(language, "chưa rõ xu hướng", "has no clear trend")
    move = market["change_pct"]
    verb = _pick(language, "tăng" if move >= 0 else "giảm",
                 "rose" if move >= 0 else "fell")
    only = _pick(language, "chỉ ", "only ") if up < 0.4 else ""
    lines = [_pick(
        language,
        f"Thị trường {mood}: VNINDEX {verb} ({pct(move)}), {only}"
        f"{num(up * 100)}% cổ phiếu tăng giá.",
        f"The market {mood}: VNINDEX {verb} ({pct(move)}), {only}"
        f"{num(up * 100)}% of stocks rose.")]
    into = [translate_term(r["sector"], language) for r in sectors_top
            if r["quadrant"] in ("leading", "improving")]
    out = [translate_term(r["sector"], language) for r in sectors_bottom
           if r["quadrant"] in ("lagging", "weakening")]
    joiner = _pick(language, " và ", " and ")
    flow = []
    if into:
        flow.append(_pick(language, f"tiền đang chảy vào {joiner.join(into)}",
                          f"money is flowing into {joiner.join(into)}"))
    if out:
        flow.append(_pick(language, f"rút khỏi {joiner.join(out)}",
                          f"out of {joiner.join(out)}"))
    if flow:
        text = "; ".join(flow)
        lines.append(text[0].upper() + text[1:] + ".")
    index = next((r for r in outlook if r["symbol"] == "VNINDEX"), None)
    if index and index["h1"]:
        f = index["h1"]
        if f["p_max"] < 0.55:
            lines.append(_pick(
                language,
                f"Mô hình chưa thấy tín hiệu rõ cho phiên tới (khả năng tăng "
                f"{num(f['p_up'] * 100)}%, giảm {num(f['p_down'] * 100)}%).",
                f"The model sees no clear signal for the next session (up "
                f"{num(f['p_up'] * 100)}%, down {num(f['p_down'] * 100)}%)."))
        else:
            view = confidence_words(f["p_max"], f["label"], language)
            share = num(f["p_max"] * 100)
            lines.append(_pick(
                language,
                f"Mô hình {view} cho phiên tới ({share}%).",
                f"The model is {view} for the next session ({share}%)."))
    return lines


def _none_if_nan(value: Any) -> float | None:
    """Convert NaN to None for the template.

    Args:
        value: A number or NaN.

    Returns:
        The float, or None.
    """
    value = float(value)
    return None if math.isnan(value) else value
