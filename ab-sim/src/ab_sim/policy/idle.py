# ab_sim/policy/idle.py


class IdlePolicy:
    def __init__(self, dwell_s: float = 0.0, continual_reposition: bool = False):
        self.dwell_s = dwell_s
        self.continual = continual_reposition
