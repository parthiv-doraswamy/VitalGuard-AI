from fastapi import APIRouter, Query
from .alert_service import list_audit_for_alerts, list_alerts
from .storage import list_observations
from .timeline import build_patient_timeline

router = APIRouter(prefix="/api/v1/patients", tags=["patient-timeline"])

@router.get("/{patient_id}/timeline")
def patient_timeline(patient_id: str, limit: int = Query(default=50, ge=1, le=100)):
    """Return newest-first synthetic observations and alert lifecycle events."""
    observations = list_observations(patient_id=patient_id, limit=limit)
    alerts = list_alerts(patient_id=patient_id, limit=limit)
    audit_events = list_audit_for_alerts([alert["id"] for alert in alerts], limit=limit * 3)
    return build_patient_timeline(patient_id, observations, alerts, audit_events, limit=limit)
