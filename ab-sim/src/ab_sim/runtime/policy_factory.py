from ab_sim.app.protocols import DwellPolicy, IdlePolicy, MatchingPolicy, PricingPolicy
from ab_sim.config.models import (
    DwellPolicyExpBoardAlightModel,
    DwellPolicyUnion,
    IdlePolicyCirculatingModel,
    IdlePolicyUnion,
    MatchingPolicyNearestAssignModel,
    MatchingPolicyUnion,
    PricingPolicyConstantModel,
    PricingPolicyUnion,
)
from ab_sim.domain.state import WorldState
from ab_sim.policy.dwell import ExpBoardingAlightingPolicy
from ab_sim.policy.idle import CirculatingIdlePolicy
from ab_sim.policy.matching import NearestAssignMatchingPolicy
from ab_sim.policy.pricing import ConstantPricingPolicy
from ab_sim.sim.rng import RNGRegistry


def make_dwell_policy(cfg: DwellPolicyUnion, *, rng_registry: RNGRegistry) -> DwellPolicy:
    if isinstance(cfg, DwellPolicyExpBoardAlightModel):
        dp = ExpBoardingAlightingPolicy(
            rng_registry=rng_registry,
            board_mean_s=cfg.board_mean_s,
            alight_mean_s=cfg.alight_mean_s,
        )
        return dp
    else:
        raise TypeError(cfg)


def make_idle_policy(cfg: IdlePolicyUnion) -> IdlePolicy:
    if isinstance(cfg, IdlePolicyCirculatingModel):
        ip = CirculatingIdlePolicy(
            dwell_s=cfg.dwell_s, continual_reposition=cfg.continual_reposition
        )
        return ip
    else:
        raise TypeError(cfg)


def make_matching_policy(cfg: MatchingPolicyUnion, world: WorldState) -> MatchingPolicy:
    if isinstance(cfg, MatchingPolicyNearestAssignModel):
        mp = NearestAssignMatchingPolicy(world=world)
        return mp
    else:
        raise TypeError(cfg)


def make_pricing_policy(cfg: PricingPolicyUnion) -> PricingPolicy:
    if isinstance(cfg, PricingPolicyConstantModel):
        mp = ConstantPricingPolicy(fare=cfg.fare)
        return mp
    else:
        raise TypeError(cfg)
