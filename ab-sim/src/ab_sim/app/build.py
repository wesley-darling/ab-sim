# ab_sim/app/build.py
from dataclasses import dataclass

from ab_sim.app.controllers.demand import DemandHandler
from ab_sim.app.controllers.idle import IdleHandler
from ab_sim.app.controllers.trips import TripHandler
from ab_sim.app.events import EndOfDay

# domain/policy/handlers you already have or will add
from ab_sim.domain.state import WorldState
from ab_sim.io.kernel_logging import KernelLogging  # JSON logs
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


def build(cfg, *, worker: int = 0, use_logging: bool = True) -> App:
    # 1) Clock & RNG
    clock = SimClock.utc_epoch(*cfg.sim.epoch)  # e.g., [2024, 1, 1, 0, 0, 0]
    rng = RNGRegistry(cfg.sim.seed, scenario=cfg.name, worker=worker)

    # 2) Kernel (with hooks)
    hooks = (
        KernelLogging(
            run_id=cfg.run_id,
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

    # 4) Handlers (inject deps explicitly)
    demand = DemandHandler(world=world)
    trips = TripHandler(
        world=world, matcher=assign, speeds=speeds, clock=clock, rng=rng, pricing=None, metrics=None
    )
    idle = IdleHandler(world=world, policy=cfg.idle, demand=demand, speeds=speeds)

    # 5) Wiring
    from ab_sim.app.wiring import wire

    wire(kernel, trips=trips, idle=idle, demand=demand)

    # 6) Seed housekeeping timers (e.g., end-of-day rollup)
    t0 = 0.0
    kernel.schedule(EndOfDay(t=t0 + DAY, day_index=0, task_id=0))

    # 7) (Optional) seed demand arrivals here, or in a DemandSeeder that pushes RiderArrival events
    # DemandSeeder(clock, rng, inputs).seed(kernel, start=t0, end=cfg.sim.duration)

    return App(kernel, clock, rng, world, trips, idle)
