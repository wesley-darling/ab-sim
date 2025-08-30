from types import SimpleNamespace

import pytest

from ab_sim.app.controllers.trips import TripHandler
from ab_sim.app.events import DriverLegArrive, TripAssigned
from ab_sim.app.protocols import Point
from ab_sim.domain.entities.driver import Driver
from ab_sim.policy.pricing import ConstantPricingPolicy
from ab_sim.services.travel_time import FixedDurationTravelTime
from ab_sim.sim.clock import SimClock
from ab_sim.sim.metrics import Metrics


# --- Minimal world stub for TripHandler unit tests ---
class _WorldStub:
    def __init__(self, driver: Driver, trip, rider, idle=True):
        self.drivers = {driver.id: driver}
        self.trips = {trip.rider_id: trip}
        self.riders = {trip.rider_id: rider}
        self.active_task = {}
        self.idle = {driver.id} if idle else set()

    def return_idle(self, d: Driver):
        self.idle.add(d.id)


# ------------------ TRIPHANDLER REGRESSIONS ------------------


def test_on_trip_assigned_uses_traveltime_even_when_pickup_is_same_location():
    # Driver at (0,0); rider pickup also (0,0) — mechanics ETA would be 0,
    # but FixedDurationTravelTime must schedule +pickup_s.
    d = Driver(id=1, loc=Point(0.0, 0.0))
    d.task_id = 1
    trip = SimpleNamespace(
        rider_id=101,
        origin=Point(0.0, 0.0),
        dest=Point(1.0, 1.0),
        driver_id=-1,
        boarded=False,
        rider_at_pickup_t=None,
    )
    rider = SimpleNamespace(max_wait_s=999.0)

    world = _WorldStub(d, trip, rider, idle=True)
    travel_time = FixedDurationTravelTime(pickup_s=10.0, dropoff_s=20.0, reposition_s=10.0)
    h = TripHandler(
        world=world,
        matching=None,
        travel_time=travel_time,
        clock=SimClock.utc_epoch(2025, 1, 1, 0, 0, 0),
        rng=None,
        pricing=ConstantPricingPolicy(0),
        metrics=Metrics("reg"),
        mechanics=None,  # mechanics optional for this test
        max_driver_wait_s=300.0,
        dwell=None,
    )

    ev = TripAssigned(t=0.0, rider_id=101, driver_id=1, task_id=1)
    out = h.on_trip_assigned(ev)

    # First event should be pickup arrival at t=10.0, not 0.0
    arr = next(e for e in out if isinstance(e, DriverLegArrive))
    assert arr.kind == "pickup"
    assert abs(arr.t - 10.0) < 1e-9

    # Driver should be removed from idle immediately
    assert 1 not in world.idle


def test_driver_leg_arrive_ignores_stale_events_by_task_id():
    d = Driver(id=1, loc=Point(0.0, 0.0))
    d.task_id = 1
    trip = SimpleNamespace(
        rider_id=201,
        origin=Point(0.0, 0.0),
        dest=Point(1.0, 1.0),
        driver_id=1,
        boarded=False,
        rider_at_pickup_t=None,
    )
    rider = SimpleNamespace(max_wait_s=999.0)

    world = _WorldStub(d, trip, rider, idle=False)
    travel_time = FixedDurationTravelTime(10.0, 20.0, 10.0)
    h = TripHandler(
        world=world,
        matching=None,
        travel_time=travel_time,
        clock=SimClock.utc_epoch(2025, 1, 1, 0, 0, 0),
        rng=None,
        pricing=ConstantPricingPolicy(0),
        metrics=Metrics("reg"),
        mechanics=None,
        max_driver_wait_s=300.0,
        dwell=None,
    )

    # Simulate a scheduled arrival for task_id=1
    stale = DriverLegArrive(t=10.0, driver_id=1, rider_id=201, kind="pickup", task_id=1)

    # But the driver got preempted/canceled and task_id advanced
    d.task_id = 2
    out = h.on_driver_leg_arrive(stale)

    # Stale event must be ignored (no outputs)
    assert out == []


# ------------------ IDEALIZED OD SAMPLER REGRESSIONS ------------------


def test_idealized_od_empty_weights_means_uniform():
    # Ensures empty/None weights don't produce NaN probabilities.
    import numpy as np

    from ab_sim.domain.mechanics.mechanics_od_samplers import IdealizedODSampler

    rng = np.random.default_rng(0)
    zones = [(0.0, 0.0, 100.0, 100.0), (100.0, 0.0, 200.0, 100.0)]
    sampler = IdealizedODSampler(zones=zones, rng=rng, weights=[])  # empty → uniform

    # Should not raise and should produce points inside the rectangles
    pts = [sampler.sample_origin() for _ in range(10)]
    for p in pts:
        assert 0.0 <= p.x <= 200.0 and 0.0 <= p.y <= 100.0


def test_idealized_od_rejects_nan_weights():
    import numpy as np

    from ab_sim.domain.mechanics.mechanics_od_samplers import IdealizedODSampler

    rng = np.random.default_rng(0)
    zones = [(0, 0, 1, 1), (1, 0, 2, 1)]
    with pytest.raises(ValueError):
        IdealizedODSampler(zones=zones, rng=rng, weights=[1.0, float("nan")])
