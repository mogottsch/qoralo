#!/usr/bin/env python3
"""Atomic, fail-closed locks for heavy RAM, phone, and generation slots."""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Iterator

DEFAULT_ROOT = Path(os.environ.get("PREVIEW_LOCK_ROOT", "/tmp/mobile-podcast-preview-locks"))

class LockBusy(RuntimeError):
    pass


def owner_metadata(task: str) -> dict[str, object]:
    return {"schema_version": 1, "owner": os.environ.get("PI_AGENT_NAME", os.environ.get("USER", "unknown")), "pid": os.getpid(), "task": task, "host": socket.gethostname(), "created_at": dt.datetime.now(dt.timezone.utc).isoformat(), "token": uuid.uuid4().hex}


def inspect_lock(path: str | Path) -> dict[str, object]:
    path = Path(path)
    try:
        data = json.loads((path / "owner.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return {"state": "occupied_unknown", "path": str(path), "detail": str(e), "safe_to_remove": False}
    alive = None
    if data.get("host") == socket.gethostname() and isinstance(data.get("pid"), int):
        try: os.kill(int(data["pid"]), 0); alive = True
        except ProcessLookupError: alive = False
        except PermissionError: alive = True
    state = "live" if alive is True else "stale" if alive is False else "remote_or_unknown"
    return {"state": state, "path": str(path), "owner": data, "safe_to_remove": False, "instruction": "Verify host/PID liveness and remove manually; locks are never stolen automatically."}


class AtomicLock:
    def __init__(self, path: str | Path, task: str):
        self.path, self.task, self.metadata = Path(path), task, None

    def acquire(self) -> "AtomicLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try: self.path.mkdir()
        except FileExistsError: raise LockBusy(json.dumps(inspect_lock(self.path), sort_keys=True)) from None
        try:
            self.metadata = owner_metadata(self.task)
            fd, temporary = tempfile.mkstemp(prefix=".owner-", dir=self.path)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self.metadata, f, sort_keys=True); f.write("\n"); f.flush(); os.fsync(f.fileno())
            os.replace(temporary, self.path / "owner.json")
        except BaseException:
            self.release(); raise
        return self

    def release(self) -> None:
        if self.metadata is None: return
        try:
            current = json.loads((self.path / "owner.json").read_text(encoding="utf-8"))
            if current.get("token") != self.metadata.get("token"):
                raise RuntimeError(f"refusing to release lock no longer owned: {self.path}")
            (self.path / "owner.json").unlink(); self.path.rmdir()
        finally: self.metadata = None

    def __enter__(self) -> "AtomicLock": return self.acquire()
    def __exit__(self, *_: object) -> None: self.release()


def policy_capacity(path: str | Path) -> int:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    capacity = data.get("generation_slots")
    if not isinstance(capacity, int) or isinstance(capacity, bool) or capacity not in (1, 2):
        raise ValueError("generation policy must set generation_slots to 1 or 2")
    return capacity


class GenerationSlot:
    def __init__(self, root: str | Path, capacity: int, task: str):
        if capacity not in (1, 2): raise ValueError("generation capacity must be 1 or 2")
        self.root, self.capacity, self.task, self.lock = Path(root), capacity, task, None

    def acquire(self) -> "GenerationSlot":
        reports = []
        for index in range(self.capacity):
            candidate = AtomicLock(self.root / f"generation-{index}.lock", self.task)
            try: candidate.acquire(); self.lock = candidate; return self
            except LockBusy as e: reports.append(json.loads(str(e)))
        raise LockBusy(json.dumps({"resource": "generation", "capacity": self.capacity, "occupied": reports}, sort_keys=True))

    def release(self) -> None:
        if self.lock: self.lock.release(); self.lock = None
    def __enter__(self) -> "GenerationSlot": return self.acquire()
    def __exit__(self, *_: object) -> None: self.release()


@contextlib.contextmanager
def acquired_resources(root: str | Path, task: str, heavy_ram: bool = False, phone: bool = False, generation_capacity: int | None = None) -> Iterator[None]:
    root, held = Path(root), []
    try:
        if heavy_ram: held.append(AtomicLock(root / "heavy-ram.lock", task).acquire())
        if phone: held.append(AtomicLock(root / "phone.lock", task).acquire())
        if generation_capacity is not None: held.append(GenerationSlot(root, generation_capacity, task).acquire())
        yield
    finally:
        for lock in reversed(held): lock.release()


def run_command(args: argparse.Namespace) -> int:
    capacity = policy_capacity(args.generation_policy) if args.generation_policy else None
    if not (args.heavy_ram or args.phone or capacity): raise ValueError("select at least one resource")
    with acquired_resources(args.lock_root, args.task, args.heavy_ram, args.phone, capacity):
        child = subprocess.Popen(args.command)
        old_handlers = {}
        def forward(sig: int, _frame: object) -> None:
            if child.poll() is None: child.send_signal(sig)
        try:
            for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP): old_handlers[sig] = signal.signal(sig, forward)
            return child.wait()
        finally:
            for sig, handler in old_handlers.items(): signal.signal(sig, handler)
            if child.poll() is None: child.terminate(); child.wait()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--lock-root", default=DEFAULT_ROOT); p.add_argument("--task", required=True)
    p.add_argument("--heavy-ram", action="store_true"); p.add_argument("--phone", action="store_true")
    p.add_argument("--generation-policy"); p.add_argument("command", nargs=argparse.REMAINDER)
    args = p.parse_args()
    if args.command and args.command[0] == "--": args.command = args.command[1:]
    if not args.command: p.error("a command is required after --")
    try: raise SystemExit(run_command(args))
    except (LockBusy, ValueError) as e: print(f"resource lock refused: {e}", file=sys.stderr); raise SystemExit(73)

if __name__ == "__main__": main()
