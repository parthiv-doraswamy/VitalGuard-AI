"""Demo-only API for submitting deterministic synthetic observations."""
from typing import Literal
from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field
from .observation_service import record_observation
from .schemas import RiskPrediction
from .simulator import observation_for_step

router = APIRouter(prefix="/api/v1/demo", tags=["demo-simulator"])

class SimulationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    patient_id: str = Field(default="DEMO-LIVE-001", min_length=1, max_length=64)
    scenario: Literal["stable", "worsening", "recovering"] = "stable"
    step: int = Field(default=0, ge=0, le=1000)

@router.post("/observations", response_model=RiskPrediction)
async def submit_demo_observation(payload: SimulationRequest):
    """Generate, score, persist, then broadcast one fictional observation."""
    values = observation_for_step(payload.scenario, payload.step)
    # The simulator has never raised alerts; that behavior is kept unchanged.
    return await record_observation(payload.patient_id, values, raise_alert=False)
