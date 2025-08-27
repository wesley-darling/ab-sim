Design goals

Engine is framework-like (events + queue + time); knows nothing about TNCs.

Domain is deterministic & typed; all randomness comes via injected RNG streams.

Policies are plugins (Strategy pattern) with slim interfaces.

I/O is peripheral; core types don’t depend on Pandas or file formats.

Metrics are first-class; separable, cheap, and consistent.

2) Core engine (discrete-event, pure)

Key types

# sim/event.py
from dataclasses import dataclass
from enum import Enum, auto
from typing import Callable, Any

class EventKind(Enum):
    RIDER_ARRIVAL = auto()
    DRIVER_STATE = auto()
    TIMER = auto()

@dataclass(order=True)
class Event:
    t: float
    kind: EventKind
    eid: int | str
    payload: dict[str, Any] | None = None


Kernel contract

# sim/kernel.py
class Kernel:
    def __init__(self, clock, queue, metrics, rng_registry): ...
    def schedule(self, event: Event): ...
    def run(self, until: float | None = None, max_events: int | None = None): ...


No TNC knowledge—just fires events to registrants (domain controllers) that subscribe by EventKind.

3) Domain layer (entities + FSM + mechanics)
Entities: typed, data-focused
# domain/entities/driver.py
from dataclasses import dataclass, field
import numpy as np

@dataclass
class Driver:
    id: int
    loc: np.ndarray         # shape (2,), meters
    state: str              # "IDLE", "TO_PICKUP", "TO_DROPOFF", ...
    speed_mps: float
    rider_id: int | None = None
    t_last: float = 0.0

@dataclass
class Rider:
    id: int
    request_t: float
    origin: np.ndarray
    dest: np.ndarray
    status: str = "WAITING"  # "ASSIGNED", "ONBOARD", "DROPPED"
    assigned_driver: int | None = None

Declarative FSM (readable + testable)
# domain/transitions.py
from typing import Protocol, Iterable, Callable

Guard = Callable[[...], None]  # raise on violation
Action = Callable[[...], None] # mutates world, schedules next event

@dataclass
class Transition:
    src: str
    event: str
    dst: str
    guards: list[Guard] = field(default_factory=list)
    actions: list[Action] = field(default_factory=list)


You keep a table of transitions and execute them when driver/rider receives a state event. Guards encode VIA-style invariants (e.g., “driver.location equals previous dropoff for chained assignment”).

Mechanics (movement, time-to-go)

Encapsulate math: eta(from, to, speed), advance_position(dt), snap-to-grid if needed. No policy logic here.

4) Policy layer (hot-swappable strategies)

Define minimal protocols so it’s easy to A/B a tactic.

# policy/assign.py
from typing import Protocol, Iterable
from domain.entities.driver import Driver
from domain.entities.rider import Rider

class Matcher(Protocol):
    def assign(self, now: float, riders: Iterable[Rider], idle_drivers: Iterable[Driver]) -> list[tuple[int,int]]:
        """Return list of (rider_id, driver_id) matches to commit now."""


Dispatch (how we notify drivers): broadcast, top-k nearest, score threshold.

Pooling: accept constraints (max detour, time-loss) and return insertion points (Dial-a-Ride style).

Rebalancing: target-density repositioning vs learned heatmap.

Pricing/Incentives: callable to compute fare/driver pay; can add per-event hooks to record costs.

Each policy can be configured via Pydantic models and selected in scenario YAML:

assign:
  name: "greedy-nearest"
  max_radius_m: 2000
  score:
    weight_wait_s: -0.3
    weight_detour_s: -0.7

5) WorldState & indices

A single source of truth with fast lookups:

# domain/state.py
class WorldState:
    def __init__(self, drivers: dict[int,Driver], riders: dict[int,Rider], grid_index, kd_index):
        self.drivers = drivers
        self.riders = riders
        self.idle_driver_ids: set[int] = set()
        self.waiting_rider_ids: set[int] = set()


Maintain a KD-Tree (scikit-spatial or your own) for nearest-driver queries; update on driver moves/idle changes.

Optionally maintain region bins for coarse demand balancing.

6) Time, units, randomness

Units: adopt meters + seconds internally; wrap with helpers (to_km, to_min) only in I/O/plots.

RNG streams: separate streams per phenomenon (rng_demand, rng_speed, rng_behavior) for reproducible yet independent draws.

Speeds/TT: parameterize speed models (by time-of-day or segment class); centralize in models.travel_time.

7) I/O & configuration

Pydantic Settings for scenario config (validates ranges, sums to 1, etc.).

Inputs: readers that produce typed in-memory structures (no Pandas in core).

Outputs: append-safe Parquet/CSV writers with fixed schemas:

rides.parquet (one row per ride with times/distances/costs)

driver_times.parquet (state splits per driver)

events.parquet (optional, for debugging)

Logging: JSON logs with run_id, seed, and event counts; DEBUG flag prints FSM transitions.

8) Run loop (putting it together)

Seed kernel with:

First wave of rider arrivals (from a generator that yields (t, rider) or Poisson process).

Driver state events at t=0 (IDLE).

On each popped event:

Advance world time and move drivers by dt (single vectorized call or per-driver).

Handle event:

RIDER_ARRIVAL → enqueue rider; invoke Matcher.assign.

DRIVER_STATE → apply FSM transition; schedule next event (pickup, dropoff, dwell end).

Collect metrics on state exit (not continuously), to minimize overhead.

9) Testing strategy (fast + trustworthy)

Unit tests: pure functions (ETA, scoring, fare split).

FSM tests: table-driven—each transition’s guards and side-effects.

Property tests:

Time monotonicity: dropoff ≥ pickup ≥ assign ≥ request.

Non-negativity of distances/times.

VIA invariants hold when enabled.

Golden runs (snapshots): tiny scenario (e.g., 200 riders, 50 drivers, seed=42) → persist key aggregates; fail if drift exceeds tolerance.

Model alignment: assert sim throughput roughly matches models.capacity.n_t(...) within ε for synthetic grids.

10) Performance playbook

Event granularity: only schedule events at meaningful boundaries (arrival, start/finish of legs, end of dwell). Avoid sub-steps.

Vectorize movement: advance all drivers in a single NumPy op per tick dt.

Batch spatial queries: rebuild KD-Tree only when idle set changes; bulk query riders in assignment.

Avoid tiny Python objects in tight loops; keep dataclasses but cache np.ndarray refs and floats.

Parallelism: many-run parallelism (scenarios/seeds) via multiprocessing/Ray; keep single-run single-threaded for determinism.

11) Extensibility hooks (what people actually ask for)

Timeouts: rider cancellation events scheduled at request_t + W.

Guarantees: schedule deadline events that trigger price boosts or priority.

Multi-party pooling: policy surface returns route insertion plans; mechanics execute and reschedule.

Geofenced rules: policy decorators that apply different matching or pricing per region/time.

Learning policies: wrap a Matcher that logs (state, action, reward) and can be swapped with an RL agent later.

12) Minimal but powerful interfaces
# cli.py
@app.command()
def run(scenario: Path, seed: int = 42, outdir: Path = Path("out")):
    cfg = load_config(scenario)   # pydantic; validates units/ranges
    world = build_world(cfg, seed)
    kernel = build_kernel(cfg, seed)
    attach_controllers(kernel, world, cfg)  # wires policy handlers
    kernel.run(until=cfg.horizon_s)
    export(world, outdir, run_id=str(uuid4()))

13) Documentation & contracts

README: what’s event-based, how to reproduce a figure, how to add a policy.

docs/architecture.md (the diagram above + FSM/table examples).

contracts.md: “engine doesn’t call sleep(), policies don’t mutate time, movement only in mechanics,” etc.


What to build (work breakdown)
A) Core engine (foundation)

Event types & queue: Event{t, kind, id, payload}, priority queue, schedule(), run().

Clock & RNG registry: named RNG streams (demand, speeds, policy).

World state: typed Driver, Rider, indices (idle set, waiting set).

FSM/transitions: driver phases (IDLE → TO_PICKUP → TO_DROPOFF → IDLE), guards, actions.

Mechanics: distance/ETA, movement math (meters/seconds).

Metrics: per-trip record, per-driver state totals, daily rollups.

Config & I/O: Pydantic Settings, readers, OutputSink (HDF5/Parquet).

B) Policy layer (pluggable)

Matcher (protocol) + Greedy-Nearest implementation.

Rebalancing (stub; no-op first).

PricingEngine (fare tables, incentives, commission).

SpeedSampler (your DOW×Hour draws + fallbacks).

C) Your notebook scenario (controller bundle)

AreaSupplyController: baseline provisioning, ephemeral spawn, idle-timeout exit, buffer-area logic.

RiderArrivalController: Poisson arrivals from hourly λ; percent scaling; iteration seed handling.

DailyRollup: end-of-day timer, sentiment sweeps, write to sink.

Experiment runner: loops over pct × FoS × sentiment × iterations.

D) Testing & docs

Unit tests: ETA math, pricing, guards, transitions.

Property tests: time monotonicity; distance non-negativity; VIA-style invariant when enabled.

Golden run: tiny seed scenario snapshot.

Docs: README, architecture diagram, scenario how-to.

Acceptance criteria (definition of done)

Engine runs with one event queue; no busy-wait ticks.

Deterministic with a fixed seed (same aggregates across runs).

Scenario reproduces your notebook outputs to within agreed tolerances:

Wait time distributions, pickup distances, trip times.

Daily rollups for each sentiment (means, counts, driver hours, commission, generalized/monetary costs).

Logs: JSON lines with run_id, seed, event counts, errors=0.

CI: lint + tests + a golden-snapshot check.


Build sequence (critical path)

1. Kernel + Events → 2) WorldState + FSM + Mechanics →

2. Matcher + SpeedSampler + PricingEngine →

3. Scenario controllers (AreaSupply, RiderArrival) →

4. Metrics + DailyRollup + OutputSink →

5. Experiment runner →

6. Tests + Golden → 8) Docs


Risk checklist (reduce rework)

Units: lock meters/seconds end-to-end; enforce with asserts.

RNG isolation: separate streams for demand/speed/policy; seed discipline.

Event granularity: only schedule at arrivals, leg starts/ends, idle timeouts, end-of-day.

Schema freeze: decide per-trip/per-day output fields before coding sinks.

Golden tolerances: agree acceptable drift vs your notebook (e.g., ±3% on means).




What to build (work breakdown)
A) Core engine (foundation)

Event types & queue: Event{t, kind, id, payload}, priority queue, schedule(), run().

Clock & RNG registry: named RNG streams (demand, speeds, policy).

World state: typed Driver, Rider, indices (idle set, waiting set).

FSM/transitions: driver phases (IDLE → TO_PICKUP → TO_DROPOFF → IDLE), guards, actions.

Mechanics: distance/ETA, movement math (meters/seconds).

Metrics: per-trip record, per-driver state totals, daily rollups.

Config & I/O: Pydantic Settings, readers, OutputSink (HDF5/Parquet).

B) Policy layer (pluggable)

Matcher (protocol) + Greedy-Nearest implementation.

Rebalancing (stub; no-op first).

PricingEngine (fare tables, incentives, commission).

SpeedSampler (your DOW×Hour draws + fallbacks).

C) Your notebook scenario (controller bundle)

AreaSupplyController: baseline provisioning, ephemeral spawn, idle-timeout exit, buffer-area logic.

RiderArrivalController: Poisson arrivals from hourly λ; percent scaling; iteration seed handling.

DailyRollup: end-of-day timer, sentiment sweeps, write to sink.

Experiment runner: loops over pct × FoS × sentiment × iterations.

D) Testing & docs

Unit tests: ETA math, pricing, guards, transitions.

Property tests: time monotonicity; distance non-negativity; VIA-style invariant when enabled.

Golden run: tiny seed scenario snapshot.

Docs: README, architecture diagram, scenario how-to.

Acceptance criteria (definition of done)

Engine runs with one event queue; no busy-wait ticks.

Deterministic with a fixed seed (same aggregates across runs).

Scenario reproduces your notebook outputs to within agreed tolerances:

Wait time distributions, pickup distances, trip times.

Daily rollups for each sentiment (means, counts, driver hours, commission, generalized/monetary costs).

Logs: JSON lines with run_id, seed, event counts, errors=0.

CI: lint + tests + a golden-snapshot check.

Estimation framework you can apply (no time units)

Use story points (relative effort), then convert to calendar using your own historical throughput.



Point scale (simple)

1 = trivial (rename, wire, tiny pure function)

2 = small (one module, no new types)

3 = medium (new type + tests)

5 = large (cross-cutting or multiple types)

8 = extra large (complex controller or refactor)

Suggested points (baseline)

A) Core engine

Event queue & kernel: 5

Clock & RNG registry: 2

World state structs & indices: 3

FSM transitions & guards: 5

Mechanics (distance/ETA, units): 2

Metrics layer: 3

Config & I/O (Pydantic + one sink): 3
Subtotal A ≈ 23

B) Policies

Matcher (greedy-nearest): 3

PricingEngine (fare tables + incentives): 3

SpeedSampler (DOW×Hour + fallbacks): 3

Rebalancing stub: 1
Subtotal B ≈ 10

C) Scenario

AreaSupplyController (baseline + spawn + exit): 5

RiderArrivalController (Poisson + pct scaling): 3

DailyRollup + sentiment loops: 3

Experiment runner (grid): 2
Subtotal C ≈ 13

D) Tests & docs

Unit/property tests: 5

Golden run & fixtures: 3

Docs (README + scenario): 2
Subtotal D ≈ 10

Grand total (baseline) ≈ 56 points

Complexity multipliers (apply if true)

Pooling or insertion heuristics beyond single-rider: ×1.5

Multiple areas or road network travel times: ×1.5–2.0

Backward-compat with legacy outputs: +5–8 points

Parallel experiment runner (multi-proc): +3

Second output format (Parquet + HDF5): +2

Convert points → calendar (your data)

Pick your typical weekly throughput (points/week) from past work.

Add a buffer factor for integration/bugs based on experience.

Sequence work by dependencies (below) to get an execution plan.


Build sequence (critical path)

Kernel + Events → 2) WorldState + FSM + Mechanics →

Matcher + SpeedSampler + PricingEngine →

Scenario controllers (AreaSupply, RiderArrival) →

Metrics + DailyRollup + OutputSink →

Experiment runner →

Tests + Golden → 8) Docs