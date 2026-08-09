from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "experiments/0002-vibevoice-1.5b-executorch-android/export/capture_recurrent_trace.py"
sys.path.insert(0, str(SCRIPT.parent))
spec = importlib.util.spec_from_file_location("capture_recurrent_trace", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(module)


def test_pcm_metrics_include_range_hash_rms_and_dbfs() -> None:
    metadata = module._pcm_metadata(torch.tensor([[-0.5, 0.5]], dtype=torch.float32))
    assert metadata["min"] == -0.5
    assert metadata["max"] == 0.5
    assert metadata["rms"] == 0.5
    assert metadata["dbfs"] < 0
    assert len(metadata["sha256"]) == 64


def test_calls_zero_through_nineteen_and_boundaries() -> None:
    calls = [
        {"index": index, "selected_token": 7, "diffusion": {"steps": [{}] * 10}, "decoder": {"pcm": {"samples": 3200}}}
        for index in range(20)
    ]
    result = module._validate_calls(calls, 7)
    assert result["pcm_total_samples"] == 64_000
    assert result["pcm_boundaries"] == list(range(0, 64_001, 3200))


def test_cache_equality_is_exact_and_named() -> None:
    left = {"layer_00.key": torch.zeros(1), "layer_00.value": torch.ones(1)}
    assert module._equal_cache(left, {key: value.clone() for key, value in left.items()})
    assert not module._equal_cache(left, {"layer_00.key": torch.zeros(1)})


def test_large_capture_evidence_is_git_ignored() -> None:
    candidate = ROOT / "artifacts/0002/recurrent-calls-0-19/call_000.pt"
    check = subprocess.run(["git", "check-ignore", "-q", str(candidate)], cwd=ROOT)
    assert check.returncode == 0


def test_capture_does_not_select_or_export_an_abi() -> None:
    source = SCRIPT.read_text()
    assert "torch.export" not in source
    assert ".pte" not in source
    assert '"abi_decision": None' in source
