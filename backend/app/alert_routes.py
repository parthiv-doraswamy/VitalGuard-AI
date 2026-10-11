"""HTTP endpoints for synthetic demo alert lifecycle."""
from typing import Literal
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, ConfigDict, Field
from .alert_service import list_alerts, list_alert_audit, transition_alert
from .auth import authenticate_principal
from .escalation_policy import evaluate_escalation

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

@router.get("/escalation-preview")
def get_escalation_preview(limit: int = Query(default=100, ge=1, le=100)):
    """Preview overdue synthetic alerts; this endpoint never sends notifications."""
    items = list_alerts(status="open", limit=limit)
    previews = [evaluate_escalation(item) for item in items]
    due = [item for item in previews if item["review_due"]]
    return {
        "items": previews,
        "count": len(previews),
        "due_count": len(due),
        "policy_version": previews[0]["policy_version"] if previews else "demo-escalation-policy-0.1.0",
        "demo_only": True,
        "notifications_sent": False,
        "clinical_policy": False,
    }

@router.post("/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: int, payload: AlertAction, principal: dict = Depends(authenticate_principal)):
    result = transition_alert(alert_id, "acknowledge", principal["sub"])
    if result is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"item": result, "demo_only": True}

@router.post("/{alert_id}/resolve")
def resolve_alert(alert_id: int, payload: AlertAction, principal: dict = Depends(authenticate_principal)):
    result = transition_alert(alert_id, "resolve", principal["sub"])
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
