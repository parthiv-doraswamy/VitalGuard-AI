"""HTTP endpoints for synthetic demo alert lifecycle."""
from typing import Literal
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, ConfigDict, Field
from .alert_service import list_alerts, list_alert_audit, transition_alert\nfrom .auth import authenticate_principal

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"], dependencies=[Depends(authenticate_principal)])

class AlertAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    actor: str = Field(default="demo-operator", min_length=1, max_length=120)

@router.get("")
def get_alerts(status: Literal["open", "acknowledged", "resolved"] | None = None,
               patient_id: str | None = Query(default=None, min_length=1, max_length=64),
               limit: int = Query(default=50, ge=1, le=100)):
    return {"items": list_alerts(status=status, patient_id=patient_id, limit=limit),
            "count": len(list_alerts(status=status, patient_id=patient_id, limit=limit)),
            "demo_only": True}

@router.post("/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: int, payload: AlertAction):
    result = transition_alert(alert_id, "acknowledge", payload.actor)
    if result is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"item": result, "demo_only": True}

@router.post("/{alert_id}/resolve")
def resolve_alert(alert_id: int, payload: AlertAction):
    result = transition_alert(alert_id, "resolve", payload.actor)
    if result is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"item": result, "demo_only": True}

@router.get("/{alert_id}/audit")
def get_alert_audit(alert_id: int):
    items = list_alert_audit(alert_id)
    if not items:
        # No audit rows also means the alert might not exist.
        if not any(item["id"] == alert_id for item in list_alerts(limit=100)):
            raise HTTPException(status_code=404, detail="Alert not found")
    return {"items": items, "count": len(items), "demo_only": True}
