from contextlib import asynccontextmanager
import os

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from .model import MODEL_VERSION, explain, predict_probability, risk_level
from .schemas import RiskPrediction, VitalInput
from .storage import initialize_storage, list_observations, save_observation


@asynccontextmanager
async def lifespan(_app: FastAPI):
    initialize_storage()
    yield


app = FastAPI(
    title="VitalGuard AI Risk Engine",
    version="0.2.0",
    description="Prototype API trained on generated synthetic observations. Not clinically validated and not for clinical use.",
    lifespan=lifespan,
)

_default_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://vitalguard-ai-g215.onrender.com",
]
_origins = os.getenv("CORS_ORIGINS", ",".join(_default_origins))
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in _origins.split(",") if origin.strip()],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


@app.get("/health")
def health():
    return {"status": "ok", "model_version": MODEL_VERSION, "demo_only": True}


@app.get("/api/v1/model/info")
def model_info():
    return {
        "name": "VitalGuard synthetic risk classifier",
        "model_version": MODEL_VERSION,
        "algorithm": "StandardScaler + LogisticRegression",
        "features": ["age", "heart_rate", "spo2", "systolic_bp", "diastolic_bp", "temperature", "respiratory_rate"],
        "training_data": "generated synthetic observations only",
        "demo_only": True,
        "clinically_validated": False,
    }


@app.post("/api/v1/risk/predict", response_model=RiskPrediction)
def predict(payload: VitalInput):
    values = payload.model_dump(exclude={"patient_id"})
    probability = predict_probability(values)
    score = round(probability * 100)
    result = RiskPrediction(
        patient_id=payload.patient_id,
        risk_score=score,
        risk_level=risk_level(score),
        model_probability=round(probability, 4),
        factors=explain(values),
        model_version=MODEL_VERSION,
    )
    saved = save_observation(payload.patient_id, values, result.model_dump())
    return result.model_copy(update={"observation_id": saved["id"], "created_at": saved["created_at"]})


@app.get("/api/v1/observations")
def observation_history(
    patient_id: str | None = Query(default=None, min_length=1, max_length=64),
    limit: int = Query(default=50, ge=1, le=100),
    before_id: int | None = Query(default=None, ge=1),
):
    """Return recent saved demo predictions, optionally filtered by demo patient ID."""
    records = list_observations(patient_id=patient_id, limit=limit, before_id=before_id)
    next_cursor = records[-1]["id"] if len(records) == limit else None
    return {
        "items": records,
        "count": len(records),
        "limit": limit,
        "next_before_id": next_cursor,
        "demo_only": True,
        "disclaimer": "Synthetic demonstration records only; not for clinical use.",
    }
