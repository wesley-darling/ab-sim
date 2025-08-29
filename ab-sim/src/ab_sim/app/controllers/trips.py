# ab_sim/app/controllers/trips.py


from ab_sim.app.events import (
    AlightingComplete,
    AlightingStarted,
    BoardingComplete,
    BoardingStarted,
    DriverAvailable,
    DriverCancel,
    DriverLegArrive,
    DriverWaitTimeout,
    PickupDeadline,
    RiderArrivePickup,
    RiderCancel,
    RiderRequeue,
    TripAssigned,
    TripBoarded,
    TripCompleted,
)
from ab_sim.domain.entities.driver import Driver
from ab_sim.domain.entities.motion import MovePlan, MoveTask
from ab_sim.domain.mechanics.mechanics_core import Mechanics
from ab_sim.domain.state import TripState, WorldState
from ab_sim.policy.matching import MatchingPolicy
from ab_sim.policy.pricing import PricingPolicy
from ab_sim.services.travel_time import TravelTimeService
from ab_sim.sim.clock import SimClock
from ab_sim.sim.metrics import Metrics


class TripHandler:
    def __init__(
        self,
        world: WorldState,
        matching: MatchingPolicy,
        travel_time: TravelTimeService,
        clock: SimClock,
        rng,
        pricing: PricingPolicy,
        metrics: Metrics,
        mechanics: Mechanics,
        max_driver_wait_s: float = 300.0,
        dwell=None,
    ):
        self.world = world
        self.travel_time = travel_time
        self.mechanics = mechanics
        self.clock = clock
        self.rng = rng
        self.max_driver_wait_s = max_driver_wait_s
        self.dwell = dwell
        self._rider_cancel_emitted: set[int] = set()  # rider_id → cancel already emitted
        self._driver_cancel_emitted: set[tuple[int, int]] = set()  # (driver_id, task_id)

    def _boarding_delay(self, rider_id, driver_id):
        return self.dwell.boarding_delay(rider_id, driver_id) if self.dwell else 0.0

    def _schedule_boarding(self, now: float, trip: TripState, d: Driver):
        # idempotency: if already started or boarded, do nothing
        if trip.boarding_started_t is not None or trip.boarded:
            return []
        delay = self._boarding_delay(trip.rider_id, d.id)  # 0 if dwell model is None
        start = BoardingStarted(t=now, rider_id=trip.rider_id, driver_id=d.id, task_id=d.task_id)
        done = BoardingComplete(
            t=now + delay, rider_id=trip.rider_id, driver_id=d.id, task_id=d.task_id
        )
        return [start, done]

    def _alighting_delay(self, rider_id, driver_id):
        return self.dwell.alighting_delay(rider_id, driver_id) if self.dwell else 0.0

    #!TODO Update below

    def estimate_pickup_eta(self, driver_pos, rider_pickup, now_s, dow, hour):
        return self.mechanics.eta(driver_pos, rider_pickup, now_s, dow=dow, hour=hour)

    def estimate_trip_eta(self, pickup, dropoff, now_s, dow, hour):
        return self.mechanics.eta(pickup, dropoff, now_s, dow=dow, hour=hour)

    def path_for_pricing(self, pickup, dropoff):
        path = self.mechanics.route(pickup, dropoff)
        return path.total_length_m, path

    # ------------ causal event handlers --------------

    def on_rider_cancel(self, ev: RiderCancel):
        trip = self.world.trips.get(ev.rider_id)
        if not trip or trip.boarded:
            return []  # nothing to do or too late to cancel

        d = self.world.drivers.get(trip.driver_id)
        # If rider was still QUEUED (no driver yet), do nothing here.
        # DemandHandler.on_rider_cancel will remove from queue and drop state.
        if d is None or trip.driver_id == -1:
            return []

        # ASSIGNED path: free driver immediately
        key = (d.id, d.task_id)
        self.world.active_task.pop(key, None)

        # If en-route to pickup, update position to the cancel time.
        if d.motion and d.state == "to_pickup":
            d.loc = d.pos_at(ev.t)

        # Invalidate any scheduled arrivals/wait timeouts for this task.
        d.task_id += 1

        # Free driver immediately.
        d.clear_motion()
        self.world.return_idle(d)

        # Remove trip/rider; DemandHandler will also remove from queue if needed (idempotent).
        self.world.trips.pop(ev.rider_id, None)
        self.world.riders.pop(ev.rider_id, None)

        # Let idle logic try to match someone else right now.
        return [DriverAvailable(t=ev.t, driver_id=d.id)]

    # Make deadline use the same path
    def on_pickup_deadline(self, ev: PickupDeadline):
        rid = ev.rider_id
        if rid in self._rider_cancel_emitted:
            return []
        self._rider_cancel_emitted.add(rid)
        return [RiderCancel(t=ev.t, rider_id=ev.rider_id, reason="pickup_deadline")]

    # Assignment → start pickup leg (+ guards)
    def on_trip_assigned(self, ev: TripAssigned):
        d = self.world.drivers.get(ev.driver_id)
        if ev.task_id != d.task_id:
            return []
        trip = self.world.trips.get(ev.rider_id)
        trip.driver_id = d.id

        self.world.active_task[(d.id, d.task_id)] = trip.rider_id

        d.state = "to_pickup"

        plan = self.mechanics.move_plan(d.loc, trip.origin, ev.t, **self.clock.dow_hour_at(ev.t))
        d.motion = plan

        return [
            DriverLegArrive(
                t=plan.end_t,
                driver_id=d.id,
                rider_id=trip.rider_id,
                kind="pickup",
                task_id=d.task_id,
            ),
            PickupDeadline(
                t=ev.t + self.world.riders.get(trip.rider_id).max_wait_s, rider_id=trip.rider_id
            ),
        ]

    # Driver arrives at pickup → maybe wait, maybe board
    def on_driver_leg_arrive(self, ev: DriverLegArrive):
        d = self.world.drivers.get(ev.driver_id)
        if ev.task_id != d.task_id:
            return []

        out: list[object] = []
        if ev.kind == "pickup":
            trip = self.world.trips.get(ev.rider_id)
            d.snap_to_plan_end()
            d.clear_motion()
            if trip is None:
                # trip canceled while en route; driver is already idle via _cancel_trip
                return [DriverAvailable(t=ev.t, driver_id=d.id)]

            d.state = "wait"
            trip.driver_at_pickup_t = ev.t
            if trip.rider_at_pickup_t is not None and not trip.boarded:
                return self._schedule_boarding(ev.t, trip, d)
            else:
                out.append(
                    DriverWaitTimeout(
                        t=ev.t + self.max_driver_wait_s, driver_id=d.id, task_id=d.task_id
                    )
                )
        elif ev.kind == "dropoff":
            trip = self.world.trips.get(ev.rider_id)
            d.snap_to_plan_end()
            d.clear_motion()
            delay = self._alighting_delay(trip.rider_id, d.id)
            return [
                AlightingStarted(t=ev.t, rider_id=trip.rider_id, driver_id=d.id, task_id=d.task_id),
                AlightingComplete(
                    t=ev.t + delay, rider_id=trip.rider_id, driver_id=d.id, task_id=d.task_id
                ),
            ]

        elif ev.kind == "reposition":
            d.snap_to_plan_end()
            d.clear_motion()
            self.world.return_idle(d)
        return out

    # Rider finishes walking to pickup → maybe board
    def on_rider_arrive_pickup(self, ev: RiderArrivePickup):
        trip = self.world.trips.get(ev.rider_id)
        if not trip or trip.boarded:
            return []
        trip.rider_at_pickup_t = ev.t
        d = self.world.drivers.get(trip.driver_id)
        if d.state == "wait" and not trip.boarded:
            return self._schedule_boarding(ev.t, trip, d)
        return []

    # Guards

    def on_driver_wait_timeout(self, ev: DriverWaitTimeout):
        key = (ev.driver_id, ev.task_id)
        if key in self._driver_cancel_emitted:
            return []
        self._driver_cancel_emitted.add(key)
        return [
            DriverCancel(t=ev.t, driver_id=ev.driver_id, task_id=ev.task_id, reason="wait_timeout")
        ]

    def on_driver_cancel(self, ev: DriverCancel):
        # driver abandons assignment; requeue rider

        rid = self.world.active_task.pop((ev.driver_id, ev.task_id), None)
        d = self.world.drivers.get(ev.driver_id)
        # Invalidate in-flight arrivals/waits
        d.task_id += 1
        d.clear_motion()
        self.world.return_idle(d)

        out = [DriverAvailable(t=ev.t, driver_id=d.id)]
        if rid is not None:
            # Clear the link on the trip; keep the trip so demand can requeue it
            trip = self.world.trips.get(rid)
            if trip:
                trip.driver_id = -1
            out.append(RiderRequeue(t=ev.t, rider_id=rid))

        return out

    def on_boarding_started(self, ev: BoardingStarted):
        d = self.world.drivers.get(ev.driver_id)
        if ev.task_id != d.task_id:  # preempted/stale
            return []
        trip = self.world.trips.get(ev.rider_id)
        if trip.boarding_started_t is None:
            trip.boarding_started_t = ev.t
        # (optional) emit metrics/logs here
        return []

    def on_boarding_complete(self, ev: BoardingComplete):
        d = self.world.drivers.get(ev.driver_id)
        if ev.task_id != d.task_id:
            return []
        trip = self.world.trips.get(ev.rider_id)
        if trip.boarded:
            return []
        trip.boarded = True
        now = ev.t

        d.state = "to_dropoff"
        if self.mechanics is not None:
            plan = self.mechanics.move_plan(d.loc, trip.dest, now, **self.clock.dow_hour_at(now))
            d.motion = plan
            t_arr = plan.end_t
        else:
            dur = self.travel_time.duration_to_dropoff(d, trip, now)
            d.motion = MovePlan(
                tasks=[MoveTask(start=d.loc, end=trip.dest, start_t=now, end_t=now + dur)],
                total_length_m=((trip.dest.x - d.loc.x) ** 2 + (trip.dest.y - d.loc.y) ** 2) ** 0.5,
                start_t=now,
                end_t=now + dur,
            )
            t_arr = now + dur
        return [
            TripBoarded(t=now, rider_id=trip.rider_id, driver_id=d.id),
            DriverLegArrive(
                t=t_arr, driver_id=d.id, rider_id=trip.rider_id, kind="dropoff", task_id=d.task_id
            ),
        ]

    # Helper
    def _board_and_depart(self, now: float, trip: TripState, d: Driver):
        trip.boarded = True
        # schedule dropoff leg

        d.state = "to_dropoff"

        plan = self.mechanics.move_plan(d.loc, trip.dest, now, **self.clock.dow_hour_at(now))
        d.motion = plan

        return [
            TripBoarded(t=now, rider_id=trip.rider_id, driver_id=d.id),
            DriverLegArrive(
                t=plan.end_t,
                driver_id=d.id,
                rider_id=trip.rider_id,
                kind="dropoff",
                task_id=d.task_id,
            ),
        ]

    def on_alighting_started(self, ev: AlightingStarted):
        d = self.world.drivers.get(ev.driver_id)
        if ev.task_id != d.task_id:
            return []
        trip = self.world.trips.get(ev.rider_id)
        if trip.alighting_started_t is None:
            trip.alighting_started_t = ev.t
        return []

    def on_alighting_complete(self, ev: AlightingComplete):
        d = self.world.drivers.get(ev.driver_id)
        if ev.task_id != d.task_id:
            return []
        trip = self.world.trips.get(ev.rider_id)
        # finalize & free driver
        d.state = "idle"
        self.world.return_idle(d)
        return [TripCompleted(t=ev.t, rider_id=trip.rider_id, driver_id=d.id)]
