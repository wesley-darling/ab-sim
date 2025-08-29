import math
import random

import pytest

from ab_sim.app.build import build
from ab_sim.app.protocols import Path, Point, Segment
from ab_sim.domain.entities.driver import Driver
from ab_sim.domain.entities.motion import MoveTask  # for compatibility checks
from ab_sim.domain.mechanics.mechanics_core import Mechanics
from ab_sim.domain.mechanics.mechanics_factory import (
    GlobalSpeedSampler,
    ManhattanRoutePlanner,
    MechanicsConfig,
    build_mechanics,
)
from ab_sim.domain.mechanics.mechanics_path_traversers import PiecewiseConstSpeedTraverser
from ab_sim.io.config import ScenarioConfig
from ab_sim.sim.rng import RNGRegistry

# ---------- Fixtures


@pytest.fixture
def mechanics_ideal_const10() -> Mechanics:
    cfg = MechanicsConfig(
        mode="idealized",
        metric="euclidean",
        zones=[(0.0, 0.0, 10_000.0, 10_000.0)],
        speed_kind="constant",
        base_mps=10.0,
        seed=42,
    )

    reg = RNGRegistry(master_seed=123, scenario="test", worker=0)
    return build_mechanics(cfg, rng_registry=reg)


@pytest.fixture
def mechanics_ideal_const8() -> Mechanics:
    cfg = MechanicsConfig(
        mode="idealized",
        metric="manhattan",
        zones=[(0.0, 0.0, 10_000.0, 10_000.0)],
        speed_kind="constant",
        base_mps=8.0,
        seed=99,
    )

    reg = RNGRegistry(master_seed=123, scenario="testB", worker=0)
    return build_mechanics(cfg, rng_registry=reg)


# ---------- Core Mechanics / Traverser tests


def test_euclidean_eta_equals_length_over_speed(mechanics_ideal_const10: Mechanics):
    m = mechanics_ideal_const10
    a, b, t0 = Point(100.0, 200.0), Point(1100.0, 200.0), 0.0
    L = math.hypot(b.x - a.x, b.y - a.y)
    eta = m.eta(a, b, t0)
    assert abs(eta - (L / 10.0)) < 1e-6


def test_move_plan_matches_eta_and_linear_pos(mechanics_ideal_const10: Mechanics):
    m = mechanics_ideal_const10
    a, b, t0 = Point(0.0, 0.0), Point(1_000.0, 0.0), 5.0  # 1000 m at 10 m/s
    plan = m.move_plan(a, b, t0)
    assert abs(plan.end_t - (t0 + 100.0)) < 1e-6
    mid = plan.pos(t0 + 50.0)  # halfway in time
    assert abs(mid.x - 500.0) < 1e-6 and abs(mid.y - 0.0) < 1e-9


def test_manhattan_router_two_segments_and_durations(mechanics_ideal_const8: Mechanics):
    # Swap router to Manhattan explicitly to check segmenting behavior if fixture isn't already
    m = mechanics_ideal_const8
    m.router = ManhattanRoutePlanner()

    a, b, t0 = Point(0.0, 0.0), Point(300.0, 400.0), 0.0
    path = m.route(a, b)
    assert len(path.segments) == 2
    assert abs(path.total_length_m - (300.0 + 400.0)) < 1e-9

    plan = m.mover.plan(path, t0, m.speed)
    assert len(plan.tasks) == 2
    # each leg duration at 8 m/s
    assert abs(plan.tasks[0].end_t - (t0 + 300.0 / 8.0)) < 1e-6
    assert abs(plan.end_t - (t0 + (300.0 + 400.0) / 8.0)) < 1e-6


def test_progress_events_monotone_and_ends_at_arrival(mechanics_ideal_const10: Mechanics):
    m = mechanics_ideal_const10
    a, b, t0 = Point(0.0, 0.0), Point(100.0, 0.0), 0.0  # 10 seconds at 10 m/s
    path = m.route(a, b)
    ticks = list(m.progress(a, b, t0, step_m=25.0))
    # expect ceil(100/25)=4 ticks, last ~t0+10
    assert len(ticks) == 4
    times = [t for t, _ in ticks]
    assert all(times[i] < times[i + 1] for i in range(len(times) - 1))
    assert abs(times[-1] - 10.0) < 1e-6
    # final point = end
    assert abs(ticks[-1][1].x - 100.0) < 1e-9 and abs(ticks[-1][1].y - 0.0) < 1e-9


# ---------- RNGRegistry integration


def test_rng_registry_makes_od_sampling_deterministic():
    cfg = MechanicsConfig(
        mode="idealized",
        metric="euclidean",
        zones=[(0.0, 0.0, 10_000.0, 10_000.0)],
        speed_kind="constant",
        base_mps=9.0,
        seed=7,
    )

    reg1 = RNGRegistry(master_seed=555, scenario="A", worker=0)
    reg2 = RNGRegistry(master_seed=555, scenario="A", worker=0)
    m1 = build_mechanics(cfg, rng_registry=reg1)
    m2 = build_mechanics(cfg, rng_registry=reg2)

    # draw a few origins/destinations — should be identical
    pts1 = [m1.space.sample_origin(None) for _ in range(5)]
    pts2 = [m2.space.sample_origin(None) for _ in range(5)]
    assert [(p.x, p.y) for p in pts1] == [(p.x, p.y) for p in pts2]


# ---------- MoveTask ↔ MovePlan compatibility on Driver


def test_driver_motion_plan_and_current_move_compat(mechanics_ideal_const10: Mechanics):
    m = mechanics_ideal_const10
    d = Driver(id=1, loc=Point(0.0, 0.0))
    plan = m.move_plan(d.loc, Point(1000.0, 0.0), 0.0)  # 100s at 10 m/s
    d.motion = plan

    # Back-compat: synthesized current_move envelope exists
    cm = d.current_move
    assert isinstance(cm, MoveTask)
    assert abs(cm.start_t - plan.start_t) < 1e-9
    assert abs(cm.end_t - plan.end_t) < 1e-9
    assert cm.start == plan.tasks[0].start and cm.end == plan.tasks[-1].end

    # Position lookup via plan
    p50 = d.pos_at(50.0)
    assert abs(p50.x - 500.0) < 1e-6 and abs(p50.y - 0.0) < 1e-9

    # Clear and ensure compatibility path is gone
    d.clear_motion()
    assert d.current_move is None


# ---------- Edge-aware speed: walking (edge_id=None) vs driving


class _WalkDriveSpeed(GlobalSpeedSampler):
    """Base=drive speed; return slower speed if edge_id is None (walking)."""

    def __init__(self, drive_mps=10.0, walk_mps=1.0):
        super().__init__(drive_mps)
        self.walk = walk_mps

    def speed_mps(self, t: float, *, edge_id=None, **_):
        return self.walk if edge_id is None else self.v


def test_plan_with_walking_and_driving_segments():
    mover = PiecewiseConstSpeedTraverser()
    speed = _WalkDriveSpeed(drive_mps=10.0, walk_mps=1.0)

    # Build a path: 100 m walk (edge_id=None) then 900 m drive (edge_id=7)
    a = Point(0.0, 0.0)
    mid = Point(0.0, 100.0)
    b = Point(0.0, 1000.0)
    segs = [
        Segment(a, mid, 100.0, edge_id=None),
        Segment(mid, b, 900.0, edge_id=7),
    ]
    path = Path(segs, total_length_m=1000.0)

    plan = mover.plan(path, t0=0.0, speed=speed)
    # Times: 100s walk + 90s drive
    assert abs(plan.end_t - 190.0) < 1e-6

    # Position after 50s: in walking segment at y=50
    p50 = plan.pos(50.0)
    assert abs(p50.y - 50.0) < 1e-6

    # Position after 150s: 50s into drive @10 m/s ⇒ +500 m beyond 100
    p150 = plan.pos(150.0)
    assert abs(p150.y - 600.0) < 1e-6


def test_mechanics_eta_constant_speed():
    cfg = ScenarioConfig.model_validate(
        {
            "name": "test",
            "run_id": "t-1",
            "sim": {"epoch": [2025, 1, 1, 0, 0, 0], "seed": 1, "duration": 3600},
            "mechanics": {
                "mode": "idealized",
                "metric": "euclidean",
                "speed_kind": "constant",
                "base_mps": 10.0,
            },
        }
    )
    app = build(cfg)
    mech = app["mechanics"]
    rng = random.Random(0)
    a = mech.space.sample_origin(rng)
    b = mech.space.sample_destination(rng)
    L = mech.router.distance_m(a, b)
    t = mech.eta(a, b, 0.0)
    assert abs(t - L / 10.0) < 1e-6
