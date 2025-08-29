# src/ab_sim/io/config.py


from pydantic import BaseModel, Field

from ab_sim.domain.mechanics.mechanics_factory import MechanicsConfig


class ScenarioConfig(BaseModel):
    # ... existing fields (demand, fleet, pricing, etc.)
    mechanics: MechanicsConfig = Field(default_factory=MechanicsConfig)
