# domain/entities/rider.py
from dataclasses import dataclass

from ab_sim.domain.entities.motion import Coord


@dataclass
class Rider:
    id: int
    pickup: Coord
    dropoff: Coord
    max_wait_s: float
    walk_s: float
