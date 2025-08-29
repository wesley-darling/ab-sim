# tests/app/test_pickup_and_rendezvous.py
from ab_sim.app.controllers.demand import DemandHandler
from ab_sim.app.controllers.fleet import FleetHandler
from ab_sim.app.controllers.idle import IdleHandler, IdlePolicy
from ab_sim.app.controllers.trips import FixedSpeedModel, TripHandler
from ab_sim.app.events import RiderCancel, RiderRequestPlaced
from ab_sim.app.wiring import wire
from ab_sim.domain.mechanics.mechanics_factory import build_mechanics
from ab_sim.domain.state import Driver, WorldState
from ab_sim.io.config import MechanicsConfig
from ab_sim.policy.assign import NearestAssign
from ab_sim.policy.pricing import PricingPolicy
from ab_sim.sim.clock import SimClock
from ab_sim.sim.hooks import NoopHooks
from ab_sim.sim.kernel import Kernel
from ab_sim.sim.metrics import Metrics
from ab_sim.sim.rng import RNGRegistry


# A tiny trace hook to observe event order/times without touching kernel internals
class TraceHooks(NoopHooks):
    def __init__(self):
        self.events = []

    def dispatch_start(self, ev, *, seq, qsize, handlers):
        self.events.append((ev.t, type(ev).__name__, getattr(ev, "kind", None)))


# --- Test-only dwell model with fixed delays ---
class FixedDwell:
    def __init__(self, board_s: float, alight_s: float):
        self.board_s = board_s
        self.alight_s = alight_s

    def boarding_delay(self, rider_id: int, driver_id: int) -> float:
        return self.board_s

    def alighting_delay(self, rider_id: int, driver_id: int) -> float:
        return self.alight_s


def build_app(pickup_s=10.0, dropoff_s=20.0, board_s=5.0, alight_s=3.0):
    world = WorldState()
    # one idle driver at (0,0)
    world.add_driver(Driver(id=1, loc=(0.0, 0.0)))
    mech_cfg = MechanicsConfig(
        mode="idealized",
        metric="euclidean",
        speed_kind="constant",
        base_mps=max(pickup_s, dropoff_s),
    )
    mechanics = build_mechanics(
        mech_cfg, rng_registry=RNGRegistry(master_seed=0, scenario="tests", worker=0)
    )
    clock = SimClock.utc_epoch(2025, 1, 1, 0, 0, 0)
    speeds = FixedSpeedModel(pickup_s=pickup_s, dropoff_s=dropoff_s)
    dwell = FixedDwell(board_s=board_s, alight_s=alight_s)
    rng_registry = RNGRegistry(master_seed=0)
    trips = TripHandler(
        world=world,
        speeds=speeds,
        mechanics=mechanics,
        max_driver_wait_s=300.0,
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

    hooks = TraceHooks()
    k = Kernel(hooks=hooks)
    wire(k, trips=trips, demand=demand, idle=idle, fleet=fleet)
    return k, hooks, world


def times_of(hooks, name):
    return [t for t, n, _ in hooks.events if n == name]


def kinds_at(hooks, name):
    return [k for _, n, k in hooks.events if n == name]


def test_queued_rider_served_after_trip_completion():
    # one driver; two riders: r1 at t=0, r2 at t=5
    # r1: pickup 10s → drop 20s → completes at t=30
    # r2: enqueues at t=5; matched at t=30 when driver becomes idle (TripCompleted)
    k, h, world = build_app(pickup_s=10.0, dropoff_s=20.0, board_s=0, alight_s=0)

    k.schedule(
        RiderRequestPlaced(
            t=0.0, rider_id=201, pickup=(0, 0), dropoff=(1, 1), max_wait_s=999, walk_s=0.0
        )
    )
    k.schedule(
        RiderRequestPlaced(
            t=5.0, rider_id=202, pickup=(0, 0), dropoff=(2, 2), max_wait_s=999, walk_s=0.0
        )
    )
    k.run(until=200.0)

    # r1 path: assign 0, pickup arrive 10, board 10, drop arrive 30, complete 30
    assert times_of(h, "TripAssigned")[0] == 0.0
    assert times_of(h, "DriverLegArrive")[0] == 10.0
    assert kinds_at(h, "DriverLegArrive")[0] == "pickup"
    # r2 match should happen when r1 completes at t=30
    assert times_of(h, "TripAssigned")[1] == 30.0
    # r2 pickup/drop based on same durations
    # pickup arrive at 40, drop arrive at 60, complete 60
    assert kinds_at(h, "DriverLegArrive")[2] == "pickup"
    assert times_of(h, "DriverLegArrive")[2] == 40.0
    assert kinds_at(h, "DriverLegArrive")[3] == "dropoff"
    assert times_of(h, "DriverLegArrive")[3] == 60.0


def test_idle_driver_matches_new_request_immediately():
    # Driver is idle; new request should match at request time
    k, h, world = build_app(pickup_s=8.0, dropoff_s=12.0, board_s=0, alight_s=0)

    # keep driver idle until request arrives
    k.schedule(
        RiderRequestPlaced(
            t=100.0, rider_id=301, pickup=(0, 0), dropoff=(3, 3), max_wait_s=999, walk_s=0.0
        )
    )
    k.run(until=200.0)

    # Assigned immediately at t=100
    assert times_of(h, "TripAssigned") == [100.0]
    # pickup at 108, drop at 120
    assert times_of(h, "DriverLegArrive")[0] == 108.0
    assert kinds_at(h, "DriverLegArrive")[0] == "pickup"
    assert times_of(h, "DriverLegArrive")[1] == 120.0
    assert kinds_at(h, "DriverLegArrive")[1] == "dropoff"


def test_driver_arrives_first_then_rider_boards():
    k, hooks, world = build_app(pickup_s=10.0, dropoff_s=20.0, board_s=0, alight_s=0)
    # Rider will walk 15s → driver (10s) arrives first, waits 5s, then depart at t=15, dropoff at 35
    k.schedule(
        RiderRequestPlaced(
            t=0.0, rider_id=101, pickup=(0, 0), dropoff=(1, 1), max_wait_s=999, walk_s=15.0
        )
    )
    k.run(until=100.0)

    # Event sequence sanity
    assert times_of(hooks, "TripAssigned") == [0.0]
    # Driver pickup arrival at t=10
    assert times_of(hooks, "DriverLegArrive")[0] == 10.0
    assert kinds_at(hooks, "DriverLegArrive")[0] == "pickup"
    # Boarding occurs when rider arrives at 15
    assert times_of(hooks, "TripBoarded") == [15.0]
    # Dropoff at 15 + 20 = 35
    assert times_of(hooks, "DriverLegArrive")[1] == 35.0
    assert kinds_at(hooks, "DriverLegArrive")[1] == "dropoff"
    assert times_of(hooks, "TripCompleted") == [35.0]


def test_rider_arrives_first_then_instant_board_on_driver_arrival():
    k, hooks, world = build_app(pickup_s=10.0, dropoff_s=20.0, board_s=0, alight_s=0)
    # Rider walks 5s → rider arrives at 5, driver arrives at 10 → board at 10, drop at 30
    k.schedule(
        RiderRequestPlaced(
            t=0.0, rider_id=102, pickup=(0, 0), dropoff=(1, 1), max_wait_s=999, walk_s=5.0
        )
    )
    k.run(until=100.0)

    assert times_of(hooks, "TripAssigned") == [0.0]
    assert times_of(hooks, "DriverLegArrive")[0] == 10.0
    assert kinds_at(hooks, "DriverLegArrive")[0] == "pickup"
    assert times_of(hooks, "TripBoarded") == [10.0]
    assert times_of(hooks, "DriverLegArrive")[1] == 30.0
    assert kinds_at(hooks, "DriverLegArrive")[1] == "dropoff"
    assert times_of(hooks, "TripCompleted") == [30.0]


def test_pickup_deadline_cancels_if_rider_not_boarded():
    k, hooks, world = build_app(pickup_s=10.0, dropoff_s=20.0, board_s=0, alight_s=0)
    # Rider walks 30s but max_wait is 8 → deadline at t=8 cancels; no boarding, no dropoff
    k.schedule(
        RiderRequestPlaced(
            t=0.0, rider_id=103, pickup=(0, 0), dropoff=(1, 1), max_wait_s=8.0, walk_s=30.0
        )
    )
    k.run(until=100.0)

    # assignment still happens at t=0 (driver exists)
    assert times_of(hooks, "TripAssigned") == [0.0]
    # There should be no TripBoarded nor dropoff arrivals
    assert times_of(hooks, "TripBoarded") == []
    # The driver pickup arrival (t=10) still occurs, but TripHandler cancels on deadline before boarding
    # After cancellation, there must be no dropoff arrival
    kinds = kinds_at(hooks, "DriverLegArrive")
    # At most one "pickup" arrival, zero "dropoff"
    assert "dropoff" not in kinds
    # Driver should end idle again
    assert world.drivers[1].state == "idle"


def test_dwell_when_rider_already_at_pickup():
    """
    Rider is at pickup immediately (walk_s=0):
      assign @0 → driver arrives @10
      BoardingStarted @10; BoardingComplete @15 (5s dwell)
      TripBoarded @15; dropoff arrival @35 (20s drive)
      AlightingStarted @35; AlightingComplete @38 (3s dwell)
      TripCompleted @38
    """
    k, h, world = build_app(board_s=5.0, alight_s=3.0)
    k.schedule(
        RiderRequestPlaced(
            t=0.0, rider_id=401, pickup=(0, 0), dropoff=(1, 1), max_wait_s=999, walk_s=0.0
        )
    )
    k.run(until=100.0)

    assert times_of(h, "TripAssigned") == [0.0]
    # pickup arrival
    assert kinds_at(h, "DriverLegArrive")[0] == "pickup"
    assert times_of(h, "DriverLegArrive")[0] == 10.0

    # boarding dwell phase
    assert times_of(h, "BoardingStarted") == [10.0]
    assert times_of(h, "BoardingComplete") == [15.0]
    # we emit TripBoarded at the same time boarding completes
    assert times_of(h, "TripBoarded") == [15.0]

    # dropoff arrival and alighting dwell
    assert kinds_at(h, "DriverLegArrive")[1] == "dropoff"
    assert times_of(h, "DriverLegArrive")[1] == 35.0
    assert times_of(h, "AlightingStarted") == [35.0]
    assert times_of(h, "AlightingComplete") == [38.0]
    assert times_of(h, "TripCompleted") == [38.0]


def test_dwell_when_driver_arrives_first_then_rider():
    """
    Rider walks for 12s; driver pickup leg is 10s:
      driver arrives @10, rider arrives @12
      BoardingStarted @12; BoardingComplete @17 (5s dwell)
      TripBoarded @17; dropoff arrival @37 (20s drive)
      AlightingStarted @37; AlightingComplete @40 (3s dwell)
      TripCompleted @40
    """
    k, h, world = build_app(board_s=5.0, alight_s=3.0)
    k.schedule(
        RiderRequestPlaced(
            t=0.0, rider_id=402, pickup=(0, 0), dropoff=(2, 2), max_wait_s=999, walk_s=12.0
        )
    )
    k.run(until=100.0)

    assert times_of(h, "TripAssigned") == [0.0]
    # pickup arrival
    assert kinds_at(h, "DriverLegArrive")[0] == "pickup"
    assert times_of(h, "DriverLegArrive")[0] == 10.0

    # boarding dwell begins when rider arrives
    assert times_of(h, "BoardingStarted") == [12.0]
    assert times_of(h, "BoardingComplete") == [17.0]
    assert times_of(h, "TripBoarded") == [17.0]

    # dropoff + alighting dwell
    assert kinds_at(h, "DriverLegArrive")[1] == "dropoff"
    assert times_of(h, "DriverLegArrive")[1] == 37.0
    assert times_of(h, "AlightingStarted") == [37.0]
    assert times_of(h, "AlightingComplete") == [40.0]
    assert times_of(h, "TripCompleted") == [40.0]


def test_rider_cancel_frees_driver_and_matches_next():
    k, h, world = build_app(pickup_s=10, dropoff_s=20, board_s=0, alight_s=0)

    # two riders; r1 cancels at t=3 while driver en-route (pickup would be at t=10)
    k.schedule(
        RiderRequestPlaced(
            t=0.0, rider_id=1, pickup=(0, 0), dropoff=(1, 1), max_wait_s=999, walk_s=0
        )
    )
    k.schedule(
        RiderRequestPlaced(
            t=1.0, rider_id=2, pickup=(0, 0), dropoff=(2, 2), max_wait_s=999, walk_s=0
        )
    )
    k.schedule(RiderCancel(t=3.0, rider_id=1))

    k.run(until=100.0)

    # driver should be reassigned to rider 2 at t=3 (immediately after cancel)
    assert times_of(h, "TripAssigned")[1] == 3.0
