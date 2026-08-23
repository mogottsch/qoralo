#!/usr/bin/env python3
"""Fail-closed local stage checks used verbatim by the phone script and tests."""

from __future__ import annotations

import argparse
import hashlib
import os
import stat
import subprocess
from pathlib import Path


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run(stage: Path, expected_runner_sha: str) -> None:
    stage = stage.resolve()
    runner = stage / "runner"
    manifest = stage / "stage-manifest.sha256"
    if runner.is_symlink() or not runner.exists():
        raise SystemExit("staged runner must exist and must not be a symlink")
    mode = runner.stat().st_mode
    if not stat.S_ISREG(mode):
        raise SystemExit("staged runner must be a regular file")
    actual = sha(runner)
    if actual != expected_runner_sha:
        raise SystemExit(
            f"staged runner hash mismatch: expected {expected_runner_sha}, got {actual}"
        )
    if not os.access(runner, os.X_OK) or mode & 0o111 == 0:
        raise SystemExit("staged runner is not executable")
    if manifest.is_symlink() or not manifest.is_file():
        raise SystemExit("stage manifest must be a regular non-symlink file")
    subprocess.run(
        ["sha256sum", "-c", manifest.name],
        cwd=stage,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )
    print(
        f"phone stage preflight passed: runner_sha256={actual} "
        f"runner_mode={oct(mode & 0o777)}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--expected-runner-sha", required=True)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(args.stage, args.expected_runner_sha)
