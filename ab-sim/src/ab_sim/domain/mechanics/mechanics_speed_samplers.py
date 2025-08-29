import math
from typing import Literal

from ab_sim.app.protocols import SpeedSampler


class GlobalSpeedSampler(SpeedSampler):
    def __init__(self, v_mps: float):
        self.v_mps = v_mps

    def speed_mps(self, t: float, **_):
        return self.v_mps


class ConstantSpeedSampler(SpeedSampler):
    def __init__(self, pickup_mps: float, dropoff_mps: float):
        self.pickup_mps = pickup_mps
        self.dropoff_mps = dropoff_mps

    def speed_mps(self, t: float, trip_leg: Literal["pickup", "dropoff"], **_):
        if trip_leg == "pickup":
            return self.pickup_mps
        if trip_leg == "dropoff":
            return self.pickup_mps


class DistDrawSpeedSampler(SpeedSampler):
    def __init__(self, rng, dist: str, params: dict[str, float], fallback_mps: float):
        self.rng, self.dist, self.p, self.fb = rng, dist, params, fallback_mps

    def speed_mps(self, t: float, **_):
        if self.dist == "lognormal":
            return max(
                0.1, self.rng.lognormvariate(self.p.get("mu", 2.0), self.p.get("sigma", 0.25))
            )
        if self.dist == "gamma":
            k = max(1, int(self.p.get("k", 9)))
            theta = self.p.get("theta", 1.0)
            s = sum(-math.log(1.0 - self.rng.random()) for _ in range(k))
            return max(0.1, s * theta)
        return self.fb


class EdgeAwareSpeedSampler(SpeedSampler):
    def __init__(self, base_mps: float, tfac: dict[str, float], efac: dict[int, float]):
        self.base, self.tfac, self.efac = base_mps, tfac, efac

    def speed_mps(
        self,
        t: float,
        *,
        edge_id: int | None = None,
        dow: int | None = None,
        hour: int | None = None,
    ):
        v = self.base
        if dow is not None and hour is not None:
            v *= self.tfac.get(f"{dow}:{hour}", 1.0)
        if edge_id is not None:
            v *= self.efac.get(edge_id, 1.0)
        return max(0.1, v)
