import json
import os
import socket
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from resource_lock import AtomicLock, GenerationSlot, LockBusy, acquired_resources, inspect_lock, policy_capacity


def test_owner_metadata_and_contention(tmp_path, monkeypatch):
    monkeypatch.setenv("PI_AGENT_NAME", "test-agent")
    first = AtomicLock(tmp_path / "heavy-ram.lock", "task-test").acquire()
    owner = json.loads((first.path / "owner.json").read_text())
    assert owner["owner"] == "test-agent" and owner["pid"] == os.getpid() and owner["task"] == "task-test"
    with pytest.raises(LockBusy, match='"state": "live"'):
        AtomicLock(first.path, "other").acquire()
    first.release()
    assert not first.path.exists()


def test_cleanup_on_failure(tmp_path):
    with pytest.raises(RuntimeError):
        with acquired_resources(tmp_path, "task", heavy_ram=True, phone=True):
            raise RuntimeError("failure")
    assert list(tmp_path.iterdir()) == []


def test_stale_lock_is_reported_and_never_stolen(tmp_path):
    path = tmp_path / "phone.lock"; path.mkdir()
    (path / "owner.json").write_text(json.dumps({"host": socket.gethostname(), "pid": 2147483647, "task": "dead", "token": "x"}))
    report = inspect_lock(path)
    assert report["state"] == "stale" and report["safe_to_remove"] is False
    with pytest.raises(LockBusy, match='"state": "stale"'):
        AtomicLock(path, "new").acquire()
    assert path.exists()


def test_incomplete_lock_is_safely_unknown(tmp_path):
    path = tmp_path / "heavy-ram.lock"; path.mkdir()
    report = inspect_lock(path)
    assert report["state"] == "occupied_unknown" and report["safe_to_remove"] is False


def test_generation_capacity_one_and_two(tmp_path):
    one = GenerationSlot(tmp_path, 1, "one").acquire()
    with pytest.raises(LockBusy): GenerationSlot(tmp_path, 1, "blocked").acquire()
    one.release()
    a = GenerationSlot(tmp_path, 2, "a").acquire()
    b = GenerationSlot(tmp_path, 2, "b").acquire()
    with pytest.raises(LockBusy): GenerationSlot(tmp_path, 2, "c").acquire()
    a.release(); b.release()
    assert list(tmp_path.iterdir()) == []


def test_policy_is_fail_closed(tmp_path):
    path = tmp_path / "policy.json"
    for valid in (1, 2):
        path.write_text(json.dumps({"generation_slots": valid}))
        assert policy_capacity(path) == valid
    for invalid in (0, 3, True, "2", None):
        path.write_text(json.dumps({"generation_slots": invalid}))
        with pytest.raises(ValueError): policy_capacity(path)


def test_release_refuses_foreign_owner(tmp_path):
    lock = AtomicLock(tmp_path / "phone.lock", "task").acquire()
    owner_path = lock.path / "owner.json"
    owner = json.loads(owner_path.read_text()); owner["token"] = "replaced"; owner_path.write_text(json.dumps(owner))
    with pytest.raises(RuntimeError, match="no longer owned"): lock.release()
    assert lock.path.exists()
