# ab_sim/app/wiring.py
from ab_sim.app.controllers.demand import DemandHandler
from ab_sim.app.controllers.fleet import FleetHandler
from ab_sim.app.controllers.idle import IdleHandler
from ab_sim.app.controllers.trips import TripHandler
from ab_sim.app.events import (
    AlightingComplete,
    AlightingStarted,
    BoardingComplete,
    BoardingStarted,
    DriverAvailable,
    DriverCancel,
    DriverIdleTimeout,
    DriverLegArrive,
    DriverStartShift,
    DriverWaitTimeout,
    EndOfDay,
    PickupDeadline,
    RiderArrivePickup,
    RiderCancel,
    RiderRequestPlaced,
    RiderRequeue,
    RiderTimeout,
    TripAssigned,
    TripCompleted,
)
from ab_sim.sim.kernel import Kernel


def wire(
    kernel: Kernel,
    *,
    trips: TripHandler,
    demand: DemandHandler,
    idle: IdleHandler,
    housekeeping=None,
    fleet: FleetHandler,
) -> None:
    k = kernel

    k.on(PickupDeadline, trips.on_pickup_deadline)  # translates to RiderCancel(...)
    k.on(DriverWaitTimeout, trips.on_driver_wait_timeout)  # translates to DriverCancel(...)

    # canonical cancels
    k.on(RiderCancel, trips.on_rider_cancel)  # free driver if assigned
    k.on(RiderCancel, demand.on_rider_cancel)  # drop from queue if queued

    k.on(DriverCancel, trips.on_driver_cancel)  # free driver + emit RiderRequeue
    k.on(RiderRequeue, demand.on_rider_requeue)  # re-enqueue rider

    k.on(DriverAvailable, idle.on_driver_available)

    # demand

    k.on(RiderRequestPlaced, demand.on_rider_request)
    k.on(RiderTimeout, demand.on_rider_timeout)

    if fleet:
        k.on(DriverStartShift, fleet.on_driver_start_shift)

    # trips
    k.on(TripAssigned, trips.on_trip_assigned)
    k.on(DriverLegArrive, trips.on_driver_leg_arrive)
    k.on(RiderArrivePickup, trips.on_rider_arrive_pickup)

    k.on(BoardingStarted, trips.on_boarding_started)
    k.on(BoardingComplete, trips.on_boarding_complete)

    k.on(AlightingStarted, trips.on_alighting_started)
    k.on(AlightingComplete, trips.on_alighting_complete)
    # idle → attempt to serve queue after completion
    k.on(TripCompleted, idle.on_trip_completed)

    # supply housekeeping
    k.on(DriverIdleTimeout, idle.on_idle_timeout)

    # daily rollups / maintenance
    if housekeeping:
        k.on(EndOfDay, housekeeping.on_end_of_day)
