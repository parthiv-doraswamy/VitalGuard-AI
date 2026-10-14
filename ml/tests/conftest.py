import sys
from pathlib import Path

import pytest

ML_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ML_DIR))

from common import load_config  # noqa: E402
from prepare_dataset import prepare  # noqa: E402


def fixture_config(data_dir: Path, patients: int = 400) -> dict:
    config = load_config("mimic_format_fixture")
    config["data_dir"] = str(data_dir)
    config["fixture"] = {"patients": patients, "seed": 11}
    return config


@pytest.fixture(scope="session")
def prepared(tmp_path_factory):
    """A small fictional MIMIC-format dataset prepared once for the whole session."""
    root = tmp_path_factory.mktemp("ml")
    config = fixture_config(root / "synthetic-mimic-format")
    manifest = prepare("mimic_format_fixture", generate=True, out_dir=root / "dataset", config=config)
    return {"config": config, "manifest": manifest, "dataset_dir": root / "dataset", "root": root}
