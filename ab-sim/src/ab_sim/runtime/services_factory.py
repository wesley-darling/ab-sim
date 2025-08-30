# ab_sim/runtime/services_factory.py
from ab_sim.config.models import (
    TravelTimeServiceFixedModel,
    TravelTimeServiceMechanicsModel,
    TravelTimeUnion,
)
from ab_sim.services.travel_time import FixedDurationTravelTime, MechanicsTravelTime  # your classes


def make_travel_time(cfg: TravelTimeUnion, *, mechanics) -> MechanicsTravelTime:
    if isinstance(cfg, TravelTimeServiceMechanicsModel):
        tt = MechanicsTravelTime(mechanics)
        return tt
    elif isinstance(cfg, TravelTimeServiceFixedModel):
        return FixedDurationTravelTime(
            pickup_s=cfg.pickup_s,
            dropoff_s=cfg.dropoff_s,
            reposition_s=cfg.reposition_s,
        )
    else:
        raise TypeError(cfg)
