from dataclasses import dataclass

Coord = tuple[float, float]  # meters


@dataclass
class MoveTask:
    start: Coord
    end: Coord
    start_t: float
    end_t: float

    def frac(self, t: float) -> float:
        if t <= self.start_t:
            return 0.0
        if t >= self.end_t:
            return 1.0
        return (t - self.start_t) / (self.end_t - self.start_t)

    def pos(self, t: float) -> Coord:
        f = self.frac(t)
        return (
            self.start[0] + f * (self.end[0] - self.start[0]),
            self.start[1] + f * (self.end[1] - self.start[1]),
        )
