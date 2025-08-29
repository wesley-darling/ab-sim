# ab_sim/io/business_events.py

from dataclasses import dataclass
from typing import Literal


# Base type for analytics events (not scheduled in the kernel!)
@dataclass
class BizEvent:
    run_id: str
    t: float  # simulation time
    seq: int  # kernel dispatch sequence (for total ordering)
    name: str  # stable event name


# Domain events you’ll actually analyze
@dataclass
class TripRequestedBiz(BizEvent):
    rider_id: int
    pickup: tuple[float, float]
    dropoff: tuple[float, float]


@dataclass
class TripMatchedBiz(BizEvent):
    rider_id: int
    driver_id: int
    task_id: int
    eta_s: float | None = None
    distance_m: float | None = None
    score: float | None = None


@dataclass
class TripCanceledBiz(BizEvent):
    rider_id: int
    reason: Literal["user", "pickup_deadline", "wait_timeout", "policy", "other"]
    driver_id: int | None = None


@dataclass
class PickupArrivedBiz(BizEvent):
    rider_id: int
    driver_id: int


@dataclass
class TripBoardedBiz(BizEvent):
    rider_id: int
    driver_id: int
    wait_s: float | None = None


@dataclass
class DropoffArrivedBiz(BizEvent):
    rider_id: int
    driver_id: int


@dataclass
class TripCompletedBiz(BizEvent):
    rider_id: int
    driver_id: int
    in_vehicle_s: float | None = None
    total_s: float | None = None
    fare_cents: int | None = None
