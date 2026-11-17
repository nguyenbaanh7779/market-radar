import datetime as dt

import pytest

from market_radar.config import load_settings
from tests.conftest import REPO_ROOT


def test_repository_settings_load():
    settings = load_settings(REPO_ROOT)
    assert settings.labels.horizons == (1, 5)
    assert settings.labels.sideway_band_pct == pytest.approx(0.2)
    assert settings.data.sample_start == dt.date(2023, 1, 1)
    assert settings.trading.lot_size == 100
    assert dt.date(2027, 1, 1) in settings.holidays


def test_universe_lists_are_consistent():
    universe = load_settings(REPO_ROOT).universe
    assert len(universe.vn30) == 30
    assert len(set(universe.vn30)) == 30
    assert set(universe.banks) <= set(universe.stocks)
    assert universe.sector_of("VCB") == "banking"
    assert universe.sector_of("BVH") is None
    assert universe.exchange_of("SHS") == "HNX"
    assert universe.price_limit_pct("VCB") == 7.0
    assert universe.instruments[:3] == ("VNINDEX", "VN30", "BANKS")
    assert "BANKS" not in universe.fetch_symbols


def test_unknown_setting_is_rejected():
    with pytest.raises(KeyError):
        load_settings(REPO_ROOT, overrides={"labels": {"band": 1}})


def test_overrides_and_fingerprint():
    base = load_settings(REPO_ROOT)
    changed = load_settings(
        REPO_ROOT, overrides={"labels": {"sideway_band_pct": 0.5}}
    )
    assert changed.labels.sideway_band_pct == 0.5
    assert base.fingerprint() != changed.fingerprint()
