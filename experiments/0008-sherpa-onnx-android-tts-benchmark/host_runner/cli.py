"""Command line interface. Staging and model execution are deliberately separate."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .runner import DeviceRunner, SubprocessCommands


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Fail-closed experiment 0008 Android runner")
    p.add_argument("--lock", type=Path, default=Path("artifacts/locks/phone.lock"))
    p.add_argument("--artifacts", type=Path, default=Path("artifacts/0008/device-runs"))
    commands = p.add_subparsers(dest="command", required=True)
    ready = commands.add_parser("ready", help="read-only exact-device readiness under the phone lock")
    ready.set_defaults(action="ready")
    stage = commands.add_parser("stage", help="install APK and stage one verified model")
    stage.add_argument("--apk", type=Path, required=True)
    stage.add_argument("--apk-sha256", required=True)
    stage.add_argument("--model-id", required=True)
    stage.add_argument("--inventory", type=Path, required=True)
    stage.add_argument("--model-dir", type=Path, required=True)
    stage.set_defaults(action="stage")
    run = commands.add_parser("run", help="run one staged candidate in a fresh process")
    run.add_argument("--candidate", choices=("pocket", "kokoro", "supertonic_3"), required=True)
    run.add_argument("--descriptor", required=True, help="relative path beneath app external files")
    run.add_argument("--descriptor-sha256", required=True)
    run.add_argument("--baseline-c", type=float)
    run.add_argument("--timeout-seconds", type=float, default=1800)
    run.set_defaults(action="run")
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    runner = DeviceRunner(SubprocessCommands(), lock_path=args.lock, artifact_dir=args.artifacts)
    if args.action == "ready":
        with runner.safe_session() as result:
            print(json.dumps(result, indent=2, sort_keys=True))
    elif args.action == "stage":
        result = runner.stage(args.apk, args.apk_sha256, args.model_id, args.inventory, args.model_dir)
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        path = runner.run_candidate(args.candidate, args.descriptor, args.descriptor_sha256,
                                    baseline_c=args.baseline_c, timeout_seconds=args.timeout_seconds)
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
