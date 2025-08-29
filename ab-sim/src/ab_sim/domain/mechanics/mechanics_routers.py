import math

from ab_sim.app.protocols import Router
from ab_sim.domain.entities.geography import NetworkGraph, Path, Point, Segment


class EuclidRouter(Router):
    def route(self, a, b):
        L = math.hypot(b.x - a.x, b.y - a.y)
        return Path([Segment(a, b, L)], L)

    def distance_m(self, a, b):
        return math.hypot(b.x - a.x, b.y - a.y)


class ManhattanRouter(Router):
    def route(self, a, b):
        dx, dy = b.x - a.x, b.y - a.y
        p1 = Point(b.x, a.y)
        segs = [Segment(a, p1, abs(dx)), Segment(p1, b, abs(dy))]
        return Path(segs, abs(dx) + abs(dy))

    def distance_m(self, a, b):
        return abs(b.x - a.x) + abs(b.y - a.y)


class NetworkRouter(Router):
    def __init__(self, graph: NetworkGraph, vmax_mps: float = 16.7):
        self.G, self.vmax = graph, vmax_mps

    def route(self, a, b):
        na, nb = self.G.nearest_node(a), self.G.nearest_node(b)
        nodes = self.G.astar(na, nb, self._h)
        segs, L = [], 0.0
        for u, v, data in self.G.iter_edges(nodes):
            L += data["length_m"]
            segs.append(
                Segment(
                    self.G.node_point(u),
                    self.G.node_point(v),
                    data["length_m"],
                    edge_id=data["edge_id"],
                )
            )
        return Path(segs, L)

    def distance_m(self, a, b):
        return self.route(a, b).total_length_m

    def _h(self, u, goal):
        pu, pg = self.G.node_point(u), self.G.node_point(goal)
        return math.hypot(pg.x - pu.x, pg.y - pu.y) / max(self.vmax, 0.1)
