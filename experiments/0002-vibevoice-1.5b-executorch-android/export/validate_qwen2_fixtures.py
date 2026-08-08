#!/usr/bin/env python3
"""Validate real Qwen2 fixtures, repeat determinism, and eager wrapper agreement."""

from __future__ import annotations

import argparse
import json
import resource
import time
from pathlib import Path
from typing import Any

import torch
from fixture_utils import repo_root, tensor_metadata
from qwen2_backbone import Qwen2Decode, Qwen2Prefill, cache_tensor_names
from qwen2_checkpoint import load_qwen2_backbone

LAYERS = 28
KV_HEADS = 2
HEAD_DIM = 128
HIDDEN_SIZE = 1536
VOCAB_SIZE = 151936
EXPECTED_SOURCE_REVISION = "6dd49cb7200c0367205a5f1e650244259e9e423d"
EXPECTED_MODEL_REVISION = "c00898d257e6b46004e3e2866a47534085fb685a"


def parse_args() -> argparse.Namespace:
    root = repo_root(Path(__file__))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture_dir", type=Path)
    parser.add_argument("--repeat-dir", type=Path)
    parser.add_argument("--model", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--atol", type=float, default=1e-5)
    parser.add_argument("--rtol", type=float, default=1e-4)
    parser.set_defaults(
        output=root
        / "experiments/0002-vibevoice-1.5b-executorch-android/results/qwen2-fixtures-host.json"
    )
    return parser.parse_args()


def load_fixture(
    directory: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    manifest = json.loads((directory / "manifest.json").read_text())
    prefill = torch.load(
        directory / "prefill.pt", map_location="cpu", weights_only=True
    )
    decode = torch.load(directory / "decode.pt", map_location="cpu", weights_only=True)
    return manifest, prefill, decode


def tensors(payload: dict[str, Any]) -> dict[str, torch.Tensor]:
    result: dict[str, torch.Tensor] = {}
    for name, value in payload.items():
        if isinstance(value, (tuple, list)):
            result.update({f"{name}.{index}": item for index, item in enumerate(value)})
        elif isinstance(value, torch.Tensor):
            result[name] = value
    return result


def compare_tuple(
    actual: tuple[torch.Tensor, ...],
    expected: tuple[torch.Tensor, ...],
    *,
    label: str,
    atol: float,
    rtol: float,
) -> dict[str, Any]:
    if len(actual) != len(expected):
        raise AssertionError(
            f"{label}: expected {len(expected)} outputs, got {len(actual)}"
        )
    maximum = 0.0
    mean_sum = 0.0
    values = 0
    for index, (actual_tensor, expected_tensor) in enumerate(zip(actual, expected)):
        torch.testing.assert_close(
            actual_tensor,
            expected_tensor,
            atol=atol,
            rtol=rtol,
            msg=lambda message, index=index: f"{label} output {index}: {message}",
        )
        difference = (actual_tensor - expected_tensor).abs().float()
        maximum = max(maximum, difference.max().item())
        mean_sum += difference.sum().item()
        values += difference.numel()
    return {
        "outputs": len(actual),
        "max_abs_error": maximum,
        "mean_abs_error": mean_sum / values,
        "atol": atol,
        "rtol": rtol,
        "allclose": True,
    }


def validate_structure(
    manifest: dict[str, Any], prefill: dict[str, Any], decode: dict[str, Any]
) -> dict[str, Any]:
    capacity = manifest["cache_capacity"]
    expected_order = cache_tensor_names(LAYERS)
    assert manifest["source_revision"] == EXPECTED_SOURCE_REVISION
    assert manifest["model_revision"] == EXPECTED_MODEL_REVISION
    assert manifest["cache_order"] == expected_order
    assert len(expected_order) == 56

    prefill_length = prefill["inputs_embeds"].shape[1]
    decode_position = int(decode["cache_position"].item())
    assert 0 < prefill_length < capacity
    assert decode_position == prefill_length
    assert tuple(prefill["inputs_embeds"].shape) == (1, prefill_length, HIDDEN_SIZE)
    assert tuple(decode["inputs_embeds"].shape) == (1, 1, HIDDEN_SIZE)
    assert torch.equal(prefill["cache_position"], torch.arange(prefill_length))
    assert torch.equal(
        prefill["position_ids"], torch.arange(prefill_length).unsqueeze(0)
    )
    assert torch.equal(decode["position_ids"], decode["cache_position"].unsqueeze(0))
    assert (
        torch.count_nonzero(prefill["attention_mask"][:, prefill_length:]).item() == 0
    )
    assert (
        torch.count_nonzero(decode["attention_mask"][:, decode_position + 1 :]).item()
        == 0
    )
    assert torch.all(prefill["attention_mask"][:, :prefill_length] == 1)
    assert torch.all(decode["attention_mask"][:, : decode_position + 1] == 1)

    cache_shape = (1, KV_HEADS, capacity, HEAD_DIM)
    for name, values, occupied in (
        ("prefill post", prefill["post_cache"], prefill_length),
        ("decode pre", decode["pre_cache"], decode_position),
        ("decode post", decode["post_cache"], decode_position + 1),
    ):
        assert len(values) == 56, f"{name}: expected 56 caches"
        for index, value in enumerate(values):
            assert tuple(value.shape) == cache_shape, f"{name} cache {index} shape"
            assert value.dtype == torch.float32, f"{name} cache {index} dtype"
            assert torch.isfinite(value).all(), f"{name} cache {index} is non-finite"
            assert torch.count_nonzero(value[:, :, occupied:]).item() == 0, (
                f"{name} cache {index} has nonzero unused slots"
            )

    for index, (post, decode_pre) in enumerate(
        zip(prefill["post_cache"], decode["pre_cache"])
    ):
        assert torch.equal(post, decode_pre), f"cache handoff {index} differs"
    for index, (before, after) in enumerate(
        zip(decode["pre_cache"], decode["post_cache"])
    ):
        assert torch.equal(
            before[:, :, :decode_position], after[:, :, :decode_position]
        ), f"decode cache {index} changed an occupied prefix slot"
        assert torch.count_nonzero(after[:, :, decode_position]).item() > 0, (
            f"decode cache {index} did not populate its new slot"
        )

    floating = [
        value
        for value in (*tensors(prefill).values(), *tensors(decode).values())
        if value.is_floating_point()
    ]
    assert all(torch.isfinite(value).all() for value in floating)
    return {
        "status": "passed",
        "prefill_length": prefill_length,
        "decode_position": decode_position,
        "cache_order": expected_order,
        "cache_tensor_count": 56,
        "cache_shape": list(cache_shape),
        "finite_float_tensor_count": len(floating),
        "cache_handoff_exact": True,
        "unused_slots_zero": True,
    }


def validate_determinism(
    first: tuple[dict[str, Any], dict[str, Any], dict[str, Any]],
    second: tuple[dict[str, Any], dict[str, Any], dict[str, Any]],
) -> dict[str, Any]:
    first_manifest, first_prefill, first_decode = first
    second_manifest, second_prefill, second_decode = second
    assert first_manifest == second_manifest
    compared = 0
    for label, left, right in (
        ("prefill", first_prefill, second_prefill),
        ("decode", first_decode, second_decode),
    ):
        left_tensors = tensors(left)
        right_tensors = tensors(right)
        assert list(left_tensors) == list(right_tensors), (
            f"{label} tensor order differs"
        )
        for name in left_tensors:
            assert torch.equal(left_tensors[name], right_tensors[name]), (
                f"{label}.{name} is not exactly deterministic"
            )
            compared += 1
    return {"status": "passed", "exact": True, "tensors_compared": compared}


def wrapper_inputs(
    payload: dict[str, Any], include_cache: bool
) -> tuple[torch.Tensor, ...]:
    values: tuple[torch.Tensor, ...] = (
        payload["inputs_embeds"],
        payload["attention_mask"],
        payload["position_ids"],
        payload["cache_position"],
    )
    return values + tuple(payload["pre_cache"] if include_cache else ())


def expected_outputs(payload: dict[str, Any]) -> tuple[torch.Tensor, ...]:
    return (
        payload["expected_last_hidden_state"],
        payload["expected_next_token_logits"],
        *payload["post_cache"],
    )


def validate_wrappers(
    model_path: Path,
    prefill_fixture: dict[str, Any],
    decode_fixture: dict[str, Any],
    capacity: int,
    atol: float,
    rtol: float,
) -> dict[str, Any]:
    started = time.perf_counter()
    backbone, lm_head = load_qwen2_backbone(model_path, dtype=torch.float32)
    options = {
        "num_hidden_layers": LAYERS,
        "num_key_value_heads": KV_HEADS,
        "head_dim": HEAD_DIM,
        "cache_capacity": capacity,
    }
    prefill = Qwen2Prefill(backbone, lm_head, **options).eval()
    decode = Qwen2Decode(backbone, lm_head, **options).eval()
    with torch.no_grad():
        actual_prefill = prefill(*wrapper_inputs(prefill_fixture, False))
        actual_decode = decode(*wrapper_inputs(decode_fixture, True))
    return {
        "status": "passed",
        "prefill": compare_tuple(
            actual_prefill,
            expected_outputs(prefill_fixture),
            label="prefill",
            atol=atol,
            rtol=rtol,
        ),
        "decode": compare_tuple(
            actual_decode,
            expected_outputs(decode_fixture),
            label="decode",
            atol=atol,
            rtol=rtol,
        ),
        "wall_seconds": time.perf_counter() - started,
    }


def main() -> None:
    args = parse_args()
    started = time.perf_counter()
    fixture = load_fixture(args.fixture_dir.resolve())
    manifest, prefill, decode = fixture
    result: dict[str, Any] = {
        "schema_version": 1,
        "component": "qwen2_real_prefill_decode_fixtures",
        "precision": "fp32",
        "status": "failed",
        "fixture_files": ["manifest.json", "prefill.pt", "decode.pt"],
    }
    try:
        result["structure"] = validate_structure(manifest, prefill, decode)
        if args.repeat_dir:
            repeat = load_fixture(args.repeat_dir.resolve())
            validate_structure(*repeat)
            result["determinism"] = validate_determinism(fixture, repeat)
        else:
            result["determinism"] = {"status": "not-run"}
        if args.model:
            result["wrapper_agreement"] = validate_wrappers(
                args.model.resolve(),
                prefill,
                decode,
                manifest["cache_capacity"],
                args.atol,
                args.rtol,
            )
        else:
            result["wrapper_agreement"] = {"status": "not-run"}
        result["status"] = "passed"
    except Exception as error:
        result["error_type"] = type(error).__name__
        result["error"] = str(error)
        raise
    finally:
        result["wall_seconds"] = time.perf_counter() - started
        result["peak_rss_kib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        result["prefill"] = tensor_metadata(prefill["inputs_embeds"])
        result["decode"] = tensor_metadata(decode["inputs_embeds"])
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
