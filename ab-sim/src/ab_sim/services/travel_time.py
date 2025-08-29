# ab_sim/app/policy/travel_time.py
from ab_sim.app.protocols import Mechanics, TravelTimeService
from ab_sim.domain.state import Driver, TripState


class MechanicsTravelTime(TravelTimeService):
    def __init__(self, mechanics: Mechanics):
        self.speed_sampler = mechanics.speed_sampler
        self.route_planner = mechanics.route_planner

    def _duration(self, a, b, now: float, **kw) -> float:
        d = self.route_planner.distance_m(a, b)  # or call your router
        v = self.speed_sampler.speed_mps(now, **kw)  # protocol method
        return d / max(0.1, v)

    def duration_to_pickup(self, driver, trip, now: float) -> float:
        return self._duration(driver.pos, trip.pickup.pos, now)

    def duration_to_dropoff(self, driver, trip, now: float) -> float:
        return self._duration(trip.pickup.pos, trip.dropoff.pos, now)

    def duration_reposition(self, driver, now: float) -> float:
        # If you have a plan/target, compute to that; else 0.
        return 0.0


class FixedDurationTravelTime(MechanicsTravelTime):
    """Helper for tests; swap with real speed model later."""

    def __init__(
        self,
        pickup_s: float = 10.0,
        dropoff_s: float = 20.0,
        reposition_s: float = 30.0,
    ):
        self.pickup_s = pickup_s
        self.dropoff_s = dropoff_s
        self.reposition_s = reposition_s

    def duration_to_pickup(self, driver: Driver, trip: TripState, now: float) -> float:
        return self.pickup_s

    def duration_to_dropoff(self, driver: Driver, trip: TripState, now: float) -> float:
        return self.dropoff_s

    def duration_reposition(self, driver: Driver, now: float) -> float:
        return self.reposition_s
