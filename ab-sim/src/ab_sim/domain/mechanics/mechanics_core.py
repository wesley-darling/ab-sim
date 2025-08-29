# ab_sim/domain/mechanics/mechanics_core.py
from dataclasses import dataclass

from ab_sim.app.protocols import (
    Mechanics,
    OriginDestinationSampler,
    PathTraverser,
    RoutePlanner,
    SpeedSampler,
)
from ab_sim.domain.entities.geography import Path, Point
from ab_sim.domain.entities.motion import MovePlan


@dataclass
class Mechanics(Mechanics):
    od_sampler: OriginDestinationSampler
    route_planner: RoutePlanner
    speed_sampler: SpeedSampler
    path_traverser: PathTraverser

    def od_pair(self, rng):
        return self.od_sampler.sample_origin(rng), self.od_sampler.sample_destination(rng)

    def route(self, a: Point, b: Point) -> Path:
        return self.route_planner.route(a, b)

    def eta_s(self, a: Point, b: Point, t0: float, **time_kw) -> float:
        return self.path_traverser.eta_s(
            self.route_planner.route(a, b), t0, self.speed_sampler, **time_kw
        )

    def distance_m(self, a: Point, b: Point) -> float:
        return self.route_planner.distance_m(a, b)

    def progress(self, a: Point, b: Point, t0: float, **time_kw):
        yield from self.path_traverser.checkpoints(
            self.route_planner.route(a, b), t0, self.speed_sampler, **time_kw
        )

    def move_plan(self, a: Point, b: Point, t0: float, **time_kw) -> MovePlan:
        return self.path_traverser.plan(
            self.route_planner.route(a, b), t0, self.speed_sampler, **time_kw
        )
