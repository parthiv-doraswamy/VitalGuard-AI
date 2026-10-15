"""HTTP endpoints for synthetic demo alert lifecycle."""
from typing import Any, Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool
from .event_broker import events
from .alert_service import MAX_AUDIT_EVENTS, get_alert, list_alerts, list_alert_audit, transition_alert
from .auth import current_user, ensure_patient_access
from .cohort import patients_for
from .escalation_policy import POLICY_VERSION, authenticate_escalation_preview, evaluate_escalation

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])

class AlertAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # Accepted for backward compatibility; the audit trail records the signed-in user instead.
    actor: str = Field(default="demo-operator", min_length=1, max_length=120)

# Who may move an alert to each state. Doctors are further limited to their assigned patients.
ACTION_ROLES = {"acknowledge": {"admin", "nurse", "doctor"}, "resolve": {"admin", "doctor"}}

@router.get("")
def get_alerts(status: Literal["open", "acknowledged", "resolved"] | None = None,
               patient_id: str | None = Query(default=None, min_length=1, max_length=64),
               limit: int = Query(default=50, ge=1, le=100),
               before_id: int | None = Query(default=None, ge=1),
               user: dict[str, Any] = Depends(current_user)):
    if patient_id:
        ensure_patient_access(user, patient_id)
    # Doctors see only alerts for their assigned patients.
    allowed = {item["id"] for item in patients_for(user["username"], user["role"])} \
        if user["role"] == "doctor" else None
    items = list_alerts(status=status, patient_id=patient_id, limit=limit, before_id=before_id, patient_ids=allowed)
    return {"items": items, "count": len(items), "limit": limit,
            "next_before_id": items[-1]["id"] if len(items) == limit else None,
            "demo_only": True}

async def _transition(alert_id: int, action: str, user: dict[str, Any]):
    if user["role"] not in ACTION_ROLES[action]:
        raise HTTPException(status_code=403, detail=f"The {user['role']} role cannot {action} alerts")
    existing = await run_in_threadpool(get_alert, alert_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    ensure_patient_access(user, existing["patient_id"])
    result = await run_in_threadpool(transition_alert, alert_id, action, user["username"])
    if result is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    # An alert.updated event was written to the outbox if the state changed.
    await events.after_commit()
    return {"item": result, "demo_only": True}

@router.get("/escalation-preview")
def get_escalation_preview(
    limit: int = Query(default=100, ge=1, le=100),
    _principal: dict[str, str] = Depends(authenticate_escalation_preview),
):
    """Preview due synthetic alert reviews; authentication is required and no notifications are sent."""
    previews = [evaluate_escalation(item) for item in list_alerts(status="open", limit=limit)]
    due_count = sum(1 for item in previews if item["review_due"])
    return {
        "items": previews,
        "count": len(previews),
        "due_count": due_count,
        "policy_version": POLICY_VERSION,
        "demo_only": True,
        "notifications_sent": False,
        "clinical_policy": False,
        "disclaimer": "Illustrative engineering deadlines only; not clinical guidance.",
    }


@router.post("/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: int, _payload: AlertAction, user: dict[str, Any] = Depends(current_user)):
    return await _transition(alert_id, "acknowledge", user)

@router.post("/{alert_id}/resolve")
async def resolve_alert(alert_id: int, _payload: AlertAction, user: dict[str, Any] = Depends(current_user)):
    return await _transition(alert_id, "resolve", user)

@router.get("/{alert_id}/audit")
def get_alert_audit(alert_id: int, limit: int = Query(default=100, ge=1, le=MAX_AUDIT_EVENTS),
                    user: dict[str, Any] = Depends(current_user)):
    alert = get_alert(alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    ensure_patient_access(user, alert["patient_id"])
    items = list_alert_audit(alert_id, limit=limit)
    return {"items": items, "count": len(items), "demo_only": True}
