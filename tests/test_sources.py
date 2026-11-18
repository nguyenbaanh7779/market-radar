import datetime as dt

import pandas as pd
import pytest
import requests

from market_radar.config import ArenaSettings, VnstockSettings
from market_radar.data.sources import (
    ArenaSource,
    SourceError,
    VnstockSource,
    normalize_bars,
)

ARENA_ITEMS = [  # Arena returns newest first, volume null
    {"symbol": "VCB", "interval": "1d", "session_date": "2026-11-16",
     "bar_start_at": "2026-11-15T17:00:00.000Z", "open": 53.8, "high": 54.1,
     "low": 53.2, "close": 53.2, "volume": None, "source": "flow_mdp"},
    {"symbol": "VCB", "interval": "1d", "session_date": "2026-11-13",
     "bar_start_at": "2026-11-12T17:00:00.000Z", "open": 53.9, "high": 54.0,
     "low": 53.6, "close": 53.8, "volume": None, "source": "flow_mdp"},
]


class FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.headers = {}

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params))
        return self.responses.pop(0)


def arena(responses):
    session = FakeSession(responses)
    source = ArenaSource(ArenaSettings(retries=2, pause_s=0), session=session,
                         sleep=lambda _: None)
    return source, session


def test_arena_parses_and_sorts_bars():
    payload = {"success": True, "data": {"items": ARENA_ITEMS}}
    source, session = arena([FakeResponse(payload)])
    bars = source.fetch("VCB", dt.date(2026, 11, 1), dt.date(2026, 11, 16))
    assert list(bars["date"]) == [pd.Timestamp("2026-11-13"),
                                  pd.Timestamp("2026-11-16")]
    assert bars["close"].tolist() == [53.8, 53.2]
    assert bars["volume"].isna().all()
    assert (bars["source"] == "arena").all()
    url, params = session.calls[0]
    assert url.endswith("/eod/market-bars")
    assert params == {"symbol": "VCB", "from": "2026-11-01",
                      "to": "2026-11-16", "interval": "1d"}


def test_arena_retries_then_succeeds():
    payload = {"success": True, "data": {"items": ARENA_ITEMS}}
    source, session = arena([FakeResponse({}, status=502),
                             FakeResponse(payload)])
    bars = source.fetch("VCB", dt.date(2026, 11, 1), dt.date(2026, 11, 16))
    assert len(bars) == 2
    assert len(session.calls) == 2


def test_arena_raises_after_retries():
    source, _ = arena([FakeResponse({}, status=500),
                       FakeResponse({}, status=500)])
    with pytest.raises(SourceError):
        source.fetch("VCB", dt.date(2026, 11, 1), dt.date(2026, 11, 16))


def test_arena_empty_items():
    payload = {"success": True, "data": {"items": []}}
    source, _ = arena([FakeResponse(payload)])
    bars = source.fetch("BANKING", dt.date(2026, 1, 1), dt.date(2026, 2, 1))
    assert bars.empty
    assert "close" in bars.columns


def test_normalize_drops_duplicates_and_missing_close():
    raw = pd.DataFrame({
        "date": ["2026-01-02", "2026-01-02", "2026-01-05"],
        "open": [1, 1, 2], "high": [1, 1, 2], "low": [1, 1, 2],
        "close": [1.0, 1.1, None], "volume": [10, 11, 12],
    })
    bars = normalize_bars(raw, "test")
    assert len(bars) == 1
    assert bars["close"].iloc[0] == 1.1


class StubOhlcv:
    def __init__(self, symbol, calls):
        self.symbol = symbol
        self.calls = calls

    def ohlcv(self, start, end, interval):
        self.calls.append((self.symbol, start, end, interval))
        times = pd.to_datetime(["2026-11-13 07:00", "2026-11-16 07:00"])
        return pd.DataFrame({
            "time": times.tz_localize("Asia/Ho_Chi_Minh"),
            "open": [1.0, 2.0], "high": [1.0, 2.0], "low": [1.0, 2.0],
            "close": [1.0, 2.0], "volume": [100, 200],
        })


class StubMarket:
    def __init__(self, provider):
        self.provider = provider
        self.calls = []
        self.kinds = []

    def equity(self, symbol):
        self.kinds.append("equity")
        return StubOhlcv(symbol, self.calls)

    def index(self, symbol):
        self.kinds.append("index")
        return StubOhlcv(symbol, self.calls)


def test_vnstock_adapter_normalises_v6_frames():
    markets = []

    def factory(provider):
        markets.append(StubMarket(provider))
        return markets[-1]

    source = VnstockSource(VnstockSettings(provider="dnse", pause_s=0),
                           market_factory=factory, sleep=lambda _: None)
    bars = source.fetch("VNINDEX", dt.date(2026, 11, 1),
                        dt.date(2026, 11, 16))
    source.fetch("VCB", dt.date(2026, 11, 1), dt.date(2026, 11, 16))
    assert markets[0].provider == "dnse"
    assert markets[0].kinds == ["index", "equity"]
    assert list(bars["date"]) == [pd.Timestamp("2026-11-13"),
                                  pd.Timestamp("2026-11-16")]
    assert bars["volume"].tolist() == [100.0, 200.0]
    assert markets[0].calls[0][3] == "1D"
