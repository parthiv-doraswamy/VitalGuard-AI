from fastapi import APIRouter, Query, Depends
from .alert_service import list_alert_audit, list_alerts
from .storage import list_observations
from .timeline import build_patient_timeline
from .auth import authenticate_principal

router = APIRouter(prefix="/api/v1/patients", tags=["patient-timeline"], dependencies=[Depends(authenticate_principal)])

@router.get("/{patient_id}/timeline")
def patient_timeline(patient_id: str, limit: int = Query(default=50, ge=1, le=100)):
    """Return newest-first synthetic observations and alert lifecycle events."""
    observations = list_observations(patient_id=patient_id, limit=limit)
    alerts = list_alerts(patient_id=patient_id, limit=limit)
    audit_events = []
    for alert in alerts:
        audit_events.extend(list_alert_audit(alert["id"]))
    return build_patient_timeline(patient_id, observations, alerts, audit_events, limit=limit)
