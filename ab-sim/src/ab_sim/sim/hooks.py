# sim/hooks.py
from typing import Protocol

from ab_sim.sim.event import BaseEvent


class KernelHooks(Protocol):
    def run_start(
        self,
        *,
        until,
        max_events,
        qsize,
    ): ...
    def run_end(self, *, processed, last_t, qsize, wall_ms): ...
    def schedule(self, ev: BaseEvent, *, now, qsize): ...
    def dispatch_start(self, ev: BaseEvent, *, seq, qsize, handlers): ...
    def dispatch_end(self, ev: BaseEvent, *, out_events, ms): ...
    def error(self, ev: BaseEvent, *, reason: str, **kw): ...


class NoopHooks:
    def run_start(self, **_):
        pass

    def run_end(self, **_):
        pass

    def schedule(self, *_, **__):
        pass

    def dispatch_start(self, *_, **__):
        pass

    def dispatch_end(self, *_, **__):
        pass

    def error(self, *_, **__):
        pass
