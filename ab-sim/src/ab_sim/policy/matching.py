# ab_sim/policy/assign.py
from dataclasses import dataclass

from ab_sim.app.protocols import MatchingPolicy
from ab_sim.domain.state import WorldState


@dataclass
class NearestAssignMatchingPolicy(MatchingPolicy):
    world: WorldState

    # Example # Emit business-only enrichment (does not affect sim)
    # self.hooks.biz(TripMatchedBiz(
    #     run_id="unknown", t=now, seq=seq, name="TripMatched",  # run_id is set by KernelJSONHooks if you want; or pass it here
    #     rider_id=rider_id, driver_id=did, task_id=self.world.drivers[did].task_id,
    #     score=score, eta_s=eta_s
    # ))
