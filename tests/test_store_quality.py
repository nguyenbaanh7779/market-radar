import datetime as dt

import pandas as pd

from market_radar.data.quality import (
    compare_closes,
    quality_report,
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


def test_compare_closes():
    left = pd.DataFrame({"symbol": "AAA", "date": pd.bdate_range(
        "2026-01-05", periods=2), "close": [10.0, 10.1]})
    right = left.assign(close=[10.0, 10.0])
    out = compare_closes(left, right).iloc[0]
    assert out["common_dates"] == 2
    assert out["max_abs_bps"] == 100.0
    assert out["share_over_50bps"] == 0.5
