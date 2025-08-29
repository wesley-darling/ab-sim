# domain/entities/rider.py
from dataclasses import dataclass

from ab_sim.domain.entities.geography import Point


@dataclass
class Rider:
    id: int
    pickup: Point
    dropoff: Point
    max_wait_s: float
    walk_s: float
