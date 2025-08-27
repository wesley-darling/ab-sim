# ab_sim/app/controllers/idle.py
from ab_sim.app.controllers.demand import DemandHandler
from ab_sim.app.events import DriverAvailable, DriverLegArrive
from ab_sim.domain.entities.motion import MoveTask
from ab_sim.domain.state import WorldState
from ab_sim.policy.idle import IdlePolicy


class IdleHandler:
    def __init__(self, world: WorldState, policy: IdlePolicy, demand: DemandHandler, speeds):
        self.world = world
        self.policy = policy
        self.demand = demand
        self.speeds = speeds

    def on_trip_completed(self, ev):
        # driver has already been returned to idle by TripHandler
        # try to match queued demand immediately
        return self.demand.try_match_from_queue(now=ev.t)

    def on_driver_available(self, ev: DriverAvailable):
        # driver just became idle now → try to serve the queue
        return self.demand.try_match_from_queue(now=ev.t)

    def on_idle_timeout(self, ev):
        return []

    def maybe_reposition(self, now: float, driver_id: int, target: tuple[float, float]):
        d = self.world.drivers[driver_id]
        dur = self.speeds.duration_reposition(d, now)
        d.state = "to_reposition"
        d.current_move = MoveTask(start=d.loc, end=target, start_t=now, end_t=now + dur)
        return [
            DriverLegArrive(
                t=now + dur, driver_id=d.id, rider_id=None, kind="reposition", task_id=d.task_id
            )
        ]
