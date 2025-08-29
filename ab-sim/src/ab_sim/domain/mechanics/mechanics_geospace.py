import math

from ab_sim.app.protocols import GeoSpace
from ab_sim.domain.entities.geography import NetworkGraph, Point, Segment


class IdealizedGeo(GeoSpace):
    def __init__(
        self,
        *,
        zones: list[tuple[float, float, float, float]],
        weights: list[float] | None = None,
        rng,
    ):
        self.zones, self.rng, self.weights = zones, rng, weights

    def _pick(self):
        if not self.weights:
            idx = self.rng.integers(0, len(self.zones))
        else:
            idx = self.rng.choice(len(self.zones), p=self.weights)
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
class EmpiricalGeo(GeoSpace):
    def __init__(self, *, sampler, rng):  # sampler.sample(rng)->Point in meters CRS
        self.sampler, self.rng = sampler, rng

    def sample_origin(self, _rng=None):
        return self.sampler.sample(self.rng)

    def sample_destination(self, _rng=None):
        return self.sampler.sample(self.rng)

    def snap(self, p, kind="vehicle"):
        return p, None


class NetworkGeo(GeoSpace):
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
