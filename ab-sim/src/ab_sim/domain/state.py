# ab_sim/domain/state.py
from dataclasses import dataclass, field

from ab_sim.domain.entities.driver import Driver
from ab_sim.domain.entities.motion import Coord
from ab_sim.domain.entities.rider import Rider


@dataclass
class TripState:
    rider_id: int
    driver_id: int
    origin: Coord
    dest: Coord
    driver_at_pickup_t: float | None = None
    rider_at_pickup_t: float | None = None
    boarding_started_t: float | None = None
    boarded: bool = False
    alighting_started_t: float | None = None


@dataclass
class WorldState:
    capacity: int = 0
    geo: str = ""
    drivers: dict[int, Driver] = field(default_factory=dict)
    riders: dict[int, Rider] = field(default_factory=dict)
    trips: dict[int, TripState] = field(default_factory=dict)
    idle_driver_ids: set[int] = field(default_factory=set)
    queued_rider_ids: set[int] = field(default_factory=set)

    # active assignment index: (driver_id, task_id) -> rider_id
    active_task: dict[tuple[int, int], int] = field(default_factory=dict)

    def add_driver(self, d: Driver) -> None:
        self.drivers[d.id] = d
        if d.state == "idle":
            self.idle_driver_ids.add(d.id)

    def get_idle_driver(self) -> Driver | None:
        if not self.idle_driver_ids:
            return None
        did = next(iter(self.idle_driver_ids))
        self.idle_driver_ids.remove(did)
        return self.drivers[did]

    def return_idle(self, d: Driver) -> None:
        d.state = "idle"
        d.current_move = None
        self.idle_driver_ids.add(d.id)


# store TripState by rider_id or trip_id
# world.trips[rider_id] -> TripState
