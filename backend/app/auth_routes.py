"""Sign-in, current user, and role-filtered access to the fictional cohort."""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .auth import TOKEN_TTL_SECONDS, authenticate, current_user, ensure_patient_access, issue_token, require_roles
from .cohort import get_patient, patients_for, staff

router = APIRouter(prefix="/api/v1", tags=["auth"])


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=200)


@router.post("/auth/login")
def login(payload: LoginRequest):
    user = authenticate(payload.username, payload.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Unknown username or wrong password")
    return {"token": issue_token(user["username"]), "token_type": "bearer", "expires_in": TOKEN_TTL_SECONDS,
            "user": user, "demo_only": True}


@router.get("/auth/me")
def me(user: dict[str, Any] = Depends(current_user)):
    return {"user": user, "demo_only": True}


@router.get("/patients")
def list_patients(user: dict[str, Any] = Depends(current_user)):
    """Doctors receive only their assigned patients; nurses and admins the whole cohort."""
    items = patients_for(user["username"], user["role"])
    return {"items": items, "count": len(items), "scope": "assigned" if user["role"] == "doctor" else "all",
            "demo_only": True, "data_origin": "synthetic"}


@router.get("/patients/{patient_id}")
def patient_detail(patient_id: str, user: dict[str, Any] = Depends(current_user)):
    patient = get_patient(patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    ensure_patient_access(user, patient_id)
    return {"item": patient, "demo_only": True}


@router.get("/staff")
def list_staff(_user: dict[str, Any] = Depends(require_roles("admin"))):
    """Staff accounts and how many patients each doctor is assigned (admin only)."""
    items = []
    for member in staff():
        assigned = [patient["id"] for patient in patients_for(member["username"], member["role"])] \
            if member["role"] == "doctor" else []
        items.append({**{key: member[key] for key in ("username", "display_name", "role", "wards")},
                      "assigned_patients": assigned})
    return {"items": items, "count": len(items), "demo_only": True}
