"""Validated, idempotent batch ingestion for synthetic demo observations only."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from .auth import authenticate_principal
from .ingestion_store import persist_ingested_observation
from .live_events import hub
from .model import MODEL_VERSION, explain, predict_probability, risk_level
from .schemas import RiskPrediction, VitalInput

router = APIRouter(
    prefix="/api/v1/ingestion",
    tags=["validated-ingestion"],
    dependencies=[Depends(authenticate_principal)],
)


class ObservationUnits(BaseModel):
    model_config = ConfigDict(extra="forbid")
    age: Literal["years"]
    heart_rate: Literal["bpm"]
    spo2: Literal["percent"]
    systolic_bp: Literal["mmHg"]
    diastolic_bp: Literal["mmHg"]
    temperature: Literal["degC"]
    respiratory_rate: Literal["breaths/min"]


class IngestionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_system: Literal["synthetic-demo"] = "synthetic-demo"
    source_event_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")
    observed_at: datetime
    observation: VitalInput
    units: ObservationUnits

    @field_validator("observed_at")
    @classmethod
    def require_timezone_and_reasonable_window(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("observed_at must include a timezone offset")
        now = datetime.now(timezone.utc)
        normalized = value.astimezone(timezone.utc)
        if normalized > now + timedelta(minutes=5):
            raise ValueError("observed_at cannot be more than 5 minutes in the future")
        if normalized < now - timedelta(days=30):
            raise ValueError("observed_at is outside the 30-day demo ingestion window")
        return normalized

    @model_validator(mode="after")
    def enforce_synthetic_patient_id(self):
        if not self.observation.patient_id.startswith("DEMO-"):
            raise ValueError("Only synthetic demo patient IDs beginning with DEMO- are accepted")
        return self


class IngestionBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    records: list[dict[str, Any]] = Field(min_length=1, max_length=100)


def _error_detail(error: ValidationError) -> list[dict[str, str]]:
    return [
        {"field": ".".join(str(part) for part in item["loc"]), "message": item["msg"]}
        for item in error.errors(include_url=False, include_context=False)
    ]


@router.post("/batch")
async def ingest_batch(batch: IngestionBatch, principal: dict = Depends(authenticate_principal)):
    """Validate each item independently; valid items commit even when peers fail."""
    results: list[dict[str, Any]] = []
    for index, raw in enumerate(batch.records):
        try:
            item = IngestionItem.model_validate(raw)
        except ValidationError as error:
            results.append({"index": index, "status": "rejected", "errors": _error_detail(error)})
            continue

        values = item.observation.model_dump(exclude={"patient_id"})
        probability = predict_probability(values)
        score = round(probability * 100)
        prediction = RiskPrediction(
            patient_id=item.observation.patient_id,
            risk_score=score,
            risk_level=risk_level(score),
            model_probability=round(probability, 4),
            factors=explain(values),
            model_version=MODEL_VERSION,
        )
        canonical = item.model_dump(mode="json")
        payload_hash = hashlib.sha256(
            json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        persisted = persist_ingested_observation(
            source_system=item.source_system,
            source_event_id=item.source_event_id,
            patient_id=item.observation.patient_id,
            observed_at=item.observed_at,
            units=item.units.model_dump(),
            payload_hash=payload_hash,
            inputs=values,
            prediction=prediction.model_dump(),
        )
        result = {
            "index": index,
            **persisted,
            "source_system": item.source_system,
            "source_event_id": item.source_event_id,
            "patient_id": item.observation.patient_id,
            "observed_at": item.observed_at.isoformat(),
            "demo_only": True,
        }
        results.append(result)
        if persisted["status"] == "accepted":
            response = prediction.model_copy(update={"observation_id": persisted["observation_id"]})
            await hub.broadcast({
                "type": "observation.created",
                "event_id": persisted["observation_id"],
                "patient_id": item.observation.patient_id,
                "observed_at": item.observed_at.isoformat(),
                "observation": values,
                "prediction": response.model_dump(),
                "source_system": item.source_system,
                "demo_only": True,
            })

    accepted = sum(result["status"] == "accepted" for result in results)
    duplicates = sum(result["status"] == "duplicate" for result in results)
    rejected = sum(result["status"] == "rejected" for result in results)
    return {
        "items": results,
        "count": len(results),
        "accepted": accepted,
        "duplicates": duplicates,
        "rejected": rejected,
        "demo_only": True,
        "disclaimer": "Synthetic demo ingestion only. No real patient data or clinical use is authorized.",
    }
