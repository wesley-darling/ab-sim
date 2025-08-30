# ab_sim/app/build.py
from collections.abc import Mapping
from dataclasses import dataclass

from ab_sim.app.controllers.demand import DemandHandler
from ab_sim.app.controllers.fleet import FleetHandler
from ab_sim.app.controllers.idle import IdleHandler
from ab_sim.app.controllers.trips import TripHandler
from ab_sim.app.events import EndOfDay
from ab_sim.app.wiring import wire
from ab_sim.config.models import ScenarioModel
from ab_sim.domain.mechanics.mechanics_core import Mechanics
from ab_sim.domain.mechanics.mechanics_factory import build_mechanics

# domain/policy/handlers you already have or will add
from ab_sim.domain.state import WorldState
from ab_sim.io.kernel_logging import KernelLogging  # JSON logs
from ab_sim.io.recorder import JsonlSink, Recorder
from ab_sim.runtime.policy_factory import (
    make_dwell_policy,
    make_idle_policy,
    make_matching_policy,
    make_pricing_policy,
)
from ab_sim.runtime.services_factory import make_travel_time
from ab_sim.services.travel_time import TravelTimeService
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


def build(cfg: ScenarioModel | Mapping, *, worker: int = 0, use_logging: bool = True) -> App:
    # 0) Validate config
    model = cfg if isinstance(cfg, ScenarioModel) else ScenarioModel.model_validate(cfg)

    # 1) Clock & RNG
    clock = SimClock.utc_epoch(*model.sim.epoch)  # e.g., [2024, 1, 1, 0, 0, 0]
    rng_registry = RNGRegistry(model.sim.seed, scenario=model.name, worker=worker)

    # 2) Kernel (with hooks)

    # Recorder for analytics
    sinks = [JsonlSink()]  # add AsyncSink(JsonlSink()) if you want non-blocking writes
    recorder = Recorder(*sinks)

    hooks = (
        KernelLogging(
            run_id=model.run_id,
            recorder=recorder,
            clock=clock,
            level=model.log.level,
            debug=model.log.debug,
            sample_every=model.log.sample_every,
        )
        if use_logging
        else NoopHooks()
    )
    kernel = Kernel(hooks=hooks)

    # 3) World & policies
    world = WorldState(capacity=model.world.capacity, geo=model.world.geo)
    matching_policy = make_matching_policy(model.matching, world=world)
    dwell_policy = make_dwell_policy(model.dwell, rng_registry=rng_registry)
    idle_policy = make_idle_policy(model.idle)
    pricing_policy = make_pricing_policy(model.pricing)

    mechanics = build_mechanics(model.mechanics, rng_registry=rng_registry)

    # 3.5) Services
    travel_time: TravelTimeService = make_travel_time(model.travel_time, mechanics=mechanics)

    # 4) Handlers (inject deps explicitly)
    demand = DemandHandler(world=world, mechanics=mechanics, rng=rng_registry.stream("demand"))

    idle = IdleHandler(
        world=world,
        idle=idle_policy,
        demand=demand,
        travel_time=travel_time,
        mechanics=mechanics,
        clock=clock,
    )

    fleet = FleetHandler(world=world, rng=rng_registry.stream("supply"), mechanics=mechanics)

    trips = TripHandler(
        world=world,
        matching=matching_policy,
        travel_time=travel_time,
        clock=clock,
        rng=rng_registry.stream("policy"),
        pricing=pricing_policy,
        metrics=None,
        mechanics=mechanics,
    )

    # 5) Wiring

    wire(kernel, trips=trips, idle=idle, demand=demand, fleet=fleet)

    # 6) Seed housekeeping timers (e.g., end-of-day rollup)
    t0 = 0.0
    kernel.schedule(EndOfDay(t=t0 + DAY, day_index=0, task_id=0))

    # 7) (Optional) seed demand arrivals here, or in a DemandSeeder that pushes RiderArrival events
    # DemandSeeder(clock, rng, inputs).seed(kernel, start=t0, end=cfg.sim.duration)

    return App(kernel, clock, rng_registry, world, trips, idle, demand, mechanics, fleet)
