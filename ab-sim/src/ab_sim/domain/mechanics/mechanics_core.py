# ab_sim/domain/mechanics/mechanics_core.py
from dataclasses import dataclass

from ab_sim.app.protocols import GeoSpace, Mover, Router, SpeedModel
from ab_sim.domain.entities.geography import Path, Point
from ab_sim.domain.entities.motion import MovePlan


@dataclass
class Mechanics:
    space: GeoSpace
    router: Router
    speed: SpeedModel
    mover: Mover

    def od_pair(self, rng):
        return self.space.sample_origin(rng), self.space.sample_destination(rng)

    def route(self, a: Point, b: Point) -> Path:
        return self.router.route(a, b)

    def eta(self, a: Point, b: Point, t0: float, **time_kw) -> float:
        return self.mover.eta_s(self.router.route(a, b), t0, self.speed, **time_kw)

    def progress(self, a: Point, b: Point, t0: float, **time_kw):
        yield from self.mover.next_progress_event(
            self.router.route(a, b), t0, self.speed, **time_kw
        )

    def move_plan(self, a: Point, b: Point, t0: float, **time_kw) -> MovePlan:
        return self.mover.plan(self.router.route(a, b), t0, self.speed, **time_kw)
