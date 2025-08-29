from dataclasses import dataclass


# Core geometry types used by mechanics
@dataclass(frozen=True)
class Point:
    x: float  # meters in projected CRS
    y: float


@dataclass(frozen=True)
class Segment:
    start: Point
    end: Point
    length_m: float
    edge_id: int | None = None  # None => off-network (e.g., walking)


@dataclass
class Path:
    segments: list[Segment]
    total_length_m: float


class NetworkGraph:
    """Wrapper over OSM preprocessor."""

    pass
    # implement nearest_node(Point)->int, node_point(int)->Point, astar(u,v,h)->List[int], iter_edges(nodes)->yield (u,v,data)
