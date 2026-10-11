"""Environment-backed identity bootstrap for the demo API.

This module establishes a minimal bearer-token identity endpoint. It does not
replace a managed identity provider or implement resource authorization; those
are explicit follow-up work. Keep this service synthetic-only until Phase 4.
"""
import hmac
import os
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from pydantic import BaseModel, ConfigDict, Field

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])
_bearer = HTTPBearer(auto_error=False)
ACCESS_TOKEN_TTL_SECONDS = 900


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=1024)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


def _credentials() -> tuple[str, str, str]:
    username = os.getenv("VITALGUARD_AUTH_USERNAME", "")
    password = os.getenv("VITALGUARD_AUTH_PASSWORD", "")
    secret = os.getenv("VITALGUARD_AUTH_SECRET", "")
    if not username or not password or len(secret) < 32:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured",
        )
    return username, password, secret


def _serializer(secret: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(secret_key=secret, salt="vitalguard-access-v1")


def authenticate_principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> dict[str, str]:
    """Validate an access token and return its authenticated subject."""
    _, _, secret = _credentials()
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Bearer token required",
                            headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = _serializer(secret).loads(
            credentials.credentials, max_age=ACCESS_TOKEN_TTL_SECONDS
        )
    except SignatureExpired:
        raise HTTPException(status_code=401, detail="Access token expired",
                            headers={"WWW-Authenticate": "Bearer"})
    except BadSignature:
        raise HTTPException(status_code=401, detail="Invalid access token",
                            headers={"WWW-Authenticate": "Bearer"})
    if not isinstance(payload, dict) or payload.get("type") != "access" or not isinstance(payload.get("sub"), str):
        raise HTTPException(status_code=401, detail="Invalid access token",
                            headers={"WWW-Authenticate": "Bearer"})
    configured_username, _, _ = _credentials()
    if not hmac.compare_digest(payload["sub"], configured_username):
        raise HTTPException(status_code=401, detail="Account is no longer valid",
                            headers={"WWW-Authenticate": "Bearer"})
    return {"sub": payload["sub"]}


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest) -> TokenResponse:
    """Issue a short-lived bearer token for the configured demo operator."""
    username, password, secret = _credentials()
    if not hmac.compare_digest(payload.username, username) or not hmac.compare_digest(payload.password, password):
        raise HTTPException(status_code=401, detail="Invalid username or password",
                            headers={"WWW-Authenticate": "Bearer"})
    token = _serializer(secret).dumps({"sub": username, "type": "access"})
    return TokenResponse(access_token=token, expires_in=ACCESS_TOKEN_TTL_SECONDS)


@router.get("/me")
def current_identity(principal: Annotated[dict[str, str], Depends(authenticate_principal)]):
    """Return the identity represented by the submitted valid access token."""
    return {"subject": principal["sub"], "authenticated": True}
