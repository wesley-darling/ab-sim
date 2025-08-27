# main.py
from ab_sim.sim.kernel import Kernel
from ab_sim.sim.event import EventKind
from ab_sim.app.controllers.rider_arrivals import RiderArrivalController
from ab_sim.app.controllers.service_manager_adapter import ServiceManagerAdapter


def run(horizon_s: float):
    k = Kernel()

    # Reuse your existing builders:
    rider_pool = make_rider_pool(...)  # your code
    service_mgr = make_service_manager(...)  # your code
    speed_sampler = make_speed_sampler(...)  # your code
    pricing_engine = make_pricing(...)  # your code

    arrivals = RiderArrivalController(k, rider_pool)
    sm_adapt = ServiceManagerAdapter(service_mgr, speed_sampler, pricing_engine)

    # Subscribe handlers
    k.on(EventKind.RIDER_ARRIVAL, sm_adapt.handle_rider_arrival)
    k.on(EventKind.DRIVER_STATE, sm_adapt.handle_driver_state)
    k.on(EventKind.DRIVER_IDLE_TIMEOUT, sm_adapt.handle_idle_timeout)

    # Seed initial events (all rider arrivals; or stream if you prefer)
    arrivals.seed(0.0, horizon_s)

    # Optional: schedule end-of-day timers, etc.
    # k.schedule(Event(t=86400.0, kind=EventKind.TIMER, eid="end_of_day"))

    k.run(until=horizon_s)
