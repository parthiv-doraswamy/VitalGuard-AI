from contextlib import asynccontextmanager
import os
import uuid
from fastapi import FastAPI, Query, WebSocket, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from starlette.requests import Request
from .model import MODEL_VERSION, explain, predict_probability, risk_level
from .model_evaluation import coefficient_contributions, evaluate_synthetic_holdout
from .news2 import score_news2
from .schemas import NEWS2Input, RiskPrediction, VitalInput
from .simulator_routes import router as simulator_router
from .timeline_routes import router as timeline_router
from .trend_routes import router as trend_router
from .alert_routes import router as alert_router
from .alert_service import create_alert
from .data_quality import assess_observations
from .live_events import hub
from .storage import database_health, initialize_storage, list_observations, save_observation
from .auth import router as auth_router, authenticate_principal
from .ingestion_routes import router as ingestion_router

@asynccontextmanager
async def lifespan(_app: FastAPI):
    initialize_storage()
    yield

app = FastAPI(title="VitalGuard AI Risk Engine", version="0.8.0",
    description="Synthetic demo risk API. Not clinically validated and not for clinical use.", lifespan=lifespan)
app.include_router(auth_router)
app.include_router(ingestion_router)
app.include_router(simulator_router)
app.include_router(alert_router)
app.include_router(timeline_router)
app.include_router(trend_router)
_default_origins = ["http://localhost:5173", "http://127.0.0.1:5173", "https://vitalguard-ai-g215.onrender.com"]
_origins = os.getenv("CORS_ORIGINS", ",".join(_default_origins))
app.add_middleware(CORSMiddleware, allow_origins=[origin.strip() for origin in _origins.split(",") if origin.strip()],
    allow_credentials=False, allow_methods=["GET", "POST", "OPTIONS"], allow_headers=["Content-Type", "Authorization"])

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Attach baseline response headers and a server-generated request ID."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Request-ID"] = str(uuid.uuid4())
    return response

async def _publish_observation(patient_id: str, values: dict, result: RiskPrediction, saved: dict) -> None:
    await hub.broadcast({"type": "observation.created", "event_id": saved["id"],
        "patient_id": patient_id, "created_at": saved["created_at"], "observation": values,
        "prediction": result.model_dump(), "demo_only": True})

def _maybe_create_alert(patient_id: str, score: int, level: str, observation_id: int, values: dict):
    if score < 65:
        return None
    return create_alert(patient_id=patient_id, event_key=f"observation:{observation_id}:elevated-risk",
        severity="critical" if level == "critical" else "high", title=f"{level.title()} demo risk score",
        details={"observation_id": observation_id, "risk_score": score, "risk_level": level, "vitals": values, "demo_only": True})

@app.get("/")
def root():
    return {"service": "VitalGuard AI Risk Engine", "status": "ok", "docs": "/docs", "health": "/health", "demo_only": True}

@app.get("/health")
def health():
    try:
        database = database_health()
        return {"status": "ok", "model_version": MODEL_VERSION, "database": database, "websocket": "available", "demo_only": True}
    except Exception:
        raise HTTPException(status_code=503, detail="Database health check failed")

@app.websocket("/api/v1/live")
async def live_socket(websocket: WebSocket, token: str | None = Query(default=None)):
    from .auth import validate_access_token
    try:
        validate_access_token(token)
    except HTTPException:
        await websocket.close(code=1008, reason="Authentication required")
        return
    await hub.serve(websocket)

@app.get("/api/v1/model/info")
def model_info(principal: dict = Depends(authenticate_principal)):
    return {"name": "VitalGuard synthetic risk classifier", "model_version": MODEL_VERSION,
        "algorithm": "StandardScaler + LogisticRegression",
        "features": ["age", "heart_rate", "spo2", "systolic_bp", "diastolic_bp", "temperature", "respiratory_rate"],
        "training_data": "generated synthetic observations only", "demo_only": True, "clinically_validated": False}

@app.post("/api/v1/scores/news2")
def calculate_news2(payload: NEWS2Input, principal: dict = Depends(authenticate_principal)):
    """Calculate parameter points for a fictional NEWS2 example; not clinical guidance."""
    return score_news2(payload.model_dump(exclude={"patient_id", "scale2_authorized"}))

@app.get("/api/v1/model/evaluation")
def model_evaluation(principal: dict = Depends(authenticate_principal)):
    return evaluate_synthetic_holdout()

@app.post("/api/v1/risk/predict", response_model=RiskPrediction)
async def predict(payload: VitalInput, principal: dict = Depends(authenticate_principal)):
    values = payload.model_dump(exclude={"patient_id"})
    probability = predict_probability(values)
    score = round(probability * 100)
    level = risk_level(score)
    result = RiskPrediction(patient_id=payload.patient_id, risk_score=score, risk_level=level,
        model_probability=round(probability, 4), factors=explain(values), model_version=MODEL_VERSION)
    saved = save_observation(payload.patient_id, values, result.model_dump())
    response = result.model_copy(update={"observation_id": saved["id"], "created_at": saved["created_at"]})
    await _publish_observation(payload.patient_id, values, response, saved)
    alert = _maybe_create_alert(payload.patient_id, score, level, saved["id"], values)
    if alert:
        await hub.broadcast({"type": "alert.created", "event_id": alert["id"], "alert": alert, "demo_only": True})
    return response

@app.post("/api/v1/risk/explain")
def explain_risk(payload: VitalInput, principal: dict = Depends(authenticate_principal)):
    values = payload.model_dump(exclude={"patient_id"})
    return {"patient_id": payload.patient_id, "model_version": MODEL_VERSION,
        "risk_score": round(predict_probability(values) * 100),
        "contributions": coefficient_contributions(values),
        "method": "standardized logistic-regression coefficient contributions",
        "caveat": "These are model contributions, not causal explanations or clinical guidance.",
        "demo_only": True}

@app.get("/api/v1/observations")
def observation_history(patient_id: str | None = Query(default=None, min_length=1, max_length=64),
    limit: int = Query(default=50, ge=1, le=100), before_id: int | None = Query(default=None, ge=1), principal: dict = Depends(authenticate_principal)):
    records = list_observations(patient_id=patient_id, limit=limit, before_id=before_id)
    next_cursor = records[-1]["id"] if len(records) == limit else None
    return {"items": records, "count": len(records), "limit": limit, "next_before_id": next_cursor,
        "demo_only": True, "disclaimer": "Synthetic demonstration records only; not for clinical use."}

@app.get("/api/v1/observations/quality")
def observation_quality(stale_after_seconds: int = Query(default=300, ge=30, le=86400),
    limit: int = Query(default=100, ge=1, le=100), principal: dict = Depends(authenticate_principal)):
    records = list_observations(limit=limit)
    return assess_observations(records, stale_after_seconds=stale_after_seconds)
