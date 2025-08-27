# tests/sim/test_kernel.py
from dataclasses import dataclass

from ab_sim.sim.event import BaseEvent
from ab_sim.sim.hooks import NoopHooks
from ab_sim.sim.kernel import Kernel


# ---- demo domain events ----
@dataclass(order=True)
class Ping(BaseEvent):
    n: int = 0


@dataclass(order=True)
class Pong(BaseEvent):
    n: int = 0


@dataclass(order=True)
class Timer(BaseEvent):
    label: str = ""


# ---- demo handlers ----
def handle_ping(ev: Ping):
    out: list[BaseEvent] = [Pong(t=ev.t, n=ev.n)]
    if ev.n > 0:
        out.append(Ping(t=ev.t + 1.0, n=ev.n - 1))
    return out


def handle_pong(ev: Pong):
    return [Timer(t=ev.t + 0.5, label=f"after pong {ev.n}")]


def handle_timer(ev: Timer):
    return []


# --- test hook that records dispatch order & times ---
class TraceHooks(NoopHooks):
    def __init__(self):
        self.trace = []

    # Kernel calls dispatch_start(ev, *, seq, qsize, handlers)
    def dispatch_start(self, ev, *, seq, qsize, handlers):
        self.trace.append((ev.t, type(ev).__name__))


# ---- self-tests ----
def test_kernel():
    hooks = TraceHooks()
    k = Kernel(hooks=hooks)
    k.on(Ping, handle_ping)
    k.on(Pong, handle_pong)
    k.on(Timer, handle_timer)

    # Order & fan-out
    k.schedule(Ping(t=0.0, n=2))
    processed = k.run(until=3.0)
    assert processed == 9
    names = [name for _, name in hooks.trace]
    times = [t for t, _ in hooks.trace]
    assert names == ["Ping", "Pong", "Timer", "Ping", "Pong", "Timer", "Ping", "Pong", "Timer"]
    assert times == [0.0, 0.0, 0.5, 1.0, 1.0, 1.5, 2.0, 2.0, 2.5]

    # FIFO tie-break
    k2 = Kernel()
    seen: list[str] = []
    k2.on(Ping, lambda ev: (seen.append("A"), [])[1] if False else (seen.append("A"), None)[1])
    k2.on(Ping, lambda ev: (seen.append("B"), None)[1])
    k2.schedule(Ping(t=5.0, n=0))
    k2.schedule(Ping(t=5.0, n=0))
    k2.run()
    assert seen == ["A", "B", "A", "B"]

    # max_events gate
    k3 = Kernel()
    k3.on(Ping, handle_ping)
    k3.schedule(Ping(t=0.0, n=10))
    assert k3.run(max_events=1) == 1
    assert k3.now == 0.0

    # scheduling in the past should raise
    k4 = Kernel()
    k4.on(Ping, lambda ev: [Ping(t=ev.t - 1.0, n=0)])
    k4.schedule(Ping(t=1.0, n=0))
    try:
        k4.run()
        assert False, "expected RuntimeError for past scheduling"
    except RuntimeError:
        pass
