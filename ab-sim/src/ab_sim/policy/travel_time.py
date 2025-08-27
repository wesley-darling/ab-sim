# ab_sim/app/policy/travel_time.py
from ab_sim.domain.state import Driver, TripState


class FixedSpeedModel:
    """Helper for tests; swap with real speed model later."""

    def __init__(self, pickup_s: float = 10.0, dropoff_s: float = 20.0, reposition_s: float = 30.0):
        self.pickup_s = pickup_s
        self.dropoff_s = dropoff_s
        self.reposition_s = reposition_s

    def duration_to_pickup(self, driver: Driver, trip: TripState, now: float) -> float:
        return self.pickup_s

    def duration_to_dropoff(self, driver: Driver, trip: TripState, now: float) -> float:
        return self.dropoff_s

    def duration_reposition(self, driver: Driver, now: float) -> float:
        return self.reposition_s
