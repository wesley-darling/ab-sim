# ab_sim/app/controllers/fleet.py

from ab_sim.app.events import DriverAvailable, DriverStartShift
from ab_sim.domain.state import Driver, WorldState


class FleetHandler:
    def __init__(self, world: WorldState):
        self.world = world

    def on_driver_start_shift(self, ev: DriverStartShift):
        self.world.add_driver(Driver(id=ev.driver_id, loc=ev.loc))
        return [DriverAvailable(t=ev.t, driver_id=ev.driver_id)]
