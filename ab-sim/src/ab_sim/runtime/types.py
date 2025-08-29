from dataclasses import dataclass, field
from enum import Enum


class Metric(Enum):
    EUCLIDEAN = "euclidean"
    MANHATTAN = "manhattan"


class Mode(Enum):
    IDEALIZED = "idealized"
    EMPIRICAL = "empirical"
    NETWORK = "network"


class SpeedSamplerKind(Enum):
    CONSTANT = "constant"
    GLOBAL = "global"
    DISTRIBUTION = "distribution"
    DOW_HOUR = "dow_hour"


@dataclass
class SimConfig:
    epoch: tuple[int, int, int, int, int, int]
    seed: int
    duration: int


@dataclass
class MechanicsConfig:
    mode: Mode = Mode.IDEALIZED
    seed: int = 123
    metric: Metric = Metric.EUCLIDEAN
    zones: list[tuple[float, float, float, float]] = field(
        default_factory=lambda: [(0, 0, 10_000, 10_000)]
    )
    zone_weights: list[float] | None = None
    shapefile_path: str | None = None
    graph_pickle_path: str | None = None
    speed_kind: SpeedSamplerKind = SpeedSamplerKind.CONSTANT
    base_mps: float = 8.94
    dist_name: str | None = None
    dist_params: dict[str, float] | None = None
    dow_hour_multiplier: dict[str, float] | None = None
    edge_factor: dict[int, float] | None = None
