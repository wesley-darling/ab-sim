import math

from ab_sim.domain.entities.motion import Coord, MoveTask


def eta(a: Coord, b: Coord, speed_mps: float) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    dist = math.hypot(dx, dy)  # or Manhattan if that’s your model
    return 0.0 if dist == 0 else dist / max(speed_mps, 1e-9)


def start_move(now: float, loc: Coord, dest: Coord, speed_mps: float) -> MoveTask:
    return MoveTask(start=loc, end=dest, start_t=now, end_t=now + eta(loc, dest, speed_mps))
