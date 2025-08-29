# ab_sim/app/build.py
from dataclasses import dataclass

from ab_sim.app.controllers.demand import DemandHandler
from ab_sim.app.controllers.fleet import FleetHandler
from ab_sim.app.controllers.idle import IdleHandler
from ab_sim.app.controllers.trips import TripHandler
from ab_sim.app.events import EndOfDay
from ab_sim.app.wiring import wire
from ab_sim.domain.mechanics.mechanics_core import Mechanics
from ab_sim.domain.mechanics.mechanics_factory import build_mechanics

# domain/policy/handlers you already have or will add
from ab_sim.domain.state import WorldState
from ab_sim.io.config import ScenarioConfig
from ab_sim.io.kernel_logging import KernelLogging  # JSON logs
from ab_sim.io.recorder import JsonlSink, Recorder
from ab_sim.policy.assign import NearestAssign
from ab_sim.policy.travel_time import FixedSpeedModel
from ab_sim.sim.clock import DAY, SimClock
from ab_sim.sim.hooks import NoopHooks
from ab_sim.sim.kernel import Kernel
from ab_sim.sim.rng import RNGRegistry


@dataclass
class App:
    kernel: Kernel
    clock: SimClock
    rng: RNGRegistry
    world: WorldState
    trips: TripHandler
    idle: IdleHandler
    demand: DemandHandler
    mechanics: Mechanics
    fleet: FleetHandler


def build(cfg: ScenarioConfig, *, worker: int = 0, use_logging: bool = True) -> App:
    # 1) Clock & RNG
    clock = SimClock.utc_epoch(*cfg.sim.epoch)  # e.g., [2024, 1, 1, 0, 0, 0]
    rng_registry = RNGRegistry(cfg.sim.seed, scenario=cfg.name, worker=worker)

    # 2) Kernel (with hooks)

    # Recorder for analytics
    sinks = [JsonlSink()]  # add AsyncSink(JsonlSink()) if you want non-blocking writes
    recorder = Recorder(*sinks)

    hooks = (
        KernelLogging(
            run_id=cfg.run_id,
            recorder=recorder,
            clock=clock,
            level=cfg.log.level,
            debug=cfg.log.debug,
            sample_every=cfg.log.sample_every,
        )
        if use_logging
        else NoopHooks()
    )
    kernel = Kernel(hooks=hooks)

    # 3) World & policies
    world = WorldState(capacity=cfg.world.capacity, geo=cfg.world.geo)
    assign = NearestAssign(world=world)  # deterministic, can still dip into rng.stream("policy")
    speeds = FixedSpeedModel(pickup_s=cfg.speeds.pickup_mps, dropoff_s=cfg.speeds.drop_mps)
    mechanics = build_mechanics(cfg.mechanics, rng_registry=rng_registry)
    # 4) Handlers (inject deps explicitly)
    demand = DemandHandler(world=world, mechanics=mechanics, rng=rng_registry.stream("demand"))
    trips = TripHandler(
        world=world,
        matcher=assign,
        speeds=speeds,
        clock=clock,
        rng=rng_registry.stream("policy"),
        pricing=None,
        metrics=None,
        mechanics=mechanics,
    )
    idle = IdleHandler(
        world=world, policy=cfg.idle, demand=demand, speeds=speeds, mechanics=mechanics
    )

    fleet = FleetHandler(world=world, rng=rng_registry.stream("supply"), mechanics=mechanics)
    # 5) Wiring

    wire(kernel, trips=trips, idle=idle, demand=demand, fleet=fleet)

    # 6) Seed housekeeping timers (e.g., end-of-day rollup)
    t0 = 0.0
    kernel.schedule(EndOfDay(t=t0 + DAY, day_index=0, task_id=0))

    # 7) (Optional) seed demand arrivals here, or in a DemandSeeder that pushes RiderArrival events
    # DemandSeeder(clock, rng, inputs).seed(kernel, start=t0, end=cfg.sim.duration)

    return App(kernel, clock, rng_registry, world, trips, idle, demand, mechanics, fleet)
