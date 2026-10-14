"""HTTP endpoints for synthetic demo alert lifecycle."""
from typing import Literal
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from .alert_service import MAX_AUDIT_EVENTS, get_alert, list_alerts, list_alert_audit, transition_alert

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])

class AlertAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    actor: str = Field(default="demo-operator", min_length=1, max_length=120)

@router.get("")
def get_alerts(status: Literal["open", "acknowledged", "resolved"] | None = None,
               patient_id: str | None = Query(default=None, min_length=1, max_length=64),
               limit: int = Query(default=50, ge=1, le=100),
               before_id: int | None = Query(default=None, ge=1)):
    items = list_alerts(status=status, patient_id=patient_id, limit=limit, before_id=before_id)
    return {"items": items, "count": len(items), "limit": limit,
            "next_before_id": items[-1]["id"] if len(items) == limit else None,
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
def get_alert_audit(alert_id: int, limit: int = Query(default=100, ge=1, le=MAX_AUDIT_EVENTS)):
    if get_alert(alert_id) is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    items = list_alert_audit(alert_id, limit=limit)
    return {"items": items, "count": len(items), "demo_only": True}
