from fastapi import APIRouter, Query
from .storage import list_observations
from .trends import summarize_observation_trends

router = APIRouter(prefix="/api/v1/observations", tags=["observation-trends"])

@router.get("/trends")
def observation_trends(patient_id: str = Query(min_length=1, max_length=64),
                       limit: int = Query(default=50, ge=2, le=100)):
    """Summarize recent stored observations for one fictional patient."""
    records = list_observations(patient_id=patient_id, limit=limit)
    return summarize_observation_trends(patient_id, records)
