#!/usr/bin/env python3
"""Fetch the exact locked CPU build/runtime wheels into an ignored wheelhouse."""
from __future__ import annotations

import argparse
import urllib.request
from pathlib import Path

from common import EXPERIMENT_ROOT, load_json, sha256_file


def fetch_wheels(lock_path: Path, wheel_dir: Path) -> None:
    lock = load_json(lock_path)
    wheel_dir.mkdir(parents=True, exist_ok=True)
    expected_names = {item["filename"] for item in lock["wheels"]}
    unexpected = {path.name for path in wheel_dir.glob("*.whl")} - expected_names
    if unexpected:
        raise RuntimeError(f"wheelhouse contains unpinned wheels: {sorted(unexpected)}")
    for item in lock["wheels"]:
        target = wheel_dir / item["filename"]
        if target.is_file() and target.stat().st_size == item["bytes"] and sha256_file(target) == item["sha256"]:
            print(f"verified {target.name}")
            continue
        target.unlink(missing_ok=True)
        temporary = target.with_suffix(target.suffix + ".part")
        temporary.unlink(missing_ok=True)
        print(f"fetching {item['url']}")
        with urllib.request.urlopen(item["url"], timeout=120) as response, temporary.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
        if temporary.stat().st_size != item["bytes"] or sha256_file(temporary) != item["sha256"]:
            temporary.unlink(missing_ok=True)
            raise RuntimeError(f"download did not match lock: {item['filename']}")
        temporary.replace(target)
        print(f"verified {target.name}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lock", type=Path, default=EXPERIMENT_ROOT / "toolchain.lock.json")
    parser.add_argument("--wheel-dir", type=Path, default=EXPERIMENT_ROOT / ".cache" / "wheels")
    args = parser.parse_args()
    fetch_wheels(args.lock, args.wheel_dir)


if __name__ == "__main__":
    main()
