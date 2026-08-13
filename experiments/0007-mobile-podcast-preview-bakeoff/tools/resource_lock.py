#!/usr/bin/env python3
"""One atomic, fail-closed gate for every model load and generation resource."""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import fcntl
import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any, Iterator

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = Path(os.environ.get("PREVIEW_LOCK_ROOT", "/tmp/mobile-podcast-preview-gate"))
DEFAULT_POLICY = ROOT / "protocol" / "model-resource-policy-v1.json"
KINDS = {
    "model-load", "full-generation",
    "smoke-load", "preflight", "generation-realtime", "generation-pocket",
    "generation-kokoro", "capture", "export", "protocol-revision",
}
class LockBusy(RuntimeError):
    pass


def _boot_id() -> str | None:
    try:
        return Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    except OSError:
        return None


def _process_start_ticks(pid: int) -> int | None:
    """Return Linux /proc starttime without being confused by spaces in comm."""
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        return int(fields[19])  # field 22; fields begins at proc field 3
    except (OSError, IndexError, ValueError):
        return None


def host_identity() -> dict[str, str | None]:
    return {"hostname": socket.gethostname(), "boot_id": _boot_id()}


def owner_metadata(task: str, kind: str) -> dict[str, Any]:
    pid = os.getpid()
    return {
        "schema_version": 2,
        "owner": os.environ.get("PI_AGENT_NAME", os.environ.get("USER", "unknown")),
        "task": task,
        "kind": kind,
        "pid": pid,
        "process_start_ticks": _process_start_ticks(pid),
        "host_identity": host_identity(),
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "token": uuid.uuid4().hex,
    }


def inspect_owner(data: dict[str, Any], path: str | Path) -> dict[str, Any]:
    """Prove live/stale only from host, PID, and process-start identity; never age."""
    report: dict[str, Any] = {"path": str(path), "owner": data, "safe_to_remove": False}
    required = (data.get("host_identity"), data.get("pid"), data.get("process_start_ticks"))
    if not isinstance(required[0], dict) or not isinstance(required[1], int) or not isinstance(required[2], int):
        return report | {"state": "stale_unverifiable", "reason": "missing host/PID/start identity", "requires_parent_recovery": True}
    if data["host_identity"] != host_identity():
        return report | {"state": "remote_or_unknown", "reason": "host identity differs", "requires_parent_recovery": True}
    actual_start = _process_start_ticks(data["pid"])
    if actual_start is None:
        return report | {"state": "stale_proven", "reason": "PID is not live on the recorded host boot", "parent_may_recover": True}
    if actual_start != data["process_start_ticks"]:
        return report | {"state": "stale_proven", "reason": "PID was reused; process start identity differs", "parent_may_recover": True}
    return report | {"state": "live", "parent_may_recover": False}


def inspect_lock(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    try:
        data = json.loads((path / "owner.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"state": "stale_unverifiable", "path": str(path), "detail": str(exc), "safe_to_remove": False, "requires_parent_recovery": True}
    return inspect_owner(data, path)


def load_policy(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or data.get("policy_version") not in (1, 2, 3):
        raise ValueError("unsupported model-resource policy")
    mode = data.get("mode")
    pairs = data.get("compatible_concurrent_sets")
    if mode == "exclusive" and pairs == [] and data.get("policy_version") in (1, 3):
        return data
    raise ValueError("resource gate requires a globally exclusive policy")


def _compatible(candidate: str, active: list[str], policy: dict[str, Any]) -> bool:
    # All model loads and full generations (including attempts/retries/repeats)
    # share this one interlocking namespace. Legacy kinds remain exclusive too.
    return not active


@contextlib.contextmanager
def _mutex(root: Path) -> Iterator[None]:
    root.mkdir(parents=True, exist_ok=True)
    fd = os.open(root / ".gate-mutex", os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _write_owner(directory: Path, metadata: dict[str, Any]) -> None:
    directory.mkdir()
    fd, temporary = tempfile.mkstemp(prefix=".owner-", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(metadata, stream, sort_keys=True)
            stream.write("\n"); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, directory / "owner.json")
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        directory.rmdir()
        raise


class ResourceGrant:
    """A logical grant created by one transaction against the interlocking gate."""
    def __init__(self, root: str | Path, task: str, kind: str, policy_path: str | Path = DEFAULT_POLICY):
        if kind not in KINDS:
            raise ValueError(f"unknown resource kind: {kind}")
        if kind == "protocol-revision" and os.environ.get("PREVIEW_PARENT_ORCHESTRATOR") != "1":
            raise PermissionError("only the parent orchestrator may acquire protocol-revision")
        self.root, self.task, self.kind = Path(root), task, kind
        self.policy_path = Path(policy_path)
        self.metadata: dict[str, Any] | None = None
        self.path: Path | None = None

    def acquire(self) -> "ResourceGrant":
        with _mutex(self.root):
            policy = load_policy(self.policy_path)
            grant_root = self.root / "grants"
            grant_root.mkdir(exist_ok=True)
            reports = [inspect_lock(path) for path in sorted(grant_root.iterdir()) if path.is_dir()]
            if any(report["state"] != "live" for report in reports):
                raise LockBusy(json.dumps({"reason": "stale grant requires explicit parent recovery", "grants": reports}, sort_keys=True))
            active = [str(report["owner"].get("kind")) for report in reports]
            if not _compatible(self.kind, active, policy):
                raise LockBusy(json.dumps({"reason": "incompatible active model-resource grant", "requested": self.kind, "grants": reports}, sort_keys=True))
            metadata = owner_metadata(self.task, self.kind)
            path = grant_root / metadata["token"]
            _write_owner(path, metadata)
            self.metadata, self.path = metadata, path
        return self

    def release(self) -> None:
        if self.metadata is None or self.path is None:
            return
        with _mutex(self.root):
            current = json.loads((self.path / "owner.json").read_text(encoding="utf-8"))
            if current.get("token") != self.metadata["token"]:
                raise RuntimeError(f"refusing to release grant no longer owned: {self.path}")
            (self.path / "owner.json").unlink(); self.path.rmdir()
        self.metadata = None; self.path = None

    def __enter__(self) -> "ResourceGrant":
        return self.acquire()

    def __exit__(self, *_: object) -> None:
        self.release()


def install_policy(root: str | Path, candidate: str | Path, destination: str | Path) -> None:
    """Atomic policy transaction; refuses any active reader or grant."""
    root, candidate, destination = Path(root), Path(candidate), Path(destination)
    policy = load_policy(candidate)
    if policy["mode"] != "exclusive":
        raise ValueError("replacement must contain a globally exclusive policy")
    with _mutex(root):
        grant_root = root / "grants"; grant_root.mkdir(exist_ok=True)
        active = [inspect_lock(path) for path in grant_root.iterdir() if path.is_dir()]
        if active:
            raise LockBusy(json.dumps({"reason": "policy update requires no active grants", "grants": active}, sort_keys=True))
        admin = owner_metadata("policy-installer", "policy-update")
        admin_path = grant_root / admin["token"]
        _write_owner(admin_path, admin)
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            fd, temporary = tempfile.mkstemp(prefix=".policy-", dir=destination.parent)
            with os.fdopen(fd, "wb") as out, candidate.open("rb") as src:
                out.write(src.read()); out.flush(); os.fsync(out.fileno())
            os.replace(temporary, destination)
            directory_fd = os.open(destination.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            (admin_path / "owner.json").unlink(); admin_path.rmdir()


def recover_stale(root: str | Path) -> list[str]:
    """Explicit parent recovery. Only grants whose full identity proves stale move aside."""
    if os.environ.get("PREVIEW_PARENT_ORCHESTRATOR") != "1":
        raise PermissionError("explicit stale recovery is parent-only")
    root = Path(root); recovered: list[str] = []
    with _mutex(root):
        grant_root = root / "grants"; grant_root.mkdir(exist_ok=True)
        for path in list(grant_root.iterdir()):
            if not path.is_dir():
                continue
            report = inspect_lock(path)
            if report["state"] != "stale_proven":
                if report["state"] != "live":
                    raise LockBusy("staleness cannot be proven; explicit investigation is required")
                continue
            (path / "owner.json").unlink(); path.rmdir(); recovered.append(str(path))
    return recovered


@contextlib.contextmanager
def acquired_resource(root: str | Path, task: str, kind: str, policy_path: str | Path = DEFAULT_POLICY) -> Iterator[None]:
    grant = ResourceGrant(root, task, kind, policy_path).acquire()
    try:
        yield
    finally:
        grant.release()


def run_command(args: argparse.Namespace) -> int:
    with acquired_resource(args.lock_root, args.task, args.kind, args.policy):
        child = subprocess.Popen(
            args.command,
            env=os.environ | {
                "PREVIEW_RESOURCE_GRANT_KIND": args.kind,
                "PREVIEW_RESOURCE_GRANT_TASK": args.task,
            },
        )
        old_handlers: dict[int, Any] = {}
        def forward(sig: int, _frame: object) -> None:
            if child.poll() is None:
                child.send_signal(sig)
        try:
            for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
                old_handlers[sig] = signal.signal(sig, forward)
            return child.wait()
        finally:
            for sig, handler in old_handlers.items():
                signal.signal(sig, handler)
            if child.poll() is None:
                child.terminate(); child.wait()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="operation", required=True)
    run = sub.add_parser("run")
    run.add_argument("--lock-root", default=DEFAULT_ROOT); run.add_argument("--policy", default=DEFAULT_POLICY)
    run.add_argument("--task", required=True); run.add_argument("--kind", choices=sorted(KINDS), required=True)
    run.add_argument("command", nargs=argparse.REMAINDER)
    install = sub.add_parser("install-policy")
    install.add_argument("candidate"); install.add_argument("destination"); install.add_argument("--lock-root", default=DEFAULT_ROOT)
    recover = sub.add_parser("recover-stale"); recover.add_argument("--lock-root", default=DEFAULT_ROOT)
    args = parser.parse_args()
    try:
        if args.operation == "run":
            if args.command and args.command[0] == "--": args.command = args.command[1:]
            if not args.command: parser.error("a command is required after --")
            raise SystemExit(run_command(args))
        if args.operation == "install-policy": install_policy(args.lock_root, args.candidate, args.destination)
        else: print(json.dumps({"recovered": recover_stale(args.lock_root)}, sort_keys=True))
    except (LockBusy, ValueError, PermissionError) as exc:
        print(f"resource gate refused: {exc}", file=sys.stderr)
        raise SystemExit(73)


if __name__ == "__main__":
    main()
