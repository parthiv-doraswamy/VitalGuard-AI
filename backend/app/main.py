from contextlib import asynccontextmanager
import logging
import os
import uuid
from fastapi import FastAPI, Query, WebSocket, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.requests import Request
from .model import MODEL_VERSION, predict_probability
from .model_evaluation import coefficient_contributions, evaluate_synthetic_holdout
from .news2 import score_news2
from .schemas import NEWS2Input, RiskPrediction, VitalInput
from .simulator_routes import live_router, router as simulator_router
from .stream_service import StreamError
from .timeline_routes import router as timeline_router
from .trend_routes import router as trend_router
from .alert_routes import router as alert_router
from .data_quality import assess_observations
from .live_events import hub
from .observation_service import record_observation
from .storage import database_health, dispose_engines, initialize_storage, list_observations

logger = logging.getLogger("vitalguard.api")

@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Fails startup (no traffic served) if the database is unreachable or not the required backend.
    initialize_storage()
    try:
        yield
    finally:
        dispose_engines()

app = FastAPI(title="VitalGuard AI Risk Engine", version="0.8.0",
    description="Synthetic demo risk API. Not clinically validated and not for clinical use.", lifespan=lifespan)
app.include_router(simulator_router)
app.include_router(live_router)
app.include_router(alert_router)
app.include_router(timeline_router)
app.include_router(trend_router)
_default_origins = ["http://localhost:5173", "http://127.0.0.1:5173", "https://vitalguard-ai-g215.onrender.com"]
_origins = os.getenv("CORS_ORIGINS", ",".join(_default_origins))
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in _origins.split(",") if origin.strip()],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    # Frontend API requests can carry the demo bearer token. Browsers preflight
    # those POSTs; omitting Authorization makes the browser reject them before
    # the request reaches the API.
    allow_headers=["Accept", "Authorization", "Content-Type", "X-Producer-Token", "X-Demo-Producer-Key"],
)

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

@app.exception_handler(SQLAlchemyError)
async def database_error(request: Request, exc: SQLAlchemyError):
    """Report database failures as 503 instead of an unhandled 500 or a fake success.

    Writes run in a transaction, so a failure here means nothing was committed.
    The exception is logged server-side; connection details are never returned.
    """
    logger.error("Database operation failed for %s %s: %s", request.method, request.url.path, type(exc).__name__)
    return JSONResponse(status_code=503, content={"detail": "Database unavailable; the request was not saved.",
        "error": "database_unavailable", "demo_only": True})

@app.exception_handler(StreamError)
async def stream_error(_request: Request, exc: StreamError):
    return JSONResponse(status_code=exc.status_code,
        content={"detail": exc.detail, "error": exc.code, **exc.extra, "demo_only": True})

@app.get("/")
def root():
    return {"service": "VitalGuard AI Risk Engine", "status": "ok", "docs": "/docs", "health": "/health", "demo_only": True}

@app.get("/health")
def health():
    try:
        database = database_health()
    except Exception as exc:
        logger.error("Database health check failed: %s", type(exc).__name__)
        raise HTTPException(status_code=503, detail="Database health check failed")
    return {"status": "ok" if database["status"] == "ok" else "degraded", "model_version": MODEL_VERSION,
        "database": database, "websocket": "available", "demo_only": True}

@app.websocket("/api/v1/live")
async def live_socket(websocket: WebSocket):
    await hub.serve(websocket)

@app.get("/api/v1/model/info")
def model_info():
    return {"name": "VitalGuard synthetic risk classifier", "model_version": MODEL_VERSION,
        "algorithm": "StandardScaler + LogisticRegression",
        "features": ["age", "heart_rate", "spo2", "systolic_bp", "diastolic_bp", "temperature", "respiratory_rate"],
        "training_data": "generated synthetic observations only", "demo_only": True, "clinically_validated": False}

@app.post("/api/v1/scores/news2")
def calculate_news2(payload: NEWS2Input):
    """Calculate parameter points for a fictional NEWS2 example; not clinical guidance."""
    return score_news2(payload.model_dump(exclude={"patient_id", "scale2_authorized"}))

@app.get("/api/v1/model/evaluation")
def model_evaluation():
    return evaluate_synthetic_holdout()

@app.post("/api/v1/risk/predict", response_model=RiskPrediction)
async def predict(payload: VitalInput):
    values = payload.model_dump(exclude={"patient_id"})
    return await record_observation(payload.patient_id, values, raise_alert=True)

@app.post("/api/v1/risk/explain")
def explain_risk(payload: VitalInput):
    values = payload.model_dump(exclude={"patient_id"})
    return {"patient_id": payload.patient_id, "model_version": MODEL_VERSION,
        "risk_score": round(predict_probability(values) * 100),
        "contributions": coefficient_contributions(values),
        "method": "standardized logistic-regression coefficient contributions",
        "caveat": "These are model contributions, not causal explanations or clinical guidance.",
        "demo_only": True}

@app.get("/api/v1/observations")
def observation_history(patient_id: str | None = Query(default=None, min_length=1, max_length=64),
    limit: int = Query(default=50, ge=1, le=100), before_id: int | None = Query(default=None, ge=1),
    after_id: int | None = Query(default=None, ge=0), session_id: str | None = Query(default=None, max_length=36)):
    if before_id is not None and after_id is not None:
        raise HTTPException(status_code=422, detail="Use either before_id or after_id, not both")
    records = list_observations(patient_id=patient_id, limit=limit, before_id=before_id,
                                after_id=after_id, session_id=session_id)
    full_page = len(records) == limit
    next_cursor = records[-1]["id"] if full_page and after_id is None else None
    next_after = records[-1]["id"] if full_page and after_id is not None else None
    return {"items": records, "count": len(records), "limit": limit, "next_before_id": next_cursor,
        "next_after_id": next_after,
        "demo_only": True, "disclaimer": "Synthetic demonstration records only; not for clinical use."}

@app.get("/api/v1/observations/quality")
def observation_quality(stale_after_seconds: int = Query(default=300, ge=30, le=86400),
    limit: int = Query(default=100, ge=1, le=100)):
    records = list_observations(limit=limit)
    return assess_observations(records, stale_after_seconds=stale_after_seconds)
