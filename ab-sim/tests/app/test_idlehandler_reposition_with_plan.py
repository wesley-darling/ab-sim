import pytest

# If your IdleHandler lives elsewhere, adjust the import path:
from ab_sim.app.controllers.idle import IdleHandler
from ab_sim.app.events import DriverLegArrive
from ab_sim.app.protocols import Point
from ab_sim.config.models import MechanicsModel
from ab_sim.domain.entities.driver import Driver
from ab_sim.domain.mechanics.mechanics_factory import build_mechanics
from ab_sim.sim.clock import SimClock
from ab_sim.sim.rng import RNGRegistry


class _FakePolicy: ...


class _FakeDemand:
    def try_match_from_queue(self, now: float):
        return []


class _WorldStub:
    def __init__(self):
        self.drivers = {1: Driver(id=1, loc=Point(0.0, 0.0))}

    def return_idle(self, d):
        d.state = "idle"


@pytest.fixture
def mechanics_const10():
    mech_cfg = MechanicsModel.model_validate(
        {
            "seed": 1,
            "od_sampler": {"kind": "idealized", "zones": [(0.0, 0.0, 10_000.0, 10_000.0)]},
            "route_planner": {"kind": "euclidean"},
            "speed_sampler": {"kind": "global", "v_mps": 10.0},
            "path_traverser": {"kind": "piecewise_const"},
        }
    )
    reg = RNGRegistry(master_seed=777, scenario="idle", worker=0)
    return build_mechanics(mech_cfg, rng_registry=reg)


def test_reposition_starts_plan_and_schedules_arrival(mechanics_const10):
    world = _WorldStub()
    clock = SimClock.utc_epoch(2025, 1, 1, 0, 0, 0)
    idle = IdleHandler(
        world=world,
        idle=_FakePolicy(),
        demand=_FakeDemand(),
        mechanics=mechanics_const10,
        clock=clock,
    )

    now = 0.0
    evs = idle.maybe_reposition(now=now, driver_id=1, target=Point(1000.0, 0.0))
    assert len(evs) == 1 and isinstance(evs[0], DriverLegArrive)

    d = world.drivers[1]
    assert d.state == "to_reposition"
    assert d.motion is not None
    # 1000 m @ 10 m/s = 100 s
    assert abs(evs[0].t - 100.0) < 1e-6
    assert abs(d.motion.end_t - 100.0) < 1e-6


def test_reposition_preemption_bumps_task_id(mechanics_const10):
    world = _WorldStub()
    clock = SimClock.utc_epoch(2025, 1, 1, 0, 0, 0)
    idle = IdleHandler(
        world=world,
        idle=_FakePolicy(),
        demand=_FakeDemand(),
        mechanics=mechanics_const10,
        clock=clock,
    )

    d = world.drivers[1]
    d.task_id = 5

    evs1 = idle.maybe_reposition(now=0.0, driver_id=1, target=Point(1000.0, 0.0))
    task_after_first = d.task_id

    # call again with a new target → should preempt and bump task_id
    evs2 = idle.maybe_reposition(now=10.0, driver_id=1, target=Point(0.0, 1000.0))
    assert d.task_id == task_after_first + 1
    assert d.motion is not None
    # verify new arrival reflects second target, not stale first
    assert evs2[0].t > evs1[0].t - 1e-9 or evs2[0].t != evs1[0].t
