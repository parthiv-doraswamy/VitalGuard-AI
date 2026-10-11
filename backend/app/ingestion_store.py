"""Transactional persistence for validated demo ingestion records."""
from __future__ import annotations

import json
from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError

from .ingestion_schema import ingestion_records
from .storage import _OBSERVATIONS, _engine


def persist_ingested_observation(
    *, source_system: str, source_event_id: str, patient_id: str,
    observed_at, units: dict[str, str], payload_hash: str,
    inputs: dict, prediction: dict,
) -> dict:
    """Persist observation and provenance together with source-event idempotency."""
    engine = _engine()
    try:
        try:
            with engine.begin() as connection:
                existing = connection.execute(
                    select(ingestion_records).where(
                        ingestion_records.c.source_system == source_system,
                        ingestion_records.c.source_event_id == source_event_id,
                    )
                ).mappings().first()
                if existing:
                    return {
                        "status": "duplicate" if existing["payload_hash"] == payload_hash else "conflict",
                        "observation_id": existing["observation_id"],
                        "ingestion_id": existing["id"],
                    }

                observation_result = connection.execute(insert(_OBSERVATIONS).values(
                    patient_id=patient_id,
                    input_json=json.dumps(inputs, separators=(",", ":")),
                    prediction_json=json.dumps(prediction, separators=(",", ":")),
                    model_version=prediction["model_version"],
                ))
                observation_id = observation_result.inserted_primary_key[0]
                ingestion_result = connection.execute(insert(ingestion_records).values(
                    source_system=source_system,
                    source_event_id=source_event_id,
                    patient_id=patient_id,
                    observed_at=observed_at,
                    observation_id=observation_id,
                    units_json=json.dumps(units, separators=(",", ":"), sort_keys=True),
                    payload_hash=payload_hash,
                ))
                return {
                    "status": "accepted",
                    "observation_id": observation_id,
                    "ingestion_id": ingestion_result.inserted_primary_key[0],
                }
        except IntegrityError:
            # A concurrent request may have won the unique source-event key.
            with engine.connect() as connection:
                existing = connection.execute(
                    select(ingestion_records).where(
                        ingestion_records.c.source_system == source_system,
                        ingestion_records.c.source_event_id == source_event_id,
                    )
                ).mappings().first()
            if existing:
                return {
                    "status": "duplicate" if existing["payload_hash"] == payload_hash else "conflict",
                    "observation_id": existing["observation_id"],
                    "ingestion_id": existing["id"],
                }
            raise
    finally:
        engine.dispose()
