"""Demo sign-in and role-based access control.

Accounts are the fictional staff in data/cohort.json (admin, nurse, doctors).
They share one demo password (VITALGUARD_DEMO_PASSWORD, default "demo-access"),
so this is access control for a demonstration, not production identity.

Tokens are `<base64url(json claims)>.<base64url(HMAC-SHA256)>` signed with
VITALGUARD_AUTH_SECRET. Without that variable a random per-process secret is
used: tokens then stop working after a restart and are not accepted by other
instances, which is logged once at startup.

Roles
- admin:  everything, including stream control, model performance and staff assignments.
- nurse:  whole cohort; may run the live stream and acknowledge alerts, not resolve them.
- doctor: only patients assigned to them; acknowledges and resolves their alerts and
          receives their patients' alerts as push notifications.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from typing import Any, Callable

from fastapi import Depends, Header, HTTPException

from .cohort import get_patient, get_staff

logger = logging.getLogger("vitalguard.auth")

ROLES = ("admin", "nurse", "doctor")
TOKEN_TTL_SECONDS = int(os.getenv("VITALGUARD_AUTH_TTL_SECONDS", str(12 * 3600)))
_EPHEMERAL_SECRET = secrets.token_bytes(32)
_warned = False


def _secret() -> bytes:
    global _warned
    configured = os.getenv("VITALGUARD_AUTH_SECRET", "").strip()
    if configured:
        return configured.encode()
    if not _warned:
        _warned = True
        logger.warning("VITALGUARD_AUTH_SECRET is not set; sign-ins last only until this process restarts")
    return _EPHEMERAL_SECRET


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _sign(body: str) -> str:
    return _b64(hmac.new(_secret(), body.encode(), hashlib.sha256).digest())


def public_user(member: dict[str, Any]) -> dict[str, Any]:
    return {"username": member["username"], "display_name": member["display_name"], "role": member["role"],
            "wards": list(member.get("wards", []))}


def issue_token(username: str, now: float | None = None) -> str:
    member = get_staff(username)
    if member is None:
        raise ValueError(f"Unknown user {username}")
    issued = int(now if now is not None else time.time())
    claims = {"sub": member["username"], "role": member["role"], "iat": issued, "exp": issued + TOKEN_TTL_SECONDS}
    body = _b64(json.dumps(claims, separators=(",", ":")).encode())
    return f"{body}.{_sign(body)}"


def verify_token(token: str, now: float | None = None) -> dict[str, Any] | None:
    """Return the signed-in user, or None if the token is malformed, forged, expired or for a removed user."""
    try:
        body, signature = token.split(".", 1)
        if not hmac.compare_digest(_sign(body), signature):
            return None
        claims = json.loads(_unb64(body))
    except (ValueError, json.JSONDecodeError):
        return None
    if not isinstance(claims, dict) or claims.get("exp", 0) < (now if now is not None else time.time()):
        return None
    member = get_staff(str(claims.get("sub", "")))
    # The role comes from the current staff list, so a changed role takes effect immediately.
    return public_user(member) if member else None


def authenticate(username: str, password: str) -> dict[str, Any] | None:
    expected = os.getenv("VITALGUARD_DEMO_PASSWORD", "demo-access")
    member = get_staff(username.strip().lower())
    # Compare even for unknown users so response time does not reveal which usernames exist.
    password_ok = hmac.compare_digest(password.encode(), expected.encode())
    return public_user(member) if member and password_ok else None


def _bearer(authorization: str | None) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip() or None
    return None


def optional_user(authorization: str | None = Header(default=None)) -> dict[str, Any] | None:
    token = _bearer(authorization)
    return verify_token(token) if token else None


def current_user(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    token = _bearer(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Sign in required", headers={"WWW-Authenticate": "Bearer"})
    user = verify_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Session expired or invalid; sign in again",
                            headers={"WWW-Authenticate": "Bearer"})
    return user


def require_roles(*roles: str) -> Callable[..., dict[str, Any]]:
    allowed = set(roles)

    def dependency(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
        if user["role"] not in allowed:
            raise HTTPException(status_code=403, detail=f"The {user['role']} role cannot perform this action")
        return user

    return dependency


def can_access_patient(user: dict[str, Any], patient_id: str) -> bool:
    """Doctors only reach their assigned patients; patients outside the cohort belong to nobody."""
    if user["role"] != "doctor":
        return True
    patient = get_patient(patient_id)
    return bool(patient) and patient["assigned_doctor"] == user["username"]


def ensure_patient_access(user: dict[str, Any], patient_id: str) -> None:
    if not can_access_patient(user, patient_id):
        raise HTTPException(status_code=403, detail="This patient is not assigned to you")
