# sim/events.py

from dataclasses import dataclass


@dataclass(order=True)
class BaseEvent:
    t: float
