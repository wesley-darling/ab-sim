# ab_sim/app/controllers/idle.py
from ab_sim.app.controllers.demand import DemandHandler
from ab_sim.app.events import DriverAvailable, DriverLegArrive
from ab_sim.domain.entities.geography import Point
from ab_sim.domain.mechanics.mechanics_core import Mechanics
from ab_sim.domain.state import WorldState
from ab_sim.policy.idle import IdlePolicy
from ab_sim.sim.clock import SimClock


class IdleHandler:
    def __init__(
        self,
        world: WorldState,
        policy: IdlePolicy,
        demand: DemandHandler,
        mechanics: Mechanics,
        clock: SimClock,
        speeds=None,
    ):
        self.world = world
        self.policy = policy
        self.demand = demand
        self.mechanics = mechanics
        self.speeds = speeds
        self.clock = clock

    def on_trip_completed(self, ev):
        # driver has already been returned to idle by TripHandler
        # try to match queued demand immediately
        return self.demand.try_match_from_queue(now=ev.t)

    def on_driver_available(self, ev: DriverAvailable):
        # driver just became idle now → try to serve the queue
        return self.demand.try_match_from_queue(now=ev.t)

    def on_idle_timeout(self, ev):
        return []

    def maybe_reposition(self, now: float, driver_id: int, target: Point):
        """
        Start (or replace) a reposition leg using the mechanics plan.
        - If replacing an existing reposition plan, bump task_id to invalidate its arrival.
        - Snaps the target to a valid vehicle location if the backend uses a network.
        """

        d = self.world.drivers.get(driver_id)

        # Preempt an in-flight reposition: invalidate any scheduled arrival
        if d.state == "to_reposition" and d.motion is not None:
            d.task_id += 1

        # Try snapping to target
        snapped_target, _ = self.mechanics.space.snap(target, kind="vehicle")

        # build plan
        plan = self.mechanics.move_plan(d.loc, snapped_target, now, **self.clock.dow_hour_at(now))

        if plan.end_t <= now:
            d.loc = snapped_target
            d.clear_motion()
            d.state = "idle"
            return []

        d.state = "to_reposition"
        d.motion = plan
        return [
            DriverLegArrive(
                t=plan.end_t, driver_id=d.id, rider_id=None, kind="reposition", task_id=d.task_id
            )
        ]
