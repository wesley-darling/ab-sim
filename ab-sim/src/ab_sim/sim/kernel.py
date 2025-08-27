# sim/kernel.py

import heapq
import time
from collections.abc import Callable, Iterable

from .event import BaseEvent
from .hooks import KernelHooks, NoopHooks

Handler = Callable[[BaseEvent], Iterable[BaseEvent] | None]


class Kernel:
    def __init__(self, hooks: KernelHooks | None = None):
        self._t = 0.0
        self._q: list[tuple[float, int, BaseEvent]] = []
        self._seq = 0
        self._subs: dict[type[BaseEvent], list[Handler]] = {}
        self._hooks = hooks or NoopHooks()

    @property
    def now(self) -> float:
        return self._t

    def on(self, etype: type[BaseEvent], handler: Handler) -> None:
        self._subs.setdefault(etype, []).append(handler)

    def schedule(self, ev: BaseEvent) -> None:
        self._seq += 1
        heapq.heappush(self._q, (ev.t, self._seq, ev))
        self._hooks.schedule(ev, now=self._t, qsize=len(self._q))

    def run(self, until: float | None = None, max_events: int | None = None) -> int:
        t0 = time.perf_counter()
        self._hooks.run_start(until=until, max_events=max_events, qsize=len(self._q))
        processed = 0
        while self._q and (until is None or self._q[0][0] <= until):
            t, _, ev = heapq.heappop(self._q)
            if t < self._t - 1e-9:
                self._hooks.error(ev, reason="time_backwards", prev_t=self._t, t=t)
                raise RuntimeError(f"time went backwards: {t} < {self._t}")
            self._t = t
            handlers = self._subs.get(type(ev), ())
            t1 = time.perf_counter()
            self._hooks.dispatch_start(
                ev, seq=self._seq, qsize=len(self._q), handlers=len(handlers)
            )
            total_out = 0
            for h in handlers:
                out = h(ev) or ()
                for nxt in out:
                    if nxt.t + 1e-12 < self._t:
                        self._hooks.error(
                            ev,
                            reason="scheduled_past",
                            scheduled_t=nxt.t,
                            nxt_type=type(nxt).__name__,
                        )
                        raise RuntimeError(
                            f"handler scheduled past event at {nxt.t} < now {self._t}"
                        )
                    self.schedule(nxt)
            ms = (time.perf_counter() - t1) * 1000
            self._hooks.dispatch_end(ev, out_events=total_out, ms=ms)
            processed += 1
            if max_events and processed >= max_events:
                break
        self._hooks.run_end(
            processed=processed,
            last_t=self._t,
            qsize=len(self._q),
            wall_ms=(time.perf_counter() - t0) * 1000,
        )
        return processed
