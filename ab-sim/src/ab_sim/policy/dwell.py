# ab_sim/policy/dwells.py
import numpy as np

from ab_sim.app.protocols import DwellPolicy
from ab_sim.sim.rng import RNGRegistry


class ExpBoardingAlightingPolicy(DwellPolicy):
    def __init__(self, rng_registry: RNGRegistry, board_mean_s=7.0, alight_mean_s=5.0):
        self.rng_registry = rng_registry
        self.board_mean_s = board_mean_s
        self.alight_mean_s = alight_mean_s

    def boarding_delay(self, rider_id: int, driver_id: int) -> float:
        # per-rider (or per driver+rider) stream
        g = self.rng_registry.substream("boarding", rider_id, driver_id)
        # e.g., truncated exponential
        return float(np.clip(g.exponential(self.board_mean_s), 1.0, 60.0))

    def alighting_delay(self, rider_id: int, driver_id: int) -> float:
        g = self.rng_registry.substream("alighting", rider_id, driver_id)
        return float(np.clip(g.exponential(self.alight_mean_s), 1.0, 60.0))
