"""Candidate model catalogue and the deployed-artifact registry.

Candidates
    Every candidate is an sklearn Pipeline over the same 7 API features, built
    from ml/config.yaml (`model` for the logistic-regression baseline,
    `candidates` for the others). Hyperparameter grids are searched on the
    validation split only (ml/train.py --benchmark).

Registry (backend/app/model_artifacts/registry.json)
    python ml/model_registry.py status
    python ml/model_registry.py promote <artifact_dir> [--allow-research-artifact]
    python ml/model_registry.py rollback

    `active` is what the API loads. Promotion verifies the artifact with the
    backend loader first and keeps the previous active version for rollback; if
    the active artifact fails verification at startup, the API itself falls back
    to the previous one (backend/app/model.py). Commit registry changes only
    after backend tests and the live smoke test pass on the promoted artifact.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import product
from pathlib import Path
from typing import Any, Callable

from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from common import BACKEND_DIR, PipelineError
from app.model import FEATURES
from app.model_artifact import ArtifactError, load_artifact
from app.model_registry_file import REGISTRY_FILE, read_registry, write_registry

ARTIFACT_ROOT = BACKEND_DIR / "app" / "model_artifacts"


@dataclass(frozen=True)
class Candidate:
    name: str
    algorithm: str
    complexity: int            # lower is simpler; ties in performance go to the simpler model
    runtime_package: str       # import name the backend needs to unpickle and run it
    requirement_name: str      # distribution name as written in backend/requirements.txt
    linear: bool               # supports coefficient contributions in /api/v1/risk/explain
    grid: Callable[[dict[str, Any]], list[dict[str, Any]]]
    build: Callable[[dict[str, Any], dict[str, Any], dict[str, Any]], Pipeline]


def _logreg_grid(config):
    return [{"C": value} for value in config["model"]["c_grid"]]


def _logreg_build(config, params, _context):
    model = config["model"]
    return Pipeline([("scale", StandardScaler()), ("classifier", LogisticRegression(
        C=params["C"], class_weight=model["class_weight"], max_iter=model["max_iter"], random_state=model["random_state"]))])


def _forest_grid(config):
    settings = config["candidates"]["random_forest"]
    return [{"max_depth": depth, "min_samples_leaf": leaf}
            for depth, leaf in product(settings["max_depth_grid"], settings["min_samples_leaf_grid"])]


def _forest_build(config, params, _context):
    settings = config["candidates"]["random_forest"]
    # Trees need no scaling; "passthrough" keeps the same pipeline shape and step names.
    return Pipeline([("scale", "passthrough"), ("classifier", RandomForestClassifier(
        n_estimators=settings["n_estimators"], max_depth=params["max_depth"], min_samples_leaf=params["min_samples_leaf"],
        class_weight="balanced_subsample", random_state=config["model"]["random_state"], n_jobs=1))])


def _xgb_grid(config):
    return [{"max_depth": depth} for depth in config["candidates"]["xgboost"]["max_depth_grid"]]


def _xgb_build(config, params, context):
    from xgboost import XGBClassifier
    settings = config["candidates"]["xgboost"]
    return Pipeline([("scale", "passthrough"), ("classifier", XGBClassifier(
        n_estimators=settings["n_estimators"], max_depth=params["max_depth"], learning_rate=settings["learning_rate"],
        subsample=settings["subsample"], colsample_bytree=settings["colsample_bytree"],
        # Same class-imbalance handling intent as class_weight="balanced", from training labels only.
        scale_pos_weight=context["negative_to_positive_ratio"], random_state=config["model"]["random_state"],
        n_jobs=1, tree_method="hist", eval_metric="logloss"))])


CANDIDATES: dict[str, Candidate] = {
    "logreg": Candidate("logreg", "StandardScaler + LogisticRegression", 1, "sklearn", "scikit-learn", True, _logreg_grid, _logreg_build),
    "random_forest": Candidate("random_forest", "RandomForestClassifier", 2, "sklearn", "scikit-learn", False, _forest_grid, _forest_build),
    "xgboost": Candidate("xgboost", "XGBoost gradient-boosted trees", 3, "xgboost", "xgboost", False, _xgb_grid, _xgb_build),
}
BASELINE = "logreg"


def installed(candidate: Candidate) -> bool:
    """Can this (training) environment build the candidate?"""
    return importlib.util.find_spec(candidate.runtime_package) is not None


def backend_runtime_supports(candidate: Candidate) -> bool:
    """Is the candidate's package a pinned dependency of the deployed API?"""
    requirements = (BACKEND_DIR / "requirements.txt").read_text().lower().splitlines()
    names = {line.split("==")[0].split("[")[0].strip() for line in requirements if line.strip() and not line.startswith("#")}
    return candidate.requirement_name.lower() in names


# --- Deployed-artifact registry -------------------------------------------------------

def status() -> dict[str, Any]:
    return read_registry(ARTIFACT_ROOT)


def promote(artifact_dir: Path, *, allow_research: bool = False, root: Path = ARTIFACT_ROOT) -> dict[str, Any]:
    """Verify, copy into the backend artifact store, and make active; the old active becomes `previous`."""
    artifact_dir = Path(artifact_dir).resolve()
    _, manifest = load_artifact(artifact_dir, FEATURES)
    kind = manifest.get("dataset", {}).get("kind")
    if manifest["dataset"].get("synthetic_fixture"):
        raise PipelineError("Refusing to promote an artifact trained on the synthetic fixture")
    if kind != "synthetic-demo" and not allow_research:
        raise PipelineError(f"Artifact dataset kind '{kind}' needs --allow-research-artifact and a governance sign-off")
    registry = read_registry(root)
    version = manifest["model_version"]
    target = root / version
    if target.resolve() != artifact_dir:
        if target.exists():
            raise PipelineError(f"{version} already exists in the artifact store with different content")
        shutil.copytree(artifact_dir, target)
    load_artifact(target, FEATURES)
    if registry["active"] == version:
        return registry
    now = datetime.now(timezone.utc).isoformat()
    registry["previous"] = registry["active"]
    registry["active"] = version
    registry["history"].append({"action": "promote", "version": version, "model_sha256": manifest["model_sha256"],
                                "dataset_kind": kind, "at": now})
    write_registry(root, registry)
    return registry


def rollback(root: Path = ARTIFACT_ROOT) -> dict[str, Any]:
    """Make the previous artifact active again (it is verified first)."""
    registry = read_registry(root)
    previous = registry.get("previous")
    if not previous:
        raise PipelineError("No previous artifact to roll back to")
    load_artifact(root / previous, FEATURES)
    registry["active"], registry["previous"] = previous, registry["active"]
    registry["history"].append({"action": "rollback", "version": previous, "at": datetime.now(timezone.utc).isoformat()})
    write_registry(root, registry)
    return registry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Deployed model artifact registry")
    parser.add_argument("command", choices=["status", "promote", "rollback", "candidates"])
    parser.add_argument("artifact", nargs="?", type=Path)
    parser.add_argument("--allow-research-artifact", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "candidates":
            result: Any = {name: {"algorithm": c.algorithm, "installed": installed(c),
                                  "backend_runtime_supports": backend_runtime_supports(c)} for name, c in CANDIDATES.items()}
        elif args.command == "status":
            result = status()
        elif args.command == "promote":
            if not args.artifact:
                parser.error("promote needs an artifact directory")
            result = promote(args.artifact, allow_research=args.allow_research_artifact)
        else:
            result = rollback()
    except (PipelineError, ArtifactError, OSError) as exc:  # reported, never half-applied
        print(f"Refused: {exc}")
        return 2
    print(json.dumps(result, indent=2))
    print(f"(registry file: {REGISTRY_FILE})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
