"""Concurrency/load test for one or more VitalGuard API instances (synthetic data only).

    python backend/scripts/load_test.py --targets http://127.0.0.1:8001,http://127.0.0.1:8002 \
        --levels 1,5,10,25,50 --duration 15 --listeners 2 --pids 1234,5678 --out results.json

For each concurrency level, N virtual users loop for `duration` seconds over the
targets (round-robin). Each request is either:
  70% POST /api/v1/risk/predict (writes an observation and its outbox events), or
  30% GET /api/v1/observations?limit=50 (bounded read).
WebSocket listeners on every target record when each committed observation
arrives, giving submit-to-delivery latency (same machine clock, so exact)
and delivery completeness across instances.

Reported per level: throughput, error rate, p50/p95/p99 request latency per
operation, delivery p50/p95 and completeness, and optional resource samples
(RSS/CPU via `ps` for --pids; PostgreSQL connections when $LOADTEST_DATABASE_URL is set).
Creates fictional records with patient ids LOAD-*. Never point it at production.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import subprocess
import time
from typing import Any

import httpx
from websockets.asyncio.client import connect

VITALS = {"age": 64, "heart_rate": 96, "spo2": 95, "systolic_bp": 118, "diastolic_bp": 74, "temperature": 37.4,
          "respiratory_rate": 19}


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(q / 100 * (len(ordered) - 1))))
    return round(ordered[index], 2)


class Listener:
    def __init__(self, url: str):
        self.url = url.replace("http", "ws", 1) + "/api/v1/live"
        self.received: dict[int, float] = {}
        self.duplicates = 0
        self.task: asyncio.Task | None = None
        self.connected = asyncio.Event()

    async def run(self):
        async with connect(self.url, max_queue=None) as socket:
            await socket.recv()
            self.connected.set()
            async for message in socket:
                event = json.loads(message)
                if event.get("type") == "observation.created" and str(event.get("patient_id", "")).startswith("LOAD-"):
                    if event["event_id"] in self.received:
                        self.duplicates += 1
                    else:
                        self.received[event["event_id"]] = time.perf_counter()


async def sample_resources(pids: list[int], database_url: str | None, stop: asyncio.Event, samples: list[dict]):
    engine = None
    if database_url:
        from sqlalchemy import create_engine, text
        engine = create_engine(database_url)
    while not stop.is_set():
        entry: dict[str, Any] = {"t": time.time()}
        for pid in pids:
            output = subprocess.run(["ps", "-o", "rss=,%cpu=", "-p", str(pid)], capture_output=True, text=True).stdout.split()
            if len(output) == 2:
                entry[f"pid{pid}"] = {"rss_mb": round(int(output[0]) / 1024, 1), "cpu_percent": float(output[1])}
        if engine is not None:
            with engine.connect() as connection:
                entry["db_connections"] = connection.execute(text(
                    "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()")).scalar()
        samples.append(entry)
        try:
            await asyncio.wait_for(stop.wait(), timeout=1.0)
        except asyncio.TimeoutError:
            pass
    if engine is not None:
        engine.dispose()


async def run_level(targets: list[str], users: int, duration: float, listeners: list[Listener],
                    pids: list[int], database_url: str | None) -> dict[str, Any]:
    latencies: dict[str, list[float]] = {"predict": [], "history": []}
    errors: dict[str, int] = {}
    submitted: dict[int, float] = {}
    counts = {"predict": 0, "history": 0}
    stop_at = time.perf_counter() + duration
    resource_samples: list[dict] = []
    stop_sampling = asyncio.Event()
    sampler = asyncio.create_task(sample_resources(pids, database_url, stop_sampling, resource_samples))
    limits = httpx.Limits(max_connections=users * 2 + 10, max_keepalive_connections=users * 2 + 10)

    async with httpx.AsyncClient(limits=limits, timeout=30) as client:
        async def user(index: int):
            rng = random.Random(index)
            turn = index
            while time.perf_counter() < stop_at:
                base = targets[turn % len(targets)]
                turn += 1
                operation = "predict" if rng.random() < 0.7 else "history"
                started = time.perf_counter()
                try:
                    if operation == "predict":
                        response = await client.post(f"{base}/api/v1/risk/predict",
                                                     json={"patient_id": f"LOAD-{users}-{index}", **VITALS})
                    else:
                        response = await client.get(f"{base}/api/v1/observations", params={"limit": 50})
                    elapsed = (time.perf_counter() - started) * 1000
                    if response.status_code >= 400:
                        errors[str(response.status_code)] = errors.get(str(response.status_code), 0) + 1
                    else:
                        latencies[operation].append(elapsed)
                        counts[operation] += 1
                        if operation == "predict":
                            submitted[response.json()["observation_id"]] = started
                except httpx.HTTPError as exc:
                    errors[type(exc).__name__] = errors.get(type(exc).__name__, 0) + 1

        wall_started = time.perf_counter()
        await asyncio.gather(*(user(index) for index in range(users)))
        wall = time.perf_counter() - wall_started

    await asyncio.sleep(3)  # let in-flight deliveries arrive
    stop_sampling.set()
    await sampler
    delivery: list[float] = []
    complete = 0
    for observation_id, sent in submitted.items():
        arrivals = [listener.received.get(observation_id) for listener in listeners]
        if all(arrival is not None for arrival in arrivals):
            complete += 1
        delivery.extend((arrival - sent) * 1000 for arrival in arrivals if arrival is not None)
    total_ok = counts["predict"] + counts["history"]
    total_errors = sum(errors.values())

    def resources():
        summary: dict[str, Any] = {}
        for pid in pids:
            series = [sample[f"pid{pid}"] for sample in resource_samples if f"pid{pid}" in sample]
            if series:
                summary[f"pid{pid}"] = {"max_rss_mb": max(s["rss_mb"] for s in series),
                                        "max_cpu_percent": max(s["cpu_percent"] for s in series)}
        connections = [sample["db_connections"] for sample in resource_samples if "db_connections" in sample]
        if connections:
            summary["max_db_connections"] = max(connections)
        return summary

    return {
        "concurrent_users": users, "duration_s": round(wall, 2),
        "requests_ok": total_ok, "requests_failed": total_errors, "errors_by_kind": errors,
        "throughput_rps": round(total_ok / wall, 1) if wall else None,
        "error_rate": round(total_errors / max(1, total_ok + total_errors), 4),
        "latency_ms": {operation: {"p50": percentile(values, 50), "p95": percentile(values, 95), "p99": percentile(values, 99),
                                   "count": len(values)} for operation, values in latencies.items()},
        "delivery": {"observations_committed": len(submitted), "received_by_every_listener": complete,
                     "completeness": round(complete / len(submitted), 4) if submitted else None,
                     "p50_ms": percentile(delivery, 50), "p95_ms": percentile(delivery, 95), "p99_ms": percentile(delivery, 99),
                     "duplicate_deliveries": sum(listener.duplicates for listener in listeners)},
        "resources": resources(),
    }


async def main_async(args) -> dict[str, Any]:
    targets = [target.rstrip("/") for target in args.targets.split(",")]
    pids = [int(pid) for pid in args.pids.split(",")] if args.pids else []
    listeners = [Listener(target) for target in targets for _ in range(args.listeners)]
    for listener in listeners:
        listener.task = asyncio.create_task(listener.run())
    await asyncio.wait_for(asyncio.gather(*(listener.connected.wait() for listener in listeners)), timeout=15)
    health = {}
    async with httpx.AsyncClient(timeout=10) as client:
        for target in targets:
            body = (await client.get(f"{target}/health")).json()
            health[target] = {"status": body["status"], "broker": body.get("event_broker", {}).get("mode"),
                              "cross_instance_delivery": body.get("event_broker", {}).get("cross_instance_delivery"),
                              "database": body["database"]["backend"]}
    levels = []
    for users in [int(level) for level in args.levels.split(",")]:
        result = await run_level(targets, users, args.duration, listeners, pids, os.getenv("LOADTEST_DATABASE_URL"))
        levels.append(result)
        print(f"users={users:>3} rps={result['throughput_rps']:>7} err={result['error_rate']:.4f} "
              f"predict p50/p95={result['latency_ms']['predict']['p50']}/{result['latency_ms']['predict']['p95']} ms "
              f"delivery p95={result['delivery']['p95_ms']} ms complete={result['delivery']['completeness']}", flush=True)
    for listener in listeners:
        listener.task.cancel()
    return {"targets": targets, "health_at_start": health, "listeners_per_target": args.listeners,
            "duration_per_level_s": args.duration, "mix": "70% POST /risk/predict, 30% GET /observations?limit=50",
            "levels": levels}


def to_markdown(report: dict[str, Any]) -> str:
    lines = [f"Targets: {', '.join(report['targets'])} · {report['mix']} · {report['duration_per_level_s']} s per level · "
             f"{report['listeners_per_target']} WebSocket listener(s) per target", "",
             "| Users | Throughput (req/s) | Error rate | Errors | Predict p50 / p95 / p99 ms | History p50 / p95 ms | "
             "Delivery p50 / p95 ms | Delivered to all listeners | Max RSS MB (per process) | Max DB conns |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for level in report["levels"]:
        predict, history, delivery = level["latency_ms"]["predict"], level["latency_ms"]["history"], level["delivery"]
        rss = ", ".join(str(value["max_rss_mb"]) for key, value in level["resources"].items() if key.startswith("pid")) or "—"
        lines.append(f"| {level['concurrent_users']} | {level['throughput_rps']} | {level['error_rate']:.2%} | "
                     f"{level['errors_by_kind'] or '—'} | {predict['p50']} / {predict['p95']} / {predict['p99']} | "
                     f"{history['p50']} / {history['p95']} | {delivery['p50_ms']} / {delivery['p95_ms']} | "
                     f"{delivery['received_by_every_listener']}/{delivery['observations_committed']} | {rss} | "
                     f"{level['resources'].get('max_db_connections', '—')} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--targets", required=True)
    parser.add_argument("--levels", default="1,5,10,25,50")
    parser.add_argument("--duration", type=float, default=15)
    parser.add_argument("--listeners", type=int, default=2)
    parser.add_argument("--pids", default="")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    report = asyncio.run(main_async(args))
    with open(args.out, "w") as handle:
        json.dump(report, handle, indent=2)
    with open(os.path.splitext(args.out)[0] + ".md", "w") as handle:
        handle.write(to_markdown(report))
    print(to_markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
