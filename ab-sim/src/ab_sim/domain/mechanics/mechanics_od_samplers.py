import math

import numpy as np

from ab_sim.app.protocols import OriginDestinationSampler
from ab_sim.domain.entities.geography import NetworkGraph, Point, Segment


class IdealizedODSampler(OriginDestinationSampler):
    def __init__(
        self,
        *,
        zones: list[tuple[float, float, float, float]],
        weights: list[float] | None = None,
        rng,
    ):
        self.zones = list(zones)
        self.rng, self.weights = rng, weights
        self._p = None if weights is None else self._normalize_weights(weights, len(self.zones))

    @staticmethod
    def _normalize_weights(weights, n):
        if weights is None:
            return None  # uniform in Generator.choice
        w = np.asarray(weights, dtype=float)
        if w.shape != (n,):
            raise ValueError(f"zone weights must have length {n}, got {w.shape[0]}")
        if not np.isfinite(w).all():
            bad = np.where(~np.isfinite(w))[0]
            raise ValueError(f"zone weights must be finite; bad indices: {bad.tolist()} ")
        s = w.sum()
        if s <= 0:
            raise ValueError("zone weights must sum to a positive value")
        return w / s

    def _pick(self):
        if not self.weights:
            idx = self.rng.integers(0, len(self.zones))
        else:
            idx = self.rng.choice(len(self.zones), p=self._p if self._p is not None else None)
        return self.zones[int(idx)]

    def _uniform(self, rect):
        x0, y0, x1, y1 = rect
        return Point(self.rng.uniform(x0, x1), self.rng.uniform(y0, y1))

    def sample_origin(self, _rng=None):
        return self._uniform(self._pick())

    def sample_destination(self, _rng=None):
        return self._uniform(self._pick())

    def snap(self, p, kind="vehicle"):
        return p, None


# -------- Empirical polygon sampler (#!stub)
class EmpiricalODSampler(OriginDestinationSampler):
    def __init__(self, *, sampler, rng):  # sampler.sample(rng)->Point in meters CRS
        self.sampler, self.rng = sampler, rng

    def sample_origin(self, _rng=None):
        return self.sampler.sample(self.rng)

    def sample_destination(self, _rng=None):
        return self.sampler.sample(self.rng)

    def snap(self, p, kind="vehicle"):
        return p, None


class NetworkODSampler(OriginDestinationSampler):
    def __init__(self, *, graph: NetworkGraph, rng_snap):
        self.G, self.rng = graph, rng_snap

    def sample_origin(self, _rng=None):
        return self.G.sample_point(self.rng)

    def sample_destination(self, _rng=None):
        return self.G.sample_point(self.rng)

    def snap(self, p, kind="vehicle"):
        n = self.G.nearest_node(p)
        q = self.G.node_point(n)
        L = math.hypot(q.x - p.x, q.y - p.y)
        return (q, None if L < 1e-6 else Segment(p, q, L, edge_id=None))
