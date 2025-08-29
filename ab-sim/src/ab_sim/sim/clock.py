# sim/clock.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, tzinfo

SEC = 1.0
MIN = 60.0
HOUR = 3600.0
DAY = 24 * HOUR


def sec(x: float) -> float:
    return x


def minutes(x: float) -> float:
    return x * MIN


def hours(x: float) -> float:
    return x * HOUR


@dataclass(frozen=True)
class SimClock:
    epoch: datetime  # wall-time zero of t=0; naive UTC or tz-aware

    @classmethod
    def utc_epoch(cls, y: int, m: int, d: int, hh=0, mm=0, ss=0) -> SimClock:
        return cls(datetime(y, m, d, hh, mm, ss, tzinfo=UTC))

    def _with_tz(self, dt: datetime, tz: tzinfo | str | None) -> datetime:
        """Return dt in the requested timezone (tzinfo or IANA string).
        If tz is None, uses dt's own tz (or UTC if naive)."""
        if tz is None:
            return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
        if isinstance(tz, str):
            from zoneinfo import ZoneInfo  # py>=3.9

            tz = ZoneInfo(tz)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(tz)

    # wall -> sim seconds
    def to_sim(self, dt: datetime) -> float:
        delta = dt - self.epoch if dt.tzinfo else (dt.replace(tzinfo=UTC) - self.epoch)
        return delta.total_seconds()

    # sim seconds -> wall
    def to_wall(self, t: float) -> datetime:
        return self.epoch + timedelta(seconds=t)

    # day helpers
    def day_index(self, t: float) -> int:
        return int(t // DAY)

    def start_of_day(self, t: float) -> float:
        return self.day_index(t) * DAY

    def tod(self, t: float) -> float:
        """time-of-day seconds [0, DAY)"""
        return t - self.start_of_day(t)

    def weekday_at(self, t: float, *, tz: tzinfo | str | None = None) -> int:
        """Return weekday as int 0=Mon … 6=Sun (like datetime.weekday())."""
        dt = self._with_tz(self.to_wall(t), tz)
        return dt.weekday()

    def iso_weekday_at(self, t: float, *, tz: tzinfo | str | None = None) -> int:
        """Return ISO weekday as int 1=Mon … 7=Sun (like datetime.isoweekday())."""
        dt = self._with_tz(self.to_wall(t), tz)
        return dt.isoweekday()

    def hour_at(self, t: float, *, tz: tzinfo | str | None = None) -> int:
        """Return hour-of-day 0..23 in the requested time zone (DST-aware)."""
        dt = self._with_tz(self.to_wall(t), tz)
        return dt.hour

    def dow_hour_at(self, t: float) -> tuple[int, int]:
        return self.to_wall(t).weekday(), self.to_wall(t).hour
