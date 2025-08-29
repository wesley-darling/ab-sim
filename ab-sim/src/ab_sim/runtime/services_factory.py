# ab_sim/runtime/services_factory.py
from ab_sim.config.models import TravelTimeUnion, TTCfgFixed, TTCfgMechanics
from ab_sim.services.travel_time import FixedDurationTravelTime, MechanicsTravelTime  # your classes


def make_travel_time(cfg: TravelTimeUnion, *, mechanics) -> MechanicsTravelTime:
    if isinstance(cfg, TTCfgMechanics):
        tt = MechanicsTravelTime(mechanics)
        return tt
    elif isinstance(cfg, TTCfgFixed):
        return FixedDurationTravelTime(
            pickup_s=cfg.pickup_s,
            dropoff_s=cfg.dropoff_s,
            reposition_s=cfg.reposition_s,
        )
    else:
        raise TypeError(cfg)
