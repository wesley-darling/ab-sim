from ab_sim.sim.clock import SimClock, hours


def test_weekday_and_hour_at_utc():
    clock = SimClock.utc_epoch(2025, 1, 1, 0, 0, 0)  # 2025-01-01 is Wednesday
    t0 = 0.0
    assert clock.weekday_at(t0) == 2  # Mon=0 .. Wed=2
    assert clock.hour_at(t0) == 0

    t_mid = hours(3.5)
    assert clock.hour_at(t_mid) == 3

    # next day + 3h
    t_next = hours(27.0)
    assert clock.weekday_at(t_next) == 3  # Thursday
    assert clock.hour_at(t_next) == 3


def test_dow_hour_pair():
    clock = SimClock.utc_epoch(2025, 1, 3, 23, 0, 0)  # Friday 23:00
    dow, hour = clock.dow_hour_at(hours(2.0))  # +2h => Saturday 01:00
    assert (dow, hour) == (5, 1)  # Sat=5 when Mon=0
