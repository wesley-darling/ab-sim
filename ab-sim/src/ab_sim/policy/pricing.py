# ab_sim/policy/pricing.py

from ab_sim.app.protocols import PricingPolicy


class ConstantPricingPolicy(PricingPolicy):
    def __init__(self, fare: float = 0.0):
        self.fare = fare

    def get_price(self):
        return self.fare
