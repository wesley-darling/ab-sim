# ab_sim/policy/idle.py

from ab_sim.app.protocols import IdlePolicy


class CirculatingIdlePolicy(IdlePolicy):
    def __init__(self, dwell_s: float = 0.0, continual_reposition: bool = True):
        self.dwell_s = dwell_s
        self.continual = continual_reposition
