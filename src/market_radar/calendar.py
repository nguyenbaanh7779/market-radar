"""Trading calendar: realised sessions from data, future ones projected."""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable

import pandas as pd

DateLike = str | dt.date | pd.Timestamp


def to_day(value: DateLike) -> pd.Timestamp:
    """Normalise a date-like value to a midnight timestamp.

    Args:
        value: Date, timestamp or ``YYYY-MM-DD`` text.

    Returns:
        Timezone-naive timestamp at midnight.
    """
    stamp = pd.Timestamp(value)
    if stamp.tzinfo is not None:
        stamp = stamp.tz_localize(None)
    return stamp.normalize()


class TradingCalendar:
    """Trading sessions of the Vietnamese market.

    Past sessions are the dates that actually have index bars. Future
    sessions are projected as weekdays that are not listed holidays.

    Args:
        sessions: Dates with index bars (e.g. VNINDEX), in any order.
        holidays: Exchange holidays used for the projection.
    """

    def __init__(
        self,
        sessions: Iterable[DateLike],
        holidays: Iterable[DateLike] = (),
    ) -> None:
        days = sorted({to_day(day) for day in sessions})
        if not days:
            raise ValueError("A trading calendar needs at least one session")
        self._sessions = pd.DatetimeIndex(days)
        self._position = {day: i for i, day in enumerate(days)}
        self._holidays = frozenset(to_day(day) for day in holidays)

    @property
    def sessions(self) -> pd.DatetimeIndex:
        """Return the realised sessions in ascending order."""
        return self._sessions

    @property
    def last(self) -> pd.Timestamp:
        """Return the most recent realised session."""
        return self._sessions[-1]

    def is_trading_day(self, day: DateLike) -> bool:
        """Tell whether a day is (or is projected to be) a session.

        Args:
            day: Day to test.

        Returns:
            True for realised sessions; for days after the last realised
            session, True on weekdays that are not holidays.
        """
        day = to_day(day)
        if day <= self.last:
            return day in self._position
        return day.weekday() < 5 and day not in self._holidays

    def position(self, day: DateLike) -> int:
        """Return the index of a realised session.

        Args:
            day: A realised session.

        Returns:
            Zero-based position in :attr:`sessions`.

        Raises:
            KeyError: If ``day`` is not a realised session.
        """
        return self._position[to_day(day)]

    def next_sessions(self, after: DateLike, count: int) -> list[pd.Timestamp]:
        """List the sessions that follow a day.

        Args:
            after: Reference day (excluded).
            count: Number of sessions wanted.

        Returns:
            The next ``count`` sessions, realised ones first, then projected.
        """
        after = to_day(after)
        found = list(self._sessions[self._sessions > after][:count])
        day = max(after, self.last)
        while len(found) < count:
            day += pd.Timedelta(days=1)
            if self.is_trading_day(day):
                found.append(day)
        return found

    def session_after(self, day: DateLike, count: int = 1) -> pd.Timestamp:
        """Return the session ``count`` sessions after a day.

        Args:
            day: Reference day.
            count: How many sessions ahead.

        Returns:
            The target session.
        """
        return self.next_sessions(day, count)[-1]

    def last_trading_day_on_or_before(self, day: DateLike) -> pd.Timestamp:
        """Return the latest (realised or projected) session up to a day.

        Args:
            day: Reference day (included).

        Returns:
            The latest trading day not after ``day``.

        Raises:
            ValueError: If ``day`` is before the first realised session.
        """
        day = to_day(day)
        if day < self._sessions[0]:
            raise ValueError(f"{day.date()} is before the calendar starts")
        while not self.is_trading_day(day):
            day -= pd.Timedelta(days=1)
        return day

    def expected_asof(
        self, today: DateLike, publish_lag_days: int
    ) -> pd.Timestamp:
        """Return the session whose bars a run on ``today`` should see.

        Args:
            today: Local date of the run.
            publish_lag_days: Days between a session and the publication
                of its bars (1 when bars arrive the next morning).

        Returns:
            The latest session that must already be published.
        """
        cutoff = to_day(today) - pd.Timedelta(days=publish_lag_days)
        return self.last_trading_day_on_or_before(cutoff)
