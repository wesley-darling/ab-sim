# domain/entities/driver.py
from dataclasses import dataclass

from ab_sim.domain.entities.motion import Coord, MoveTask


@dataclass
class Driver:
    id: int
    loc: Coord
    state: str = "idle"  # "idle" | "to_pickup" | "wait" | "to_dropoff"
    task_id: int = 0
    current_move: MoveTask | None = None
