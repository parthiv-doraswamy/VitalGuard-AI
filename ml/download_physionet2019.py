"""Download the open-access PhysioNet/CinC Challenge 2019 training data (~40,000 small .psv files, ~42 MB).

Files land in ml/data/physionet-2019/training_setA|B (git-ignored). Already
downloaded files are skipped, so the script can be re-run to resume.

  python ml/download_physionet2019.py [--workers 8]
"""
from __future__ import annotations

import argparse
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BASE = "https://physionet.org/files/challenge-2019/1.0.0/training"
TARGET = Path(__file__).resolve().parent / "data" / "physionet-2019"


def listing(subset: str) -> list[str]:
    with urllib.request.urlopen(f"{BASE}/{subset}/", timeout=60) as response:
        return sorted(set(re.findall(r"p\d+\.psv", response.read().decode())))


def fetch(subset: str, name: str) -> bool:
    path = TARGET / subset / name
    if path.exists() and path.stat().st_size > 0:
        return False
    for attempt in range(3):
        try:
            with urllib.request.urlopen(f"{BASE}/{subset}/{name}", timeout=60) as response:
                data = response.read()
            tmp = path.with_suffix(".part")
            tmp.write_bytes(data)
            tmp.replace(path)
            return True
        except OSError:
            if attempt == 2:
                raise
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    for subset in ("training_setA", "training_setB"):
        (TARGET / subset).mkdir(parents=True, exist_ok=True)
        names = listing(subset)
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            fetched = sum(pool.map(lambda name: fetch(subset, name), names))
        print(f"{subset}: {len(names)} files ({fetched} downloaded now)")


if __name__ == "__main__":
    main()
