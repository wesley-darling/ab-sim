# ab_sim/domain/mechanics/mechanics_factory.py
from dataclasses import dataclass

from ab_sim.domain.mechanics.mechanics_core import Mechanics
from ab_sim.domain.mechanics.mechanics_geospace import EmpiricalGeo, IdealizedGeo, NetworkGeo
from ab_sim.domain.mechanics.mechanics_movers import PiecewiseConstSpeedMover
from ab_sim.domain.mechanics.mechanics_routers import EuclidRouter, ManhattanRouter, NetworkRouter
from ab_sim.domain.mechanics.mechanics_speeds import DistDrawSpeed, EdgeAwareSpeed, GlobalSpeed
from ab_sim.sim.rng import RNGRegistry


# ---- light import hooks (#!stubs)
def load_polygon_sampler(path: str):
    from ab_sim.io.inputs import PolygonSampler

    return PolygonSampler.from_shapefile(path)


def load_graph(path: str):
    from ab_sim.io.inputs import load_network_graph  # your preprocessor output

    return load_network_graph(path)


@dataclass
class MechanicsConfig:
    mode: str = "idealized"  # "idealized"|"empirical"|"network"
    seed: int = 123
    # idealized
    metric: str = "euclidean"  # or "manhattan"
    zones: list[tuple[float, float, float, float]] = ((0, 0, 10_000, 10_000),)
    zone_weights: list[float] | None = None
    # empirical
    shapefile_path: str | None = None
    # network
    graph_pickle_path: str | None = None
    # speeds
    speed_kind: str = "constant"  # "constant"|"distribution"|"dow_hour"
    base_mps: float = 8.94
    dist_name: str | None = None
    dist_params: dict[str, float] = None
    dow_hour_multiplier: dict[str, float] = None
    edge_factor: dict[int, float] = None


def build_mechanics(cfg: MechanicsConfig, rng_registry: RNGRegistry) -> Mechanics:
    rng_od = rng_registry.stream("od")
    rng_speed = rng_registry.stream("speed")
    rng_snap = rng_registry.stream("snap")

    # Speed
    if cfg.speed_kind == "constant":
        speed = GlobalSpeed(cfg.base_mps)
    elif cfg.speed_kind == "distribution":
        speed = DistDrawSpeed(
            rng_speed, cfg.dist_name or "lognormal", cfg.dist_params or {}, cfg.base_mps
        )
    else:
        speed = EdgeAwareSpeed(cfg.base_mps, cfg.dow_hour_multiplier or {}, cfg.edge_factor or {})

    # Geo & Router
    if cfg.mode == "idealized":
        space = IdealizedGeo(zones=list(cfg.zones), rng=rng_od, weights=cfg.zone_weights)
        router = EuclidRouter() if cfg.metric == "euclidean" else ManhattanRouter()

    elif cfg.mode == "empirical":
        sampler = load_polygon_sampler(
            cfg.shapefile_path
        )  # <-- implement in your io/inputs.py if you like
        space = EmpiricalGeo(sampler=sampler, rng=rng_od)
        router = EuclidRouter() if cfg.metric == "euclidean" else ManhattanRouter()

    elif cfg.mode == "network":
        graph = load_graph(
            cfg.graph_pickle_path
        )  # <-- implement once; include KD-tree for snapping
        space = NetworkGeo(graph=graph, rng=rng_snap)
        router = NetworkRouter(graph)
    else:
        raise ValueError(f"Unknown mechanics.mode={cfg.mode}")

    mover = PiecewiseConstSpeedMover()
    return Mechanics(space=space, router=router, speed=speed, mover=mover)
