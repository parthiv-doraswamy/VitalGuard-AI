from contextlib import asynccontextmanager
import os
from fastapi import FastAPI, Query, WebSocket, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .model import MODEL_VERSION, explain, predict_probability, risk_level
from .schemas import RiskPrediction, VitalInput
from .simulator_routes import router as simulator_router
from .alert_routes import router as alert_router
from .alert_service import create_alert
from .live_events import hub
from .storage import database_health, initialize_storage, list_observations, save_observation

@asynccontextmanager
async def lifespan(_app: FastAPI):
    initialize_storage()
    yield

app = FastAPI(title="VitalGuard AI Risk Engine", version="0.6.0",
    description="Synthetic demo risk API. Not clinically validated and not for clinical use.", lifespan=lifespan)
app.include_router(simulator_router)
app.include_router(alert_router)
_default_origins = ["http://localhost:5173", "http://127.0.0.1:5173", "https://vitalguard-ai-g215.onrender.com"]
_origins = os.getenv("CORS_ORIGINS", ",".join(_default_origins))
app.add_middleware(CORSMiddleware, allow_origins=[origin.strip() for origin in _origins.split(",") if origin.strip()],
    allow_credentials=False, allow_methods=["GET", "POST", "OPTIONS"], allow_headers=["Content-Type"])

async def _publish_observation(patient_id: str, values: dict, result: RiskPrediction, saved: dict) -> None:
    await hub.broadcast({
        "type": "observation.created",
        "event_id": saved["id"],
        "patient_id": patient_id,
        "created_at": saved["created_at"],
        "observation": values,
        "prediction": result.model_dump(),
        "demo_only": True,
    })

def _maybe_create_alert(patient_id: str, score: int, level: str, observation_id: int, values: dict) -> dict | None:
    # Demo threshold only. Not a validated clinical alarm rule.
    if score < 65:
        return None
    alert = create_alert(
        patient_id=patient_id,
        event_key=f"observation:{observation_id}:elevated-risk",
        severity="critical" if level == "critical" else "high",
        title=f"{level.title()} demo risk score",
        details={"observation_id": observation_id, "risk_score": score, "risk_level": level,
                 "vitals": values, "demo_only": True},
    )
    return alert

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
async def live_socket(websocket: WebSocket):
    await hub.serve(websocket)

@app.get("/api/v1/model/info")
def model_info():
    return {"name": "VitalGuard synthetic risk classifier", "model_version": MODEL_VERSION,
        "algorithm": "StandardScaler + LogisticRegression",
        "features": ["age", "heart_rate", "spo2", "systolic_bp", "diastolic_bp", "temperature", "respiratory_rate"],
        "training_data": "generated synthetic observations only", "demo_only": True, "clinically_validated": False}

@app.post("/api/v1/risk/predict", response_model=RiskPrediction)
async def predict(payload: VitalInput):
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

@app.get("/api/v1/observations")
def observation_history(patient_id: str | None = Query(default=None, min_length=1, max_length=64),
    limit: int = Query(default=50, ge=1, le=100), before_id: int | None = Query(default=None, ge=1)):
    records = list_observations(patient_id=patient_id, limit=limit, before_id=before_id)
    next_cursor = records[-1]["id"] if len(records) == limit else None
    return {"items": records, "count": len(records), "limit": limit, "next_before_id": next_cursor,
        "demo_only": True, "disclaimer": "Synthetic demonstration records only; not for clinical use."}
