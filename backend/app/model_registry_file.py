"""Read and write the deployed-model registry (model_artifacts/registry.json).

The registry names the `active` artifact the API loads and the `previous` one it
falls back to (and that `ml/model_registry.py rollback` restores).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

REGISTRY_FILE = "registry.json"
REGISTRY_FORMAT = "vitalguard-model-registry"


def read_registry(root: Path) -> dict[str, Any]:
    path = Path(root) / REGISTRY_FILE
    registry = json.loads(path.read_text())
    if registry.get("format") != REGISTRY_FORMAT or not registry.get("active"):
        raise ValueError("Invalid model registry")
    registry.setdefault("previous", None)
    registry.setdefault("history", [])
    return registry


def write_registry(root: Path, registry: dict[str, Any]) -> None:
    """Atomic replace so a crash never leaves a half-written registry."""
    path = Path(root) / REGISTRY_FILE
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(registry, indent=2) + "\n")
    os.replace(temporary, path)
