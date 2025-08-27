# sim/clock.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

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
