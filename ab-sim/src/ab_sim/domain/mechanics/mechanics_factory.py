# ab_sim/domain/mechanics/mechanics_factory.py

from ab_sim.config.models import MechanicsModel
from ab_sim.domain.mechanics.mechanics_core import Mechanics
from ab_sim.runtime.registries import make_od, make_path_traverser, make_route_planner, make_speed
from ab_sim.sim.rng import RNGRegistry


# ---- light import hooks (#!stubs)
def load_polygon_sampler(path: str):
    from ab_sim.io.inputs import PolygonSampler

    return PolygonSampler.from_shapefile(path)


def load_graph(path: str):
    from ab_sim.io.inputs import load_network_graph  # your preprocessor output

    return load_network_graph(path)


def build_mechanics(cfg: MechanicsModel, rng_registry: RNGRegistry, *, graphs=None) -> Mechanics:
    rng_od = rng_registry.stream("od")
    rng_speed_sampler = rng_registry.stream("speed_sampling")
    # rng_snap = rng_registry.stream("snap")

    speed_sampler = make_speed(cfg.speed_sampler, deps={"rng": rng_speed_sampler})
    od_sampler = make_od(cfg.od_sampler, deps={"rng": rng_od})
    route_planner = make_route_planner(cfg.route_planner)
    path_traverser = make_path_traverser(cfg.path_traverser)

    return Mechanics(
        od_sampler=od_sampler,
        route_planner=route_planner,
        speed_sampler=speed_sampler,
        path_traverser=path_traverser,
    )
