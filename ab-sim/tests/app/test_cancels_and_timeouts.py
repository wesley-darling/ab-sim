from ab_sim.app.controllers.demand import DemandHandler
from ab_sim.app.controllers.fleet import FleetHandler
from ab_sim.app.controllers.idle import IdleHandler, IdlePolicy

# Controllers
from ab_sim.app.controllers.trips import FixedSpeedModel, TripHandler

# Events
from ab_sim.app.events import (
    DriverStartShift,
    DriverWaitTimeout,
    PickupDeadline,
    RiderCancel,
    RiderRequestPlaced,
)
from ab_sim.app.protocols import Point
from ab_sim.app.wiring import wire
from ab_sim.domain.mechanics.mechanics_factory import build_mechanics
from ab_sim.domain.state import Driver, WorldState
from ab_sim.io.config import MechanicsConfig
from ab_sim.policy.matching import NearestAssign
from ab_sim.policy.pricing import PricingPolicy
from ab_sim.sim.clock import SimClock
from ab_sim.sim.hooks import NoopHooks
from ab_sim.sim.kernel import Kernel
from ab_sim.sim.metrics import Metrics
from ab_sim.sim.rng import RNGRegistry

# ---------- Trace helper ----------


class Trace(NoopHooks):
    def __init__(self):
        self.events = []

    def dispatch_start(self, ev, *, seq, qsize, handlers):
        rec = {
            "t": ev.t,
            "name": type(ev).__name__,
        }
        # Helpful fields if present
        for f in ("kind", "rider_id", "driver_id", "task_id", "reason"):
            if hasattr(ev, f):
                rec[f] = getattr(ev, f)
        self.events.append(rec)


def times_of(h, name):
    return [e["t"] for e in h.events if e["name"] == name]


def kinds_of(h, name):
    return [e.get("kind") for e in h.events if e["name"] == name]


def times_of_rider(h, name, rid):
    return [e["t"] for e in h.events if e["name"] == name and e.get("rider_id") == rid]


def kinds_of_rider(h, name, rid):
    return [e.get("kind") for e in h.events if e["name"] == name and e.get("rider_id") == rid]


# ---------- Tiny dwell for tests ----------


class ZeroDwell:
    def boarding_delay(self, rider_id: int, driver_id: int) -> float:
        return 0.0

    def alighting_delay(self, rider_id: int, driver_id: int) -> float:
        return 0.0


# ---------- Builders ----------


def build_app(*, add_driver=True, pickup_s=10.0, dropoff_s=20.0, max_driver_wait_s=3.0, dwell=None):
    world = WorldState()
    if add_driver:
        world.add_driver(Driver(id=1, loc=Point(0.0, 0.0)))

    speeds = FixedSpeedModel(pickup_s=pickup_s, dropoff_s=dropoff_s)
    dwell = dwell if dwell is not None else ZeroDwell()
    speeds = FixedSpeedModel(pickup_s=pickup_s, dropoff_s=dropoff_s)
    mech_cfg = MechanicsConfig(
        mode="idealized",
        metric="euclidean",
        speed_kind="constant",
        base_mps=max(pickup_s, dropoff_s),
    )
    rng_registry = RNGRegistry(master_seed=0, scenario="tests", worker=0)
    mechanics = build_mechanics(mech_cfg, rng_registry=rng_registry)
    clock = SimClock.utc_epoch(2025, 1, 1, 0, 0, 0)
    trips = TripHandler(
        world=world,
        speeds=speeds,
        mechanics=mechanics,
        max_driver_wait_s=max_driver_wait_s,
        dwell=dwell,
        matcher=NearestAssign(world),
        clock=clock,
        rng=rng_registry,
        pricing=PricingPolicy(0),
        metrics=Metrics("test"),
    )
    demand = DemandHandler(world=world, rng=rng_registry, mechanics=mechanics)
    idle = IdleHandler(
        world=world,
        policy=IdlePolicy(dwell_s=0.0),
        demand=demand,
        speeds=speeds,
        mechanics=mechanics,
        clock=clock,
    )
    fleet = FleetHandler(world=world, rng=rng_registry, mechanics=mechanics)

    hooks = Trace()
    k = Kernel(hooks=hooks)

    wire(k, trips=trips, demand=demand, idle=idle, fleet=fleet)
    return k, hooks, world


# ========================= TESTS =========================


def test_user_cancel_while_en_route_frees_driver_immediately_and_rematches():
    """
    r1 at t=0 assigned; driver pickup leg = 10s.
    r2 at t=1 queued (driver busy).
    User cancels r1 at t=3 → driver becomes available immediately (t=3),
    emits DriverAvailable, and r2 is assigned at t=3.
    The stale pickup arrival for r1 at t=10 must not cause boarding.
    """
    k, h, world = build_app(pickup_s=10, dropoff_s=20, max_driver_wait_s=300, dwell=ZeroDwell())

    # r1 request → immediate assign; pickup arrival would be at t=10
    k.schedule(
        RiderRequestPlaced(
            t=0.0, rider_id=1, pickup=(0, 0), dropoff=(1, 1), max_wait_s=999, walk_s=0
        )
    )
    # r2 request queued at t=1
    k.schedule(
        RiderRequestPlaced(
            t=1.0, rider_id=2, pickup=(0, 0), dropoff=(2, 2), max_wait_s=999, walk_s=0
        )
    )
    # user cancels r1 at t=3
    k.schedule(RiderCancel(t=3.0, rider_id=1, reason="user"))
    k.run(until=100.0)

    # r2 must be assigned at the cancel time
    assert times_of_rider(h, "TripAssigned", 2) == [3.0]
    # stale pickup arrival for r1 fires at t=10, but must not board
    assert times_of_rider(h, "TripBoarded", 1) == []
    # driver proceeds to serve r2 normally
    assert kinds_of_rider(h, "DriverLegArrive", 2) == ["pickup", "dropoff"]
    assert times_of_rider(h, "DriverLegArrive", 2) == [13.0, 33.0]  # pickup_s=10 from t=3; then +20


def test_pickup_deadline_translates_to_rider_cancel_and_immediate_rematch():
    """
    r1 at t=0 assigned; driver en route (pickup 10s). r2 at t=5 queued.
    r1 has max_wait = 8s and is walking long → PickupDeadline at t=8 fires.
    That MUST translate to RiderCancel(reason="pickup_deadline"), free driver at t=8,
    emit DriverAvailable, and assign r2 at t=8.
    """
    k, h, world = build_app(pickup_s=10, dropoff_s=20, max_driver_wait_s=300, dwell=ZeroDwell())

    k.schedule(
        RiderRequestPlaced(
            t=0.0, rider_id=10, pickup=(0, 0), dropoff=(1, 1), max_wait_s=8, walk_s=999
        )
    )
    k.schedule(
        RiderRequestPlaced(
            t=5.0, rider_id=20, pickup=(0, 0), dropoff=(2, 2), max_wait_s=999, walk_s=0
        )
    )
    # Explicitly schedule the deadline (if your Demand/Trip code didn't already)
    k.schedule(PickupDeadline(t=8.0, rider_id=10))
    k.run(until=100.0)

    # Next assignment must occur at t=8 for rider 20
    assert times_of_rider(h, "TripAssigned", 20) == [8.0]
    # For observability, we expect to have seen a RiderCancel(reason="pickup_deadline")
    # (If you don't store reason on the event, just check the presence of RiderCancel at 8.0)
    rc_times = [e["t"] for e in h.events if e["name"] == "RiderCancel" and e.get("rider_id") == 10]
    assert rc_times == [8.0]


def test_driver_wait_timeout_translates_to_driver_cancel_and_requeue_rider():
    """
    r1 at t=0; driver arrives pickup at t=10, but rider isn't there (walk 999s).
    Set max_driver_wait_s=3 → DriverWaitTimeout at t=13 triggers DriverCancel(reason="wait_timeout").
    Driver becomes available and should be assigned to r2 (queued at t=11) at t=13.
    r1 remains queued; later they will be canceled by their own deadline or matched if a driver appears.
    """
    k, h, world = build_app(pickup_s=10, dropoff_s=20, max_driver_wait_s=3, dwell=ZeroDwell())

    k.schedule(
        RiderRequestPlaced(
            t=0.0, rider_id=100, pickup=(0, 0), dropoff=(1, 1), max_wait_s=999, walk_s=999
        )
    )
    # Another rider shows up while driver is waiting
    k.schedule(
        RiderRequestPlaced(
            t=11.0, rider_id=200, pickup=(0, 0), dropoff=(2, 2), max_wait_s=999, walk_s=0
        )
    )
    # The wait timeout should be scheduled internally at pickup-arrival + 3 = 13,
    # but we add it here to be explicit in case your handler doesn't.
    k.schedule(DriverWaitTimeout(t=13.0, driver_id=1, task_id=1))
    k.run(until=100.0)

    # r2 must be assigned at t=13
    assert times_of_rider(h, "TripAssigned", 200) == [13.0]
    # r1 should not have boarded
    assert times_of_rider(h, "TripBoarded", 100) == []
    # We should see a DriverCancel with reason wait_timeout
    dc_times = [
        e["t"]
        for e in h.events
        if e["name"] == "DriverCancel"
        and e.get("driver_id") == 1
        and e.get("reason") == "wait_timeout"
    ]
    assert 13.0 in dc_times


def test_rider_cancel_before_assignment_removes_from_queue_no_assignment_occurs():
    """
    No drivers initially; r1 requests at t=0 and is queued.
    r1 cancels at t=2 before any driver appears → removed from queue; no assignment ever.
    Later we add a driver and a different rider; only that rider should be assigned.
    """
    k, h, world = build_app(add_driver=False, pickup_s=10, dropoff_s=20, dwell=ZeroDwell())

    k.schedule(
        RiderRequestPlaced(
            t=0.0, rider_id=501, pickup=(0, 0), dropoff=(1, 1), max_wait_s=999, walk_s=0
        )
    )
    k.schedule(RiderCancel(t=2.0, rider_id=501, reason="user"))

    # Add a driver later and a new rider
    k.schedule(DriverStartShift(t=5.0, driver_id=1, loc=(0.0, 0.0)))
    k.schedule(
        RiderRequestPlaced(
            t=5.0, rider_id=502, pickup=(0, 0), dropoff=(2, 2), max_wait_s=999, walk_s=0
        )
    )
    k.run(until=100.0)

    # r501 was never assigned
    assert times_of_rider(h, "TripAssigned", 501) == []
    # r502 is assigned at t=5
    assert times_of_rider(h, "TripAssigned", 502) == [5.0]


def test_completion_without_dwell_assigns_next_rider_at_completion_time():
    """
    Baseline sanity: r1 completes at t=30 (10 pickup + 20 drive, zero dwell),
    r2 queued at t=5 should be assigned exactly at t=30.
    """
    k, h, world = build_app(pickup_s=10, dropoff_s=20, max_driver_wait_s=300, dwell=ZeroDwell())

    k.schedule(
        RiderRequestPlaced(
            t=0.0, rider_id=601, pickup=(0, 0), dropoff=(1, 1), max_wait_s=999, walk_s=0
        )
    )
    k.schedule(
        RiderRequestPlaced(
            t=5.0, rider_id=602, pickup=(0, 0), dropoff=(2, 2), max_wait_s=999, walk_s=0
        )
    )
    k.run(until=200.0)

    # First trip milestones
    assert times_of_rider(h, "TripAssigned", 601) == [0.0]
    assert kinds_of_rider(h, "DriverLegArrive", 601) == ["pickup", "dropoff"]
    assert times_of_rider(h, "DriverLegArrive", 601) == [10.0, 30.0]
    assert times_of_rider(h, "TripCompleted", 601) == [30.0]

    # Second assignment at completion time
    assert times_of_rider(h, "TripAssigned", 602) == [30.0]
    assert kinds_of_rider(h, "DriverLegArrive", 602) == ["pickup", "dropoff"]
    assert times_of_rider(h, "DriverLegArrive", 602) == [40.0, 60.0]
