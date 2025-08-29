import math
from collections.abc import Iterable

from ab_sim.app.protocols import PathTraverser, SpeedSampler
from ab_sim.domain.entities.geography import Path, Point
from ab_sim.domain.entities.motion import MovePlan, MoveTask


def eta(a: Point, b: Point, speed_mps: float) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    dist = math.hypot(dx, dy)  # or Manhattan if that is your model
    return 0.0 if dist == 0 else dist / max(speed_mps, 1e-9)


def start_move(now: float, loc: Point, dest: Point, speed_mps: float) -> MoveTask:
    return MoveTask(start=loc, end=dest, start_t=now, end_t=now + eta(loc, dest, speed_mps))


class PiecewiseConstSpeedTraverser(PathTraverser):
    def eta_s(self, path: Path, t0: float, speed: SpeedSampler, **kw) -> float:
        t = t0
        for seg in path.segments:
            v = max(0.1, speed.speed_mps(t, edge_id=seg.edge_id, **kw))
            t += seg.length_m / v
        return t

    def checkpoints(
        self, path: Path, t0: float, speed: SpeedSampler, step_m: float = 50.0, **kw
    ) -> Iterable[tuple[float, Point]]:
        t = t0
        for seg in path.segments:
            v = max(0.1, speed.speed_mps(t, edge_id=seg.edge_id, **kw))
            if seg.length_m <= step_m:
                t += seg.length_m / v
                yield (t, seg.end)
            else:
                steps = max(1, math.ceil(seg.length_m / step_m))
                for k in range(1, steps + 1):
                    dm = min(k * step_m, seg.length_m)
                    dt = dm / v
                    s = dm / seg.length_m
                    p = Point(
                        seg.start.x + s * (seg.end.x - seg.start.x),
                        seg.start.y + s * (seg.end.y - seg.start.y),
                    )
                    yield (t + dt, p)
                t += seg.length_m / v

    def plan(
        self,
        path: Path,
        t0: float,
        speed: SpeedSampler,
        dow: int | None = None,
        hour: int | None = None,
    ) -> MovePlan:
        t = t0
        tasks = []
        for seg in path.segments:
            v = max(0.1, speed.speed_mps(t, edge_id=seg.edge_id, dow=dow, hour=hour))
            dt = seg.length_m / v
            tasks.append(MoveTask(start=seg.start, end=seg.end, start_t=t, end_t=t + dt))
            t += dt
        return MovePlan(tasks=tasks, total_length_m=path.total_length_m, start_t=t0, end_t=t)
