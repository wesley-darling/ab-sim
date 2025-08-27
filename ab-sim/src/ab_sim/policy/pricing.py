# ab_sim/policy/pricing.py

from dataclasses import dataclass


@dataclass
class PricingPolicy:
    price: int
