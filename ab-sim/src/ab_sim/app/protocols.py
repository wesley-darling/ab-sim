from collections.abc import Iterable
from typing import Protocol

from ab_sim.domain.entities.geography import Path, Point, Segment


# ------------- Mechanics --------------------
class GeoSpace(Protocol):
    def sample_origin(self, rng) -> Point: ...
    def sample_destination(self, rng) -> Point: ...
    def snap(self, p: Point, kind: str = "vehicle") -> tuple[Point, Segment | None]:
        """Return snapped point + optional 'walking' segment from p to snapped location."""


class Router(Protocol):
    def route(self, a: Point, b: Point) -> Path: ...
    def distance_m(self, a: Point, b: Point) -> float: ...


class SpeedModel(Protocol):
    def speed_mps(
        self,
        t: float,
        *,
        edge_id: int | None = None,
        dow: int | None = None,
        hour: int | None = None,
    ) -> float: ...


class Mover(Protocol):
    def eta_s(
        self,
        path: Path,
        t0: float,
        speed: SpeedModel,
        dow: int | None = None,
        hour: int | None = None,
    ) -> float: ...
    def next_progress_event(
        self,
        path: Path,
        t0: float,
        speed: SpeedModel,
        step_m: float = 50.0,  # coarse-grain
        dow: int | None = None,
        hour: int | None = None,
    ) -> Iterable[tuple[float, Point]]:
        """Yield (t, location) checkpoints for optional mid-edge events/logging."""
