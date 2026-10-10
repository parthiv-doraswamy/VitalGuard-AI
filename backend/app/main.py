from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .model import MODEL_VERSION, explain, predict_probability, risk_level
from .schemas import RiskPrediction, VitalInput

app = FastAPI(
    title="VitalGuard AI Risk Engine",
    version="0.1.0",
    description=(
        "Prototype API trained on generated synthetic observations. "
        "Not clinically validated and not for clinical use."
    ),
)

# Local development and the deployed Render frontend are allowed. Override
# with comma-separated origins in CORS_ORIGINS for other environments.
import os

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
        "features": [
            "age",
            "heart_rate",
            "spo2",
            "systolic_bp",
            "diastolic_bp",
            "temperature",
            "respiratory_rate",
        ],
        "training_data": "generated synthetic observations only",
        "demo_only": True,
        "clinically_validated": False,
    }


@app.post("/api/v1/risk/predict", response_model=RiskPrediction)
def predict(payload: VitalInput):
    values = payload.model_dump(exclude={"patient_id"})
    probability = predict_probability(values)
    score = round(probability * 100)
    return RiskPrediction(
        patient_id=payload.patient_id,
        risk_score=score,
        risk_level=risk_level(score),
        model_probability=round(probability, 4),
        factors=explain(values),
        model_version=MODEL_VERSION,
    )
