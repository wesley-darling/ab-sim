from collections.abc import Iterable
from typing import Protocol, runtime_checkable

from ab_sim.domain.entities.geography import Path, Point, Segment


# ------------- Mechanics --------------------
@runtime_checkable
class OriginDestinationSampler(Protocol):
    """
    Responsibilities:
    • Sample plausible origins/destinations given demand geography.
    • Snap free points to the service network (vehicle or rider context).
    Units: meters for coordinates/distances; seconds for times elsewhere.
    """

    def sample_origin(self, rng) -> Point: ...
    def sample_destination(self, rng) -> Point: ...
    def snap(self, p: Point, kind: str = "vehicle") -> tuple[Point, Segment | None]:
        """Return snapped point + optional 'walking' segment from p to snapped location."""


@runtime_checkable
class ODSampleFn(Protocol):
    def sample(self, rng) -> Point: ...


@runtime_checkable
class RoutePlanner(Protocol):
    """
    Responsibilities:
      • Compute a path between two points (on or off network).
      • Compute network distance between points.
    """

    def route(self, a: Point, b: Point) -> Path: ...
    def distance_m(self, a: Point, b: Point) -> float: ...


@runtime_checkable
class SpeedSampler(Protocol):
    """
    Return instantaneous speed in meters/second at time t_s.
    Contextual factors (edge_id, day-of-week, hour) are optional.
    Must be >= 0.1 m/s to avoid degenerate division.
    """

    def speed_mps(
        self,
        t_s: float,
        *,
        edge_id: int | None = None,
        dow: int | None = None,
        hour: int | None = None,
    ) -> float: ...


@runtime_checkable
class PathTraverser(Protocol):
    """
    Responsibilities:
      • Integrate travel time over a path given a SpeedSampler.
      • Optionally yield coarse checkpoints for mid-edge events/logging.
    """

    def eta_s(
        self,
        path: Path,
        t0_s: float,
        speed: SpeedSampler,
        *,
        dow: int | None = None,
        hour: int | None = None,
    ) -> float: ...
    def checkpoints(
        self,
        path: Path,
        t0_s: float,
        speed: SpeedSampler,
        *,
        step_m: float = 50.0,  # coarse-grain
        dow: int | None = None,
        hour: int | None = None,
    ) -> Iterable[tuple[float, Point]]:
        """Yield (t_s, location) checkpoints along the path."""


@runtime_checkable
class TravelTimeService(Protocol):
    def duration_to_pickup(self, driver, trip, now: float) -> float: ...
    def duration_to_dropoff(self, driver, trip, now: float) -> float: ...
    def duration_reposition(self, driver, now: float) -> float: ...


@runtime_checkable
class Mechanics(Protocol):
    """
    Convenience façade bundling the core mechanics components.
    Provides common helpers so call sites don’t need to juggle pieces.
    """

    od_sampler: OriginDestinationSampler
    route_planner: RoutePlanner
    speed_sampler: SpeedSampler
    path_traverser: PathTraverser

    def eta_s(
        self,
        a: Point,
        b: Point,
        t0_s: float,
        *,
        dow: int | None = None,
        hour: int | None = None,
    ) -> float:
        path = self.route_planner.route(a, b)
        return self.path_traverser.travel_time_s(path, t0_s, self.speed_sampler, dow=dow, hour=hour)

    def distance_m(self, a: Point, b: Point) -> float:
        return self.route_planner.distance_m(a, b)


# --------------- Policies -------------------------


@runtime_checkable
class PricingPolicy(Protocol):
    def fare(self, driver, trip, now) -> float: ...


@runtime_checkable
class MatchingPolicy(Protocol):
    pass


@runtime_checkable
class IdlePolicy(Protocol):
    pass


@runtime_checkable
class DwellPolicy(Protocol):
    pass


@runtime_checkable
class DispatchPolicy(Protocol):
    pass


@runtime_checkable
class RebalancingPolicy(Protocol):
    pass
