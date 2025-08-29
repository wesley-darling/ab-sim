# runtime/registries.py
from collections.abc import Callable
from typing import Any

from ab_sim.app.protocols import (
    ODSampleFn,
    OriginDestinationSampler,
    PathTraverser,
    RoutePlanner,
    SpeedSampler,
)
from ab_sim.config.models import (
    GraphByName,
    GraphByPath,
    GraphRef,
    ODSamplerEmpiricalModel,
    ODSamplerIdealizedModel,
    ODSamplerNetworkModel,
    ODUnion,
    PathTraverserPiecewiseConstModel,
    PathTraverserUnion,
    RoutePlannerEuclideanModel,
    RoutePlannerManhattanModel,
    RoutePlannerNetworkModel,
    RoutePlannerUnion,
    SpeedSamplerConstantModel,
    SpeedSamplerDistributionModel,
    SpeedSamplerEdgeAwareModel,
    SpeedSamplerGlobalModel,
    SpeedSamplerUnion,
)
from ab_sim.domain.mechanics.mechanics_od_samplers import (
    EmpiricalODSampler,
    IdealizedODSampler,
    NetworkODSampler,
)
from ab_sim.domain.mechanics.mechanics_path_traversers import PiecewiseConstSpeedTraverser
from ab_sim.domain.mechanics.mechanics_route_planners import (
    EuclidRoutePlanner,
    ManhattanRoutePlanner,
    NetworkRoutePlanner,
)
from ab_sim.domain.mechanics.mechanics_speed_samplers import (
    ConstantSpeedSampler,
    DistDrawSpeedSampler,
    EdgeAwareSpeedSampler,
    GlobalSpeedSampler,
)
from ab_sim.runtime.resources import load_graph_from_path

SpeedFactory = Callable[[SpeedSamplerUnion, Any], SpeedSampler]
ODFactory = Callable[[ODUnion, dict], OriginDestinationSampler]
RoutePlannerFactory = Callable[[RoutePlannerUnion, dict], RoutePlanner]
PathTraverserFactory = Callable[[PathTraverserUnion, dict], PathTraverser]

_speed_registry: dict[str, SpeedFactory] = {}
_od_registry: dict[str, ODFactory] = {}
_sampler_fn_registry: dict[str, ODSampleFn] = {}
_route_planner_registry: dict[str, RoutePlannerFactory] = {}
_path_traverser_registry: dict[str, PathTraverserFactory] = {}


# ------------------- Speed sampler registries ---------------------------


def register_speed(kind: str):
    def deco(fn: SpeedFactory):
        _speed_registry[kind] = fn
        return fn

    return deco


def make_speed(cfg: SpeedSamplerUnion, *, rng) -> SpeedSampler:
    try:
        return _speed_registry[cfg.kind](cfg, {"rng": rng})
    except KeyError:
        raise ValueError(f"Unknown speed kind {cfg.kind!r}")


@register_speed("global")
def _make_global(cfg: SpeedSamplerGlobalModel, deps):
    return GlobalSpeedSampler(cfg.v_mps)


@register_speed("constant")
def _make_const(cfg: SpeedSamplerConstantModel, deps):
    return ConstantSpeedSampler(cfg.v_mps)


@register_speed("distribution")
def _make_dist(cfg: SpeedSamplerDistributionModel, deps):
    return DistDrawSpeedSampler(deps["rng"], cfg.dist, cfg.params, cfg.fallback_mps)


@register_speed("edge_aware")
def _make_edge(cfg: SpeedSamplerEdgeAwareModel, deps):
    return EdgeAwareSpeedSampler(cfg.base_mps, cfg.tfac, cfg.efac)


# ----- Origin/Destination Samplers --------------------------


def register_od(kind: str):
    def deco(fn):
        _od_registry[kind] = fn
        return fn

    return deco


def register_od_sampler_fn(name: str):
    def deco(fn: ODSampleFn):
        _sampler_fn_registry[name] = fn
        return fn

    return deco


def resolve_graph(ref: GraphRef | None, *, deps: dict):
    """
    deps can include:
      - 'graphs': dict[str, Any]  # prebuilt graphs by name
      - 'graph': Any              # a direct fallback/default
    """
    if ref is None:
        if "graph" in deps:
            return deps["graph"]
        raise ValueError("No graph provided")
    if isinstance(ref, GraphByName):
        return deps["graphs"][ref.name]  # raises KeyError if missing
    if isinstance(ref, GraphByPath):
        g = load_graph_from_path(ref.file, ref.fmt)
        if ref.must_exist and g is None:
            raise FileNotFoundError(ref.file)
        return g
    raise TypeError(ref)


def make_od(cfg: ODUnion, *, deps: dict) -> OriginDestinationSampler:
    return _od_registry[cfg.kind](cfg, deps)


@register_od("idealized")
def _make_uniform(cfg: ODSamplerIdealizedModel, deps):
    rng = deps["rng"]
    return IdealizedODSampler(zones=cfg.zones, weights=cfg.weights, rng=rng)


@register_od("empirical")
def _make_empirical(cfg: ODSamplerEmpiricalModel, deps):
    rng = deps["rng"]
    sampler = _sampler_fn_registry[cfg.sampler_name]
    return EmpiricalODSampler(sampler=sampler, rng=rng)


@register_od("network")
def _make_network(cfg: ODSamplerNetworkModel, deps):
    rng = deps["rng"]
    g = resolve_graph(cfg.graph, deps=deps)
    return NetworkODSampler(graph=g, rng=rng)


# --------------------- Route Planners  ---------------------
def register_route_planner(kind: str):
    def deco(fn):
        _route_planner_registry[kind] = fn
        return fn

    return deco


def make_route_planner(cfg: RoutePlannerUnion, *, deps: dict) -> RoutePlanner:
    return _route_planner_registry[cfg.kind](cfg, deps)


@register_route_planner("euclidean")
def _make_euclidean(cfg: RoutePlannerEuclideanModel, deps):
    return EuclidRoutePlanner()


@register_route_planner("manhattan")
def _make_manhattan(cfg: RoutePlannerManhattanModel, deps):
    return ManhattanRoutePlanner()


@register_route_planner("network")
def _make_route_planner_network(cfg: RoutePlannerNetworkModel, deps):
    g = resolve_graph(cfg.graph, deps=deps)
    return NetworkRoutePlanner(graph=g, vmax_mps=cfg.vmax_mps)


# ---------------------- Path Traversers ----------------------------


def register_path_traverser(kind: str):
    def deco(fn):
        _path_traverser_registry[kind] = fn
        return fn

    return deco


def make_path_traverser(cfg: RoutePlannerUnion, *, deps: dict) -> PathTraverser:
    return _path_traverser_registry[cfg.kind](cfg, deps)


@register_path_traverser("piecewise_const")
def _make_piecewise_const(cfg: PathTraverserPiecewiseConstModel, deps):
    return PiecewiseConstSpeedTraverser()
