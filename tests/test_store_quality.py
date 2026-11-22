import dataclasses
import datetime as dt

import pandas as pd

from market_radar.config import Listing
from market_radar.data.quality import (
    compare_closes,
    price_limits,
    quality_report,
    repeated_bars,
    suspect_bars,
    suspect_moves,
)
from market_radar.data.sources import empty_bars, normalize_bars
from market_radar.data.store import BarStore
from market_radar.data.update import update_bars


def bars_for(dates, closes, source="test"):
    frame = pd.DataFrame({"date": dates, "open": closes, "high": closes,
                          "low": closes, "close": closes})
    return normalize_bars(frame, source)


def test_upsert_merges_and_new_rows_win(tmp_path):
    store = BarStore(tmp_path)
    store.upsert("VCB", bars_for(["2026-11-12", "2026-11-13"], [1.0, 2.0]),
                 "t1")
    merged = store.upsert(
        "VCB", bars_for(["2026-11-13", "2026-11-16"], [2.5, 3.0]), "t2")
    assert merged["close"].tolist() == [1.0, 2.5, 3.0]
    assert merged["fetched_at"].tolist() == ["t1", "t2", "t2"]
    assert store.last_date("VCB") == pd.Timestamp("2026-11-16")
    assert store.symbols() == ["VCB"]


def test_load_many_symbols(tmp_path):
    store = BarStore(tmp_path)
    store.upsert("AAA", bars_for(["2026-11-13"], [1.0]), "t")
    store.upsert("BBB", bars_for(["2026-11-13", "2026-11-16"], [2.0, 3.0]),
                 "t")
    frame = store.load()
    assert frame["symbol"].tolist() == ["AAA", "BBB", "BBB"]
    assert store.load(["BBB"])["close"].tolist() == [2.0, 3.0]
    assert store.load(["ZZZ"]).empty


class ListSource:
    name = "list"

    def __init__(self, data):
        self.data = data
        self.requests = []

    def fetch(self, symbol, start, end):
        self.requests.append((symbol, start, end))
        if symbol == "BAD":
            from market_radar.data.sources import SourceError
            raise SourceError("boom")
        return self.data.get(symbol, empty_bars())


def test_update_uses_overlap_and_reports(tmp_path):
    store = BarStore(tmp_path)
    store.upsert("AAA", bars_for(["2026-11-02", "2026-11-13"], [1.0, 2.0]),
                 "t")
    source = ListSource({"AAA": bars_for(["2026-11-13", "2026-11-16"],
                                         [2.0, 3.0])})
    report = update_bars(store, source, ["AAA", "NEW", "BAD"],
                         start=dt.date(2019, 1, 1),
                         end=dt.date(2026, 11, 16), overlap_days=10)
    starts = {symbol: start for symbol, start, _ in source.requests}
    assert starts["AAA"] == dt.date(2026, 11, 3)
    assert starts["NEW"] == dt.date(2019, 1, 1)
    status = dict(zip(report["symbol"], report["status"], strict=True))
    assert status == {"AAA": "ok", "NEW": "empty", "BAD": "error"}
    aaa = report.set_index("symbol").loc["AAA"]
    assert aaa["new_rows"] == 1 and aaa["total_rows"] == 3


def test_suspect_moves_respect_exchange_limits(universe):
    dates = pd.bdate_range("2026-01-05", periods=3)
    frame = pd.DataFrame({
        "symbol": ["AAA"] * 3 + ["FFF"] * 3,
        "date": list(dates) * 2,
        "close": [10.0, 10.9, 10.0, 10.0, 10.9, 10.0],  # +9% then -8.3%
    })
    moves = suspect_moves(frame, universe)
    # AAA is on HOSE (7% limit): both moves breach. FFF is on HNX (10%).
    assert moves["symbol"].tolist() == ["AAA", "AAA"]


def transferred(universe, until="2026-01-07"):
    """AAA traded on HNX until ``until``, then on HOSE."""
    history = {"AAA": (Listing("HNX", dt.date.fromisoformat(until)),)}
    return dataclasses.replace(universe, exchange_history=history)


def test_price_limits_follow_the_exchange_of_the_day(universe):
    dates = pd.bdate_range("2026-01-05", periods=6)   # Mon 5 .. Mon 12
    frame = pd.DataFrame({"symbol": "AAA", "date": dates})
    limits = price_limits(frame, transferred(universe)).tolist()
    # HNX up to Wed 7, first HOSE session Thu 8 at 20%, then HOSE 7%
    assert limits == [10.0, 10.0, 10.0, 20.0, 7.0, 7.0]
    assert universe.exchange_of("AAA", dt.date(2026, 1, 7)) == "HOSE"
    assert transferred(universe).exchange_of(
        "AAA", dt.date(2026, 1, 7)) == "HNX"
    assert transferred(universe).price_limit_pct("AAA") == 7.0


def test_hnx_move_before_a_transfer_is_not_suspect(universe):
    dates = pd.bdate_range("2026-01-05", periods=6)
    #          HNX:  +9%            first HOSE: +12%   HOSE: +9%
    closes = [10.0, 10.9, 10.9, 12.208, 12.208, 13.307]
    frame = pd.DataFrame({"symbol": "AAA", "date": dates, "close": closes})
    moves = suspect_moves(frame, transferred(universe))
    assert moves["date"].tolist() == [dates[5]]
    assert moves["limit_pct"].tolist() == [7.0]
    # without the history, all three moves breach the HOSE limit
    assert len(suspect_moves(frame, universe)) == 3


def ohlc_frame(rows):
    dates = pd.bdate_range("2026-01-05", periods=len(rows))
    return pd.DataFrame([
        {"symbol": "AAA", "date": day, "open": o, "high": h, "low": low,
         "close": c} for day, (o, h, low, c) in zip(dates, rows, strict=True)
    ]), dates


def test_repeated_bars_flag_copies_and_the_bar_after():
    frame, dates = ohlc_frame([
        (10, 11, 9, 10.5), (10, 11, 9, 10.5), (10, 11, 9, 10.5),
        (10.6, 11.2, 10.4, 11.0), (11.0, 11.0, 11.0, 11.0),
    ])
    out = repeated_bars(frame)
    assert out["date"].tolist() == [dates[1], dates[2], dates[3]]
    assert out["repeat"].tolist() == [True, True, False]


def test_suspect_bars_combine_reasons_once_per_date(universe):
    frame, dates = ohlc_frame([
        (10, 10, 10, 10), (10, 10, 10, 10), (12, 12, 12, 12),
    ])
    out = suspect_bars(frame, universe)
    # day 2 is a copy; day 3 is both the bar after it and a +20% jump
    assert out["date"].tolist() == [dates[1], dates[2]]
    assert out["reason"].tolist() == ["repeat", "limit"]


def test_quality_report_counts_problems(universe):
    dates = pd.bdate_range("2026-01-05", periods=5)
    frame = pd.DataFrame({
        "symbol": "AAA",
        "date": [dates[0], dates[1], dates[3], dates[4]],  # one gap
        "open": [10.0, 10.0, 10.0, 10.0],
        "high": [10.5, 9.0, 10.5, 10.5],                   # one bad high
        "low": [9.5, 9.5, 9.5, 9.5],
        "close": [10.0, 10.2, 10.1, 10.0],
        "volume": [1.0, None, 1.0, 1.0],
    })
    report = quality_report(frame, dates, universe).iloc[0]
    assert report["missing_sessions"] == 1
    assert report["bad_ohlc"] == 1
    assert report["volume_coverage"] == 0.75
    assert report["repeated_bars"] == 0


def test_compare_closes():
    left = pd.DataFrame({"symbol": "AAA", "date": pd.bdate_range(
        "2026-01-05", periods=2), "close": [10.0, 10.1]})
    right = left.assign(close=[10.0, 10.0])
    out = compare_closes(left, right).iloc[0]
    assert out["common_dates"] == 2
    assert out["max_abs_bps"] == 100.0
    assert out["share_over_50bps"] == 0.5


class DeniedSource:
    name = "denied"

    def __init__(self):
        self.requests = []

    def fetch(self, symbol, start, end):
        from market_radar.data.sources import SourceAccessDenied
        self.requests.append(symbol)
        raise SourceAccessDenied("HTTP 403")


def test_update_stops_at_the_first_access_denied(tmp_path):
    import pytest

    from market_radar.data.sources import SourceAccessDenied
    source = DeniedSource()
    with pytest.raises(SourceAccessDenied):
        update_bars(BarStore(tmp_path), source, ["VNINDEX", "VN30", "AAA"],
                    start=dt.date(2019, 1, 1), end=dt.date(2026, 11, 16),
                    overlap_days=10)
    assert source.requests == ["VNINDEX"]
