import pandas as pd
import pytest

from market_radar.calendar import TradingCalendar

# Realised sessions: Wed 2026-12-30 and Thu 2026-12-31.
SESSIONS = ["2026-12-28", "2026-12-29", "2026-12-30", "2026-12-31"]
HOLIDAYS = ["2027-01-01"]


@pytest.fixture
def calendar():
    return TradingCalendar(SESSIONS, HOLIDAYS)


def test_next_sessions_skip_weekend_and_holiday(calendar):
    nxt = calendar.next_sessions("2026-12-31", 3)
    assert [d.date().isoformat() for d in nxt] == [
        "2027-01-04", "2027-01-05", "2027-01-06"]


def test_next_sessions_start_with_realised_ones(calendar):
    nxt = calendar.next_sessions("2026-12-29", 3)
    assert [d.date().isoformat() for d in nxt] == [
        "2026-12-30", "2026-12-31", "2027-01-04"]


def test_session_after(calendar):
    assert calendar.session_after("2026-12-31", 5) == pd.Timestamp(
        "2027-01-08")


def test_expected_asof_with_overnight_publication(calendar):
    # Run on Monday 4 Jan morning: Friday is a holiday, so Thursday's
    # bars are the latest that must be published.
    assert calendar.expected_asof("2027-01-04", 1) == pd.Timestamp(
        "2026-12-31")
    # Run on Tuesday 5 Jan morning: Monday's bars are expected.
    assert calendar.expected_asof("2027-01-05", 1) == pd.Timestamp(
        "2027-01-04")


def test_expected_asof_same_evening(calendar):
    assert calendar.expected_asof("2027-01-05", 0) == pd.Timestamp(
        "2027-01-05")


def test_position_of_realised_sessions(calendar):
    assert calendar.position("2026-12-30") == 2
    with pytest.raises(KeyError):
        calendar.position("2027-01-04")


def test_before_calendar_start_raises(calendar):
    with pytest.raises(ValueError):
        calendar.last_trading_day_on_or_before("2026-01-01")
