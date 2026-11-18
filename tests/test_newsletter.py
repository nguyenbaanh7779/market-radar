import re

import pandas as pd
import pytest

from market_radar.report import newsletter as n

MARKET = {
    "close": 1726.72, "change_pct": -0.59, "vn30_close": 1837.13,
    "vn30_change_pct": -0.39, "regime": "downtrend", "dist_ma20_pct": -0.8,
    "dist_ma50_pct": -1.6, "vol_pct": 17.6, "vol_pctile": 0.54,
    "breadth_up": 0.32, "breadth_above_ma20": 0.24, "liquidity_ratio": None,
}


@pytest.mark.parametrize("p, expected", [
    (0.46, "gần như ngang nhau"),
    (0.56, "hơi nghiêng về tăng"),
    (0.70, "nghiêng rõ về tăng"),
])
def test_confidence_words(p, expected):
    assert n.confidence_words(p, "UP", "vi") == expected


def test_confidence_words_english_down():
    assert n.confidence_words(0.6, "DOWN", "en") == "leaning down"


@pytest.mark.parametrize("name, value, expected", [
    ("ret_20", 0.08, "tăng gần đây (+8,0% trong 20 phiên)"),
    ("ret_20", -0.271, "giảm gần đây (-27,1% trong 20 phiên)"),
    ("dist_ma20", 0.03, "giá trên mức trung bình 20 phiên (+3,0%)"),
    ("dist_ma50", -0.136, "giá dưới mức trung bình 50 phiên (-13,6%)"),
    ("ma20_ma50", 0.019,
     "xu hướng trung hạn đi lên (MA20 cao hơn MA50 1,9%)"),
    ("rsi_14", 72.0, "quá mua (RSI 72)"),
    ("rsi_14", 21.0, "quá bán (RSI 21)"),
    ("rsi_14", 62.0, "lực mua nhỉnh hơn (RSI 62)"),
    ("rel_ret_20", 0.07, "mạnh hơn VNINDEX (+7,0% trong 20 phiên)"),
    ("sec_rs_ratio", 87.6, "ngành yếu hơn thị trường (sức mạnh 87,6)"),
])
def test_describe_feature_keeps_the_number(name, value, expected):
    assert n.describe_feature(name, value, "vi") == expected


def test_describe_feature_skips_and_falls_back():
    assert n.describe_feature("is_index", 1.0) is None
    assert n.describe_feature("ret_5", float("nan")) is None
    assert n.describe_feature("mystery", 0.5, "en") == "mystery (0.500)"


def test_every_feature_sentence_has_a_number():
    for name in ("ret_1", "ret_5", "rel_ret_5", "dist_ma20", "ma20_ma50",
                 "rsi_14", "macd_hist_norm", "bb_pct_b", "vol_20",
                 "atr_14_norm", "range_1", "vol_ratio_20", "sec_rs_ratio",
                 "sec_rs_momentum", "idx_dist_ma20", "idx_vol_20",
                 "idx_vol_pctile", "breadth_up", "breadth_above_ma20",
                 "liquidity_ratio"):
        for language in ("vi", "en"):
            text = n.describe_feature(name, 0.42, language)
            assert re.search(r"\(.*\d.*\)", text), (name, language, text)


def test_plain_drivers_uses_real_values():
    values = pd.Series({"ma20_ma50": -0.313, "ret_20": -0.271,
                        "dist_ma20": -0.088})
    text = n.plain_drivers("ma20_ma50 +1.94, ret_20 +0.73, dist_ma20 +0.53",
                           values, "vi", top=2)
    assert text == ("xu hướng trung hạn đi xuống (MA20 thấp hơn MA50 "
                    "31,3%); giảm gần đây (-27,1% trong 20 phiên)")
    assert n.plain_drivers("", values) == ""
    assert n.plain_drivers("ret_20 +0.1", None) == ""


def test_reversal_note_only_when_drivers_oppose_the_forecast():
    falling = pd.Series({"ret_20": -0.27, "rsi_14": 30.0})
    rising = pd.Series({"ret_20": 0.12, "rsi_14": 60.0})
    expl = "ret_20 +0.7, rsi_14 +0.1"
    assert "hồi phục" in n._reversal_note(expl, falling, "UP", "vi")
    assert n._reversal_note(expl, rising, "UP", "vi") == ""
    assert "điều chỉnh" in n._reversal_note(expl, rising, "DOWN", "vi")


def test_market_plain_sentences_keep_numbers():
    plain = n.market_plain(MARKET, "vi")
    assert plain["trend"].startswith("GIẢM")
    assert "(-0,8%)" in plain["trend"] and "(-1,6%)" in plain["trend"]
    assert plain["volatility"] == ("Dao động bình thường (17,6%/năm, cao hơn "
                                   "54% số phiên trong 1 năm qua)")
    assert plain["breadth"].startswith("Độ lan toả yếu (32%")
    assert plain["liquidity"] is None


def test_sector_plain():
    row = {"quadrant": "leading", "rs_ratio": 103.9, "rs_momentum": 106.4}
    assert n.sector_plain(row, "vi") == (
        "mạnh hơn thị trường và đang tăng tốc (sức mạnh 103,9; động lượng "
        "106,4)")


def outlook(p_up, p_side, p_down, label):
    return [{"symbol": "VNINDEX", "h5": None,
             "h1": {"label": label, "p_up": p_up, "p_sideway": p_side,
                    "p_down": p_down, "p_max": max(p_up, p_side, p_down)}}]


def test_summary_weak_market_with_flows_and_no_clear_signal():
    top = [{"sector": "real_estate", "quadrant": "leading"},
           {"sector": "industrials", "quadrant": "weakening"}]
    bottom = [{"sector": "technology", "quadrant": "lagging"}]
    lines = n.summary_lines(MARKET, top, bottom,
                            outlook(0.46, 0.21, 0.33, "UP"), "vi")
    assert lines[0] == ("Thị trường đang yếu: VNINDEX giảm (-0,59%), chỉ 32% "
                        "cổ phiếu tăng giá.")
    assert lines[1] == "Tiền đang chảy vào Bất động sản; rút khỏi Công nghệ."
    assert lines[2].startswith("Mô hình chưa thấy tín hiệu rõ")


def test_summary_healthy_market_with_a_clear_signal():
    market = {**MARKET, "regime": "uptrend", "breadth_up": 0.65,
              "change_pct": 1.2}
    lines = n.summary_lines(market, [], [], outlook(0.68, 0.1, 0.22, "UP"),
                            "vi")
    assert lines[0].startswith("Thị trường đang khoẻ: VNINDEX tăng (+1,20%)")
    assert lines[1] == "Mô hình nghiêng rõ về tăng cho phiên tới (68%)."
