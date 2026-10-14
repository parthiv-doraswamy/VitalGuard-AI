"""Verify that synthetic records survive a backend restart or redeploy.

Step 1, before the restart:
    python backend/scripts/persistence_check.py write --base-url URL --state FILE
Step 2, restart or redeploy the backend (no other changes).
Step 3, after the restart:
    python backend/scripts/persistence_check.py verify --state FILE

`write` creates one fictional elevated-risk observation (which raises a demo
alert), acknowledges and resolves that alert, and records the ids in FILE.
`verify` re-reads the same ids through the public API and fails unless the
observation, alert status, timestamps and full audit history are unchanged.

Only synthetic records are created; patient ids are prefixed PERSIST-CHECK-.
The state file holds ids and the API base URL only, never credentials.
"""
from __future__ import annotations
import argparse
import json
import sys
import time
import httpx

SYNTHETIC_ELEVATED_VITALS = {"age": 70, "heart_rate": 180, "spo2": 78, "systolic_bp": 80,
                             "diastolic_bp": 50, "temperature": 39.5, "respiratory_rate": 34}


def _client(base_url: str) -> httpx.Client:
    # Long timeout tolerates hosted cold starts.
    return httpx.Client(base_url=base_url.rstrip("/"), timeout=90)


def _ok(response: httpx.Response) -> dict:
    if response.status_code >= 400:
        raise SystemExit(f"{response.request.method} {response.request.url.path} -> {response.status_code}: {response.text[:300]}")
    return response.json()


def write(base_url: str, state_path: str) -> int:
    patient_id = f"PERSIST-CHECK-{int(time.time())}"
    with _client(base_url) as client:
        health = _ok(client.get("/health"))
        prediction = _ok(client.post("/api/v1/risk/predict", json={"patient_id": patient_id, **SYNTHETIC_ELEVATED_VITALS}))
        alerts = _ok(client.get("/api/v1/alerts", params={"patient_id": patient_id, "limit": 10}))["items"]
        if not alerts:
            raise SystemExit("Elevated synthetic observation did not create an alert")
        alert_id = alerts[0]["id"]
        _ok(client.post(f"/api/v1/alerts/{alert_id}/acknowledge", json={"actor": "persistence-check"}))
        resolved = _ok(client.post(f"/api/v1/alerts/{alert_id}/resolve", json={"actor": "persistence-check"}))["item"]
        audit = _ok(client.get(f"/api/v1/alerts/{alert_id}/audit"))["items"]
    state = {"base_url": base_url, "patient_id": patient_id, "observation_id": prediction["observation_id"],
             "observation_created_at": prediction["created_at"], "alert_id": alert_id, "alert": resolved,
             "audit_ids": [item["id"] for item in audit], "audit_actions": [item["action"] for item in audit],
             "backend_before": health["database"]["backend"], "written_at": time.time()}
    with open(state_path, "w") as handle:
        json.dump(state, handle, indent=2)
    print(json.dumps({"written": True, "backend": state["backend_before"], "patient_id": patient_id,
                      "observation_id": state["observation_id"], "alert_id": alert_id,
                      "audit_actions": state["audit_actions"]}, indent=2))
    print("Now restart or redeploy the backend, then run `verify` with the same --state file.")
    return 0


def verify(state_path: str) -> int:
    with open(state_path) as handle:
        state = json.load(handle)
    failures: list[str] = []
    with _client(state["base_url"]) as client:
        health = _ok(client.get("/health"))
        history = _ok(client.get("/api/v1/observations", params={"patient_id": state["patient_id"], "limit": 10}))["items"]
        alert = _ok(client.get("/api/v1/alerts", params={"patient_id": state["patient_id"], "limit": 10}))["items"]
        audit_response = client.get(f"/api/v1/alerts/{state['alert_id']}/audit")
    observation = next((item for item in history if item["id"] == state["observation_id"]), None)
    if observation is None:
        failures.append(f"observation {state['observation_id']} missing")
    elif observation["created_at"] != state["observation_created_at"]:
        failures.append("observation created_at changed")
    stored_alert = next((item for item in alert if item["id"] == state["alert_id"]), None)
    if stored_alert is None:
        failures.append(f"alert {state['alert_id']} missing")
    else:
        for key in ("status", "acknowledged_by", "acknowledged_at", "resolved_at", "created_at"):
            if stored_alert.get(key) != state["alert"].get(key):
                failures.append(f"alert {key} changed: {state['alert'].get(key)!r} -> {stored_alert.get(key)!r}")
    if audit_response.status_code != 200:
        failures.append(f"alert audit returned {audit_response.status_code}")
    else:
        audit = audit_response.json()["items"]
        if [item["id"] for item in audit] != state["audit_ids"]:
            failures.append(f"audit history changed: {state['audit_actions']} -> {[item['action'] for item in audit]}")
    result = {"verified": not failures, "backend_before": state["backend_before"],
              "backend_after": health["database"]["backend"], "patient_id": state["patient_id"],
              "observation_id": state["observation_id"], "alert_id": state["alert_id"], "failures": failures}
    print(json.dumps(result, indent=2))
    return 0 if not failures else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Synthetic restart-survival check for the VitalGuard API.")
    parser.add_argument("command", choices=["write", "verify"])
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--state", required=True, help="local JSON file holding the ids to re-check")
    args = parser.parse_args(argv)
    return write(args.base_url, args.state) if args.command == "write" else verify(args.state)


if __name__ == "__main__":
    sys.exit(main())
