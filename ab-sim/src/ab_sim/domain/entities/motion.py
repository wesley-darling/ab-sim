from dataclasses import dataclass

from ab_sim.domain.entities.geography import Point

Pt = Point | tuple[float, float]


def _to_point(p: Pt) -> Point:
    return p if isinstance(p, Point) else Point(float(p[0]), float(p[1]))


@dataclass
class MoveTask:
    start: Point
    end: Point
    start_t: float
    end_t: float

    def frac(self, t: float) -> float:
        if t <= self.start_t:
            return 0.0
        if t >= self.end_t:
            return 1.0
        return (t - self.start_t) / (self.end_t - self.start_t)

    def pos(self, t: float) -> Point:
        f = self.frac(t)
        return Point(
            self.start.x + f * (self.end.x - self.start.x),
            self.start.y + f * (self.end.y - self.start.y),
        )


@dataclass
class MovePlan:
    tasks: list[MoveTask]
    total_length_m: float
    start_t: float
    end_t: float

    def pos(self, t: float) -> Point:
        if t <= self.start_t:
            return self.tasks[0].start
        if t >= self.end_t:
            return self.tasks[-1].end
        # binary search would be fine; linear is OK (few segments)
        for m in self.tasks:
            if t <= m.end_t:
                return m.pos(t)
        return self.tasks[-1].end  # fallback

    def current_task_index(self, t: float) -> int:
        if t <= self.start_t:
            return 0
        for i, m in enumerate(self.tasks):
            if t <= m.end_t:
                return i
        return len(self.tasks) - 1
