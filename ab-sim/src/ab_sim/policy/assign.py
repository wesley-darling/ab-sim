# ab_sim/policy/assign.py
from dataclasses import dataclass

from ab_sim.domain.state import WorldState


@dataclass
class MatchingPolicy:
    world: WorldState


@dataclass
class NearestAssign(MatchingPolicy):
    world: WorldState
