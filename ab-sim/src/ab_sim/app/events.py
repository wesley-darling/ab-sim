# app/events.py
from dataclasses import dataclass
from typing import Literal

from ab_sim.domain.entities.motion import Coord
from ab_sim.sim.event import BaseEvent

LegKind = Literal["pickup", "dropoff", "reposition"]


# Demand-side
@dataclass(order=True)
class RiderRequestPlaced(BaseEvent):
    rider_id: int
    pickup: Coord
    dropoff: Coord
    max_wait_s: float
    walk_s: float  # 0 for “already at pickup”


@dataclass(order=True)
class RiderTimeout(BaseEvent):
    rider_id: int


# Trip lifecycle
@dataclass(order=True)
class TripAssigned(BaseEvent):
    driver_id: int
    rider_id: int
    task_id: int  # versioning to make stale events harmless


@dataclass(order=True)
class DriverLegArrive(BaseEvent):
    driver_id: int
    rider_id: int | None
    kind: LegKind
    task_id: int


# Rendezvous & guards
@dataclass(order=True)
class RiderArrivePickup(BaseEvent):
    rider_id: int


@dataclass(order=True)
class BoardingStarted(BaseEvent):
    rider_id: int
    driver_id: int
    task_id: int


@dataclass(order=True)
class BoardingComplete(BaseEvent):
    rider_id: int
    driver_id: int
    task_id: int


@dataclass(order=True)
class PickupDeadline(BaseEvent):
    rider_id: int


@dataclass(order=True)
class DriverWaitTimeout(BaseEvent):
    driver_id: int
    task_id: int


@dataclass(order=True)
class DriverIdleTimeout(BaseEvent):
    driver_id: int
    task_id: int


# Observability
@dataclass(order=True)
class TripBoarded(BaseEvent):
    rider_id: int
    driver_id: int


@dataclass(order=True)
class TripCompleted(BaseEvent):
    rider_id: int
    driver_id: int


@dataclass(order=True)
class AlightingStarted(BaseEvent):
    rider_id: int
    driver_id: int
    task_id: int


@dataclass(order=True)
class AlightingComplete(BaseEvent):
    rider_id: int
    driver_id: int
    task_id: int


@dataclass(order=True)
class RiderCancel(BaseEvent):
    rider_id: int
    reason: str | None = None


@dataclass(order=True)
class RiderRequeue(BaseEvent):
    rider_id: int


@dataclass(order=True)
class DriverCancel(BaseEvent):
    driver_id: int
    reason: str | None = None
    task_id: int | None = None


@dataclass(order=True)
class DriverAvailable(BaseEvent):
    driver_id: int


@dataclass(order=True)
class DriverStartShift(BaseEvent):
    driver_id: int
    loc: Coord


# logging
@dataclass(order=True)
class EndOfDay(BaseEvent):
    day_index: int
    task_id: int
