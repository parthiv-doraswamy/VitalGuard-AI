"""Shared configuration, hashing and path helpers for the VitalGuard ML pipeline."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

ML_DIR = Path(__file__).resolve().parent
REPO_ROOT = ML_DIR.parent
BACKEND_DIR = REPO_ROOT / "backend"
CONFIG_PATH = ML_DIR / "config.yaml"
RUNS_DIR = ML_DIR / "runs"
ARTIFACTS_DIR = ML_DIR / "artifacts"

# The pipeline saves and verifies artifacts with the backend's own loader, so
# anything it produces is guaranteed loadable by the API.
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


class PipelineError(RuntimeError):
    """A configuration, data-access or validation problem that stops the pipeline."""


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        merged[key] = _merge(merged[key], value) if isinstance(value, dict) and isinstance(merged.get(key), dict) else value
    return merged


def load_config(experiment: str, path: Path = CONFIG_PATH) -> dict[str, Any]:
    """Return the effective configuration for one experiment (defaults + overrides)."""
    raw = yaml.safe_load(Path(path).read_text())
    experiments = raw.pop("experiments")
    if experiment not in experiments:
        raise PipelineError(f"Unknown experiment '{experiment}'. Choose one of: {', '.join(sorted(experiments))}")
    config = _merge(raw, experiments[experiment])
    config["experiment"] = experiment
    from app.model import FEATURES
    names = tuple(feature["name"] for feature in config["features"])
    if names != FEATURES:
        raise PipelineError(f"config features {names} must equal the API feature order {FEATURES}")
    return config


def config_sha256(config: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(config, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_ids(ids) -> str:
    return hashlib.sha256("\n".join(sorted(str(item) for item in ids)).encode()).hexdigest()


def git_commit() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True,
                              check=True, timeout=5).stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def resolve_data_dir(config: dict[str, Any]) -> Path:
    if config.get("data_dir"):
        return (REPO_ROOT / config["data_dir"]).resolve()
    variable = config.get("data_dir_env")
    value = os.getenv(variable or "", "").strip()
    if not value:
        raise PipelineError(
            f"BLOCKED: experiment '{config['experiment']}' needs ${variable} pointing at a local copy of the dataset. "
            "No data is downloaded by this pipeline; obtain access through the data provider first.")
    return Path(value).expanduser().resolve()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n")
