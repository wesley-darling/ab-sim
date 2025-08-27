# ab_sim/app/controllers/demand.py
from collections import deque

from ab_sim.app.events import (
    RiderArrivePickup,
    RiderCancel,
    RiderRequestPlaced,
    RiderRequeue,
    RiderTimeout,
    TripAssigned,
)
from ab_sim.domain.state import Rider, TripState, WorldState


class DemandHandler:
    def __init__(self, world: WorldState):
        self.world = world
        self.queue = deque()  # rider_ids in FIFO (replace with spatial/priority later)

    def on_rider_request(self, ev: RiderRequestPlaced):
        r = Rider(ev.rider_id, ev.pickup, ev.dropoff, ev.max_wait_s, ev.walk_s)
        self.world.riders[r.id] = r
        # Create trip record (no driver yet)
        self.world.trips[r.id] = TripState(
            rider_id=r.id, driver_id=-1, origin=r.pickup, dest=r.dropoff
        )
        out: list[object] = []
        # Model walking (or instantaneous presence)
        if r.walk_s > 0:
            out.append(RiderArrivePickup(t=ev.t + r.walk_s, rider_id=r.id))
        else:
            self.world.trips[r.id].rider_at_pickup_t = ev.t

        # Try to match immediately
        d = self.world.get_idle_driver()
        if d:
            d.task_id += 1
            self.world.trips[r.id].driver_id = d.id
            out.append(TripAssigned(t=ev.t, driver_id=d.id, rider_id=r.id, task_id=d.task_id))
        else:
            self.queue.append(r.id)
            out.append(RiderTimeout(t=ev.t + r.max_wait_s, rider_id=r.id))
        return out

    def on_rider_timeout(self, ev: RiderTimeout):
        # If still queued and not boarded → cancel request
        if ev.rider_id in self.queue:
            self.queue.remove(ev.rider_id)
            # drop trip state; rider not served
            self.world.trips.pop(ev.rider_id, None)
            self.world.riders.pop(ev.rider_id, None)
        return []

    def on_rider_cancel(self, ev: RiderCancel):
        # Remove from queue if present; drop trip & rider state
        if ev.rider_id in self.queue:
            try:
                self.queue.remove(ev.rider_id)
            except ValueError:
                pass
        self.world.trips.pop(ev.rider_id, None)
        self.world.riders.pop(ev.rider_id, None)
        return []

    def on_rider_requeue(self, ev: RiderRequeue):
        # Put rider back at the *front* so they get priority after a driver cancel
        if ev.rider_id in self.world.trips:
            self.queue.appendleft(ev.rider_id)
        return []

    def try_match_from_queue(self, now: float) -> list[object]:
        """Call this when a driver becomes idle to match the oldest queued rider."""
        out: list[object] = []
        if not self.queue:
            return out
        d = self.world.get_idle_driver()
        if not d:
            return out
        rid = self.queue.popleft()
        trip = self.world.trips[rid]
        trip.driver_id = d.id
        d.task_id += 1
        out.append(TripAssigned(t=now, driver_id=d.id, rider_id=rid, task_id=d.task_id))
        return out
