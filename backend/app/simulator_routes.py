"""Demo-only API for submitting deterministic synthetic observations."""
from typing import Literal
from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field
from .model import MODEL_VERSION, explain, predict_probability, risk_level
from .schemas import RiskPrediction
from .simulator import observation_for_step
from .storage import save_observation

router = APIRouter(prefix="/api/v1/demo", tags=["demo-simulator"])

class SimulationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    patient_id: str = Field(default="DEMO-LIVE-001", min_length=1, max_length=64)
    scenario: Literal["stable", "worsening", "recovering"] = "stable"
    step: int = Field(default=0, ge=0, le=1000)

@router.post("/observations", response_model=RiskPrediction)
def submit_demo_observation(payload: SimulationRequest):
    """Generate, score, and persist one fictional observation; each POST is new."""
    values = observation_for_step(payload.scenario, payload.step)
    probability = predict_probability(values)
    score = round(probability * 100)
    result = RiskPrediction(patient_id=payload.patient_id, risk_score=score,
        risk_level=risk_level(score), model_probability=round(probability, 4),
        factors=explain(values), model_version=MODEL_VERSION)
    saved = save_observation(payload.patient_id, values, result.model_dump())
    return result.model_copy(update={"observation_id": saved["id"], "created_at": saved["created_at"]})
