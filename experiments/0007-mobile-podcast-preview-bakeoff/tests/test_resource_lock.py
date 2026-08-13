import json
import os
import socket
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from resource_lock import (DEFAULT_POLICY, LockBusy, ResourceGrant, host_identity,
                           inspect_lock, install_policy, owner_metadata, recover_stale)


def exclusive_policy(path):
    path.write_text(json.dumps({
        "schema_version": 1, "policy_version": 3, "mode": "exclusive",
        "compatible_concurrent_sets": [],
        "covered_operations": ["model-load", "full-generation", "smoke-load", "preflight", "generation-realtime", "generation-pocket", "generation-kokoro", "capture", "export", "protocol-revision"],
        "rule": "Every model load and full generation is globally exclusive"
    }))
    return path


def test_initial_policy_is_one_interlocking_exclusive_gate(tmp_path):
    first = ResourceGrant(tmp_path, "task-2", "smoke-load").acquire()
    owner = json.loads((first.path / "owner.json").read_text())
    assert owner["pid"] == os.getpid()
    assert owner["process_start_ticks"] and owner["host_identity"] == host_identity()
    for kind in ("model-load", "full-generation", "preflight", "generation-pocket", "generation-kokoro", "generation-realtime", "capture", "export"):
        with pytest.raises(LockBusy):
            ResourceGrant(tmp_path, "blocked", kind).acquire()
    first.release()


def test_model_loads_attempts_retries_and_repeats_are_mutually_exclusive(tmp_path):
    policy = exclusive_policy(tmp_path / "exclusive.json")
    attempt = ResourceGrant(tmp_path / "gate", "attempt-0", "full-generation", policy).acquire()
    for task, kind in (
        ("retry-1", "full-generation"),
        ("fresh-repeat", "full-generation"),
        ("other-model-load", "model-load"),
        ("legacy-generation", "generation-pocket"),
        ("smoke", "smoke-load"),
    ):
        with pytest.raises(LockBusy):
            ResourceGrant(tmp_path / "gate", task, kind, policy).acquire()
    attempt.release()


def test_legacy_measured_sharing_policy_is_rejected(tmp_path):
    policy = tmp_path / "retired.json"
    policy.write_text(json.dumps({
        "schema_version": 1, "policy_version": 2, "mode": "measured-pocket-kokoro",
        "compatible_concurrent_sets": [["generation-pocket", "generation-kokoro"]]
    }))
    with pytest.raises(ValueError, match="globally exclusive"):
        ResourceGrant(tmp_path / "gate", "task", "generation-pocket", policy).acquire()


def test_cleanup_on_failure(tmp_path):
    with pytest.raises(RuntimeError):
        with ResourceGrant(tmp_path, "task", "capture"):
            raise RuntimeError("failure")
    assert not list((tmp_path / "grants").iterdir())


def test_dead_pid_with_complete_identity_is_reported_not_stolen(tmp_path):
    grant = tmp_path / "grants" / "dead"; grant.mkdir(parents=True)
    metadata = owner_metadata("dead", "capture")
    metadata["pid"] = 2147483647
    (grant / "owner.json").write_text(json.dumps(metadata))
    report = inspect_lock(grant)
    assert report["state"] == "stale_proven" and report["safe_to_remove"] is False
    with pytest.raises(LockBusy, match="explicit parent recovery"):
        ResourceGrant(tmp_path, "new", "generation-pocket").acquire()
    assert grant.exists()


def test_age_or_incomplete_identity_never_proves_staleness(tmp_path):
    grant = tmp_path / "grant"; grant.mkdir()
    (grant / "owner.json").write_text(json.dumps({
        "host_identity": {"hostname": socket.gethostname(), "boot_id": None},
        "pid": 2147483647, "created_at": "1990-01-01T00:00:00Z"
    }))
    report = inspect_lock(grant)
    assert report["state"] == "stale_unverifiable" and not report["safe_to_remove"]


def test_only_parent_explicitly_recovers_proven_stale(tmp_path, monkeypatch):
    grant = tmp_path / "grants" / "dead"; grant.mkdir(parents=True)
    metadata = owner_metadata("dead", "export"); metadata["pid"] = 2147483647
    (grant / "owner.json").write_text(json.dumps(metadata))
    with pytest.raises(PermissionError): recover_stale(tmp_path)
    monkeypatch.setenv("PREVIEW_PARENT_ORCHESTRATOR", "1")
    assert recover_stale(tmp_path) == [str(grant)]
    assert not grant.exists()


def test_policy_replacement_is_atomic_and_refuses_active_grant(tmp_path):
    candidate = exclusive_policy(tmp_path / "candidate.json")
    destination = tmp_path / "installed.json"
    active = ResourceGrant(tmp_path / "gate", "task", "preflight").acquire()
    with pytest.raises(LockBusy): install_policy(tmp_path / "gate", candidate, destination)
    assert not destination.exists()
    active.release()
    install_policy(tmp_path / "gate", candidate, destination)
    assert json.loads(destination.read_text())["mode"] == "exclusive"
    assert not list((tmp_path / "gate" / "grants").iterdir())


def test_release_refuses_foreign_owner(tmp_path):
    grant = ResourceGrant(tmp_path, "task", "capture").acquire()
    owner = json.loads((grant.path / "owner.json").read_text()); owner["token"] = "replaced"
    (grant.path / "owner.json").write_text(json.dumps(owner))
    with pytest.raises(RuntimeError, match="no longer owned"): grant.release()
    assert grant.path.exists()


def test_protocol_revision_is_parent_only_and_exclusive(tmp_path, monkeypatch):
    with pytest.raises(PermissionError): ResourceGrant(tmp_path, "parent", "protocol-revision")
    monkeypatch.setenv("PREVIEW_PARENT_ORCHESTRATOR", "1")
    revision = ResourceGrant(tmp_path, "parent", "protocol-revision").acquire()
    with pytest.raises(LockBusy): ResourceGrant(tmp_path, "worker", "generation-pocket").acquire()
    revision.release()
