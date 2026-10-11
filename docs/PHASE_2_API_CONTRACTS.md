# Phase 2 — API Contract Inventory

**Purpose:** Record the API contract evidenced by the current backend source and identify target contracts for later phases.  
**Important:** This is not a claim that every listed route is secure or clinically approved. Authentication is not established in the inspected entry point; keep the deployment synthetic-only.

## 1. Contract conventions

- Base URL is the deployed backend origin or local `http://localhost:8000`.
- JSON requests use `Content-Type: application/json`.
- Existing API paths use the `/api/v1` prefix except health/root and the WebSocket route.
- Existing Pydantic request models generally reject unknown fields where `extra="forbid"` is configured.
- Existing response errors may not yet use one common envelope; normalize this in a future compatibility-reviewed implementation.
- Never expose stack traces, secrets, credentials or sensitive payloads in errors.
- All current risk/model outputs are demo-only and not for clinical use.

## 2. Existing endpoints verified in the inspected backend entry point

| Method | Path | Request | Response / behavior | Notes |
|---|---|---|---|---|
| GET | `/` | None | Service/status metadata | Demo-only marker |
| GET | `/health` | None | Status, model version, database health, WebSocket availability | Returns 503 if database health check fails |
| GET | `/api/v1/model/info` | None | Algorithm, feature list, training-data description, demo/validation flags | Synthetic model |
| GET | `/api/v1/model/evaluation` | None | Synthetic holdout evaluation | Not clinical validation |
| POST | `/api/v1/risk/predict` | `VitalInput` | `RiskPrediction`, persisted observation ID/time | Persists and broadcasts event; may create synthetic alert |
| POST | `/api/v1/risk/explain` | `VitalInput` | Model coefficient contributions and caveat | Not SHAP or causal explanation |
| POST | `/api/v1/scores/news2` | `NEWS2Input` | Parameter-score result | Demonstration only; not clinically validated |
| GET | `/api/v1/observations` | Optional `patient_id`, `limit` 1–100, `before_id` | Items, count, cursor and demo disclaimer | Cursor currently based on numeric observation ID |
| GET | `/api/v1/observations/quality` | `stale_after_seconds` 30–86400, `limit` 1–100 | Quality assessment | Bounded history only |
| WS | `/api/v1/live` | WebSocket connection | Observation/alert events | In-process hub; authentication not established |
| POST | `/api/v1/demo/observations` | `SimulationRequest` | Synthetic prediction | Router mounted by `main.py`; one new record per request, not idempotent |

Additional alert, timeline and trend routers are mounted in the backend entry point. Their precise route contracts must be captured from their actual route modules before implementation depends on them; see the dedicated inventory task below.

## 3. Existing input schema: VitalInput

Current source fields:
- `patient_id`: string, length 1–64, default `DEMO-001`.
- `age`: integer 18–110.
- `heart_rate`: number 20–250.
- `spo2`: number 50–100.
- `systolic_bp`: number 50–280.
- `diastolic_bp`: number 20–180.
- `temperature`: number 30–45.
- `respiratory_rate`: number 3–70.
- Cross-field validation requires diastolic BP to be lower than systolic BP.
- Unknown fields are forbidden.

These bounds are the current prototype schema, not an approved clinical reference range or universal validity standard. Explicit units, observation timestamps and source provenance are not part of this request model today.

## 4. Existing prediction response: RiskPrediction

Current source fields:
- `patient_id`
- `observation_id` (nullable until persistence)
- `created_at` (nullable until persistence)
- `risk_score` integer 0–100
- `risk_level`: `low | moderate | high | critical`
- `model_probability` number 0–1
- `factors`: feature, observed value, direction and explanation
- `model_version`
- `demo_only`: literal `true`
- `disclaimer`

The field `model_probability` is the output of the synthetic classifier; it must not be presented as a clinically calibrated probability.

## 5. Target API envelope (proposed, not implemented)

Success responses should preserve endpoint-specific payload fields and add a consistent request ID through a response header. Error responses should converge on this shape after a versioned compatibility review:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "The request could not be validated.",
    "request_id": "server-generated-id",
    "retryable": false,
    "details": []
  }
}
```

Do not expose database details, stack traces, secrets or another patient's existence in the error details. The exact schema and status-code matrix must be added to automated contract tests before adoption.

## 6. Target observation contract (proposed, not implemented)

A future versioned observation object should contain:
- Internal patient/resource reference.
- Measurement code/type.
- Numeric or coded value.
- Explicit UCUM-compatible or otherwise documented unit.
- `observed_at` with an explicit timezone/offset.
- Server-generated `received_at`.
- Source/integration identifier and external source-record identifier where available.
- Source event/idempotency key where available.
- Validation status and data-quality flags.
- Schema version.
- Correction/retraction linkage where required.

Do not silently interpret absent units or ambiguous timestamps. Do not silently convert missing observations to normal values. Corrections should preserve the original audit history.

## 7. Target error/status semantics (proposed)

| Condition | Target response | Persistence effect |
|---|---|---|
| Malformed JSON/schema | 400/422, structured validation error | No write |
| Missing/invalid authentication | 401 | No protected operation |
| Authenticated but unauthorized | 403 or deliberate non-disclosing 404 | No protected operation |
| Unknown permitted resource | 404 | No write |
| Duplicate idempotency key with same payload | Documented duplicate result | No second record |
| Same idempotency key with conflicting payload | 409 conflict | No overwrite |
| Database unavailable before commit | 503 retryable | No success response |
| Event publish fails after committed write | Successful persisted result plus durable retry/operational signal | Do not duplicate on retry |
| Rate limit exceeded | 429 with retry guidance | No mutation |
| Missing/stale observation | Explicit data-quality state | Never synthesize normal value |

The exact status codes must be applied consistently and tested in a later implementation phase.

## 8. Contract tests required before production-like use

- Validate every request and response against versioned schemas.
- Test boundary values, invalid types, unknown fields and cross-field validation.
- Test missing/invalid auth, insufficient role and cross-patient access attempts.
- Test duplicate keys, conflicting retries, out-of-order/future timestamps and unsupported units.
- Test database failure and event-delivery failure independently.
- Test pagination stability and deterministic ordering.
- Verify no secrets or sensitive payloads leak in errors/logs.
- Verify generated OpenAPI is consistent with the committed contract and deployed commit.

## 9. Known gaps

- No versioned external OpenAPI snapshot is committed yet.
- Observation request does not currently include explicit units, observation timestamp, source provenance or idempotency key.
- Authenticated identity and server-side resource authorization are not established.
- Error formats are not yet normalized.
- The simulator endpoint is explicitly non-idempotent.
- The frontend API client exposes patient endpoints not verified in the inspected `main.py`; reconcile these with mounted routers before relying on them.
- Existing numeric bounds must not be mistaken for clinical validation.
