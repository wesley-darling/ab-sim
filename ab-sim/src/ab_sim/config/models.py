import os
from math import isfinite
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator


class SimModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    epoch: tuple[int, int, int, int, int, int]
    seed: int
    duration: int  # seconds


class LogModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    debug: bool = False
    sample_every: int = 1


class WorldModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    capacity: int = 4
    geo: dict[str, float] | dict[str, int] | dict[str, str] = Field(default_factory=dict)


# ----------------- MECHANICS ---------------------


class SpeedSamplerGlobalModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["global"] = "global"
    v_mps: float = 8.94


class SpeedSamplerConstantModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["constant"] = "constant"
    pickup_mps: float = 8.94
    dropoff_mps: float = 8.94


class SpeedSamplerDistributionModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["distribution"] = "distribution"
    dist: Literal["lognormal", "gamma"]
    params: dict[str, float] = Field(default_factory=dict)
    fallback_mps: float = 8.94


class SpeedSamplerEdgeAwareModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["edge_aware"] = "edge_aware"
    base_mps: float = 8.94
    tfac: dict[str, float] = Field(default_factory=dict)  # "dow:hour" -> factor
    efac: dict[int, float] = Field(default_factory=dict)  # edge_id -> factor


SpeedSamplerUnion = Annotated[
    SpeedSamplerGlobalModel
    | SpeedSamplerConstantModel
    | SpeedSamplerDistributionModel
    | SpeedSamplerEdgeAwareModel,
    Field(discriminator="kind"),
]

# --------------------- OD Samplers -------------------------


class ODSamplerIdealizedModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["idealized"] = "idealized"
    zones: list[tuple[float, float, float, float]] = Field(
        default_factory=lambda: [(0, 0, 10_000, 10_000)]
    )
    weights: list[float] | None = None

    @field_validator("weights", mode="before")
    @classmethod
    def _empty_to_none(cls, v):
        # YAML [] or "" should mean "uniform"
        if v is None:
            return None
        if isinstance(v | (list, tuple)) and len(v) == 0:
            return None
        return v

    @model_validator(mode="after")
    def _check_weights(self):
        if self.weights is None:
            return self
        n = len(self.zones)
        w = self.weights
        if len(w) != n:
            raise ValueError(f"zone_weights must have length {n}, got {len(w)}")
        # reject NaN/Inf and non-positive sums early (friendlier than numpy error)
        if any((not isinstance(x | (int, float))) or (not isfinite(float(x))) for x in w):
            raise ValueError("zone_weights must be finite")
        if sum(float(x) for x in w) <= 0:
            raise ValueError("zone_weights must sum to a positive value")
        return self


class ODSamplerEmpiricalModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["empirical"] = "empirical"
    sampler: str


class GraphByPath(BaseModel):
    model_config = ConfigDict(extra="forbid")
    by: Literal["path"] = "path"
    file: str
    fmt: Literal["pickle", "graphml", "parquet"] = "pickle"
    must_exist: bool = True

    @field_validator("file")
    @classmethod
    def _expand(cls, v: str) -> str:
        return os.path.expandvars(os.path.expanduser(v))


class GraphByName(BaseModel):
    model_config = ConfigDict(extra="forbid")
    by: Literal["name"] = "name"
    name: str


GraphRef = Annotated[GraphByPath | GraphByName, Field(discriminator="by")]


class ODSamplerNetworkModel(BaseModel):
    kind: Literal["network"] = "network"
    graph: GraphRef


ODUnion = Annotated[
    ODSamplerIdealizedModel | ODSamplerEmpiricalModel | ODSamplerNetworkModel,
    Field(discriminator="kind"),
]

# ----------------- ROUTE PLANNERS ---------------------


class RoutePlannerEuclideanModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["euclidean"] = "euclidean"


class RoutePlannerManhattanModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["manhattan"] = "manhattan"


class RoutePlannerNetworkModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["network"] = "network"
    graph: GraphByPath
    vmax_mps: float = 16.7


RoutePlannerUnion = Annotated[
    RoutePlannerEuclideanModel | RoutePlannerManhattanModel | RoutePlannerNetworkModel,
    Field(discriminator="kind"),
]

# ----------------- PATH TRAVERSERS ---------------------


class PathTraverserPiecewiseConstModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["piecewise_const"] = "piecewise_const"


PathTraverserUnion = Annotated[PathTraverserPiecewiseConstModel, Field(discriminator="kind")]


# ------------------ SERVICES -----------------------------


class TravelTimeServiceMechanicsModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["mechanics"] = "mechanics"
    # Optional switches if you later add a traverser/ETA path:
    method: Literal["distance_over_speed", "router_eta"] = "distance_over_speed"
    min_speed_mps: float = 0.1  # clamp to avoid div by 0


class TravelTimeServiceFixedModel(BaseModel):
    """Test stub with fixed durations."""

    model_config = ConfigDict(extra="forbid")
    kind: Literal["fixed"] = "fixed"
    pickup_s: float = 10.0
    dropoff_s: float = 20.0
    reposition_s: float = 30.0

    @field_validator("pickup_s", "dropoff_s", "reposition_s")
    def _nonneg(cls, v: float, info: ValidationInfo) -> float:
        if v < 0:
            raise ValueError(f"{info.field_name} must be >= 0")
        return v


TravelTimeUnion = Annotated[
    TravelTimeServiceMechanicsModel | TravelTimeServiceFixedModel, Field(discriminator="kind")
]


# ------------------ POLICIES -----------------------------


class DwellPolicyExpBoardAlightModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["exponential_board_alight"] = "exponential_board_alight"  # examples
    board_mean_s: float = 7.0
    alight_mean_s: float = 5.0


DwellPolicyUnion = Annotated[DwellPolicyExpBoardAlightModel, Field(discriminator="kind")]


class IdlePolicyCirculatingModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["circulating"] = "circulating"  # examples
    dwell_s: float = 0.0
    continual_reposition: bool = False


IdlePolicyUnion = Annotated[IdlePolicyCirculatingModel, Field(discriminator="kind")]


class MatchingPolicyNearestAssignModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["nearest_assign"] = "nearest_assign"  # examples


MatchingPolicyUnion = Annotated[MatchingPolicyNearestAssignModel, Field(discriminator="kind")]


class PricingPolicyConstantModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["constant"] = "constant"  # examples
    fare: float = 0.0


PricingPolicyUnion = Annotated[PricingPolicyConstantModel, Field(discriminator="kind")]


# ------------------------------------------------------------------


class MechanicsModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    seed: int = 123

    od_sampler: ODUnion = Field(default_factory=ODSamplerIdealizedModel)
    speed_sampler: SpeedSamplerUnion = Field(default_factory=SpeedSamplerGlobalModel)
    route_planner: RoutePlannerUnion = Field(default_factory=RoutePlannerManhattanModel)
    path_traverser: PathTraverserUnion = Field(default_factory=PathTraverserPiecewiseConstModel)


class ScenarioModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    run_id: str
    sim: SimModel
    log: LogModel = LogModel()
    world: WorldModel = WorldModel()
    travel_time: TravelTimeUnion = Field(default_factory=TravelTimeServiceFixedModel)
    mechanics: MechanicsModel
    idle: IdlePolicyUnion = Field(default_factory=IdlePolicyCirculatingModel)
    matching: MatchingPolicyUnion = Field(default_factory=MatchingPolicyNearestAssignModel)
    dwell: DwellPolicyUnion = Field(default_factory=DwellPolicyExpBoardAlightModel)
    pricing: PricingPolicyUnion = Field(default_factory=PricingPolicyConstantModel)
