#!/usr/bin/env python3
"""Resolve the canonical-v2 T235 versus frozen T239 masked-padding gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import unicodedata
from pathlib import Path
from typing import Any

import numpy as np
import onnxruntime as ort
import onnxruntime.capi.onnxruntime_pybind11_state as ort_state

SOURCE_HASHES = {
    "duration_predictor.onnx": "c3eb91414d5ff8a7a239b7fe9e34e7e2bf8a8140d8375ffb14718b1c639325db",
    "text_encoder.onnx": "c7befd5ea8c3119769e8a6c1486c4edc6a3bc8365c67621c881bbb774b9902ff",
    "vector_estimator.onnx": "883ac868ea0275ef0e991524dc64f16b3c0376efd7c320af6b53f5b780d7c61c",
    "vocoder.onnx": "085de76dd8e8d5836d6ca66826601f615939218f90e519f70ee8a36ed2a4c4ba",
    "unicode_indexer.json": "9bf7346e43883a81f8645c81224f786d43c5b57f3641f6e7671a7d6c493cb24f",
}
FROZEN_HASHES = {
    "duration_predictor.onnx": "8a1875ef0f6960ca16fc06814509b1c3258e8f50b04a5d590d3ab6db8c775016",
    "text_encoder.onnx": "769fd1d257674e8624bdea941f7a903d9460051f9845b604cd2c2980f281a8c3",
    "vector_estimator-stable-softplus.onnx": "f2318c54726a034dcc89aa9818a91f1c3db0e3067b9932c7c2dae65957897c7b",
    "vocoder.onnx": "35b90eeae4a01d06f82dccc903a63d23c95eb2d9095ffa0d62f2cf151817c7c7",
}
TRANSCRIPT_SHA = "424b38073a00cf48e4c3ebaa246aec0b6549b3ed56a1bf7cfa26d037fb29db67"
VOICE_SHA = "e35604687f5d23694b8e91593a93eec0e4eca6c0b02bb8ed69139ab2ea6b0a5b"


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require_hashes(root: Path, expected: dict[str, str]) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for name, digest in expected.items():
        path = root / name
        actual = sha_file(path)
        if actual != digest:
            raise SystemExit(f"hash mismatch for {path}: expected {digest}, got {actual}")
        records[name] = {"bytes": path.stat().st_size, "sha256": actual}
    return records


def flatten(value: Any):
    if isinstance(value, list):
        for child in value:
            yield from flatten(child)
    else:
        yield value


def array_record(value: np.ndarray, include_values: bool = False) -> dict[str, Any]:
    array = np.ascontiguousarray(value)
    result: dict[str, Any] = {
        "shape": list(array.shape),
        "dtype": array.dtype.name,
        "bytes": int(array.nbytes),
        "sha256": sha_bytes(array.tobytes()),
    }
    if include_values:
        result["values"] = array.reshape(-1).tolist()
    return result


def metrics(reference: np.ndarray, candidate: np.ndarray) -> dict[str, Any]:
    a = np.asarray(reference)
    b = np.asarray(candidate)
    if a.shape != b.shape:
        raise ValueError(f"metric shape mismatch: {a.shape} versus {b.shape}")
    af = a.astype(np.float64, copy=False).reshape(-1)
    bf = b.astype(np.float64, copy=False).reshape(-1)
    delta = af - bf
    denominator = float(np.linalg.norm(af) * np.linalg.norm(bf))
    return {
        "elements": int(a.size),
        "exact": bool(np.array_equal(a, b)),
        "max_abs": float(np.max(np.abs(delta))),
        "rmse": float(np.sqrt(np.mean(np.square(delta)))),
        "cosine": float(np.dot(af, bf) / denominator) if denominator else None,
    }


def make_session(path: Path) -> ort.InferenceSession:
    options = ort.SessionOptions()
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    return ort.InferenceSession(
        str(path), sess_options=options, providers=["CPUExecutionProvider"]
    )


def evaluate(
    duration: ort.InferenceSession,
    text: ort.InferenceSession,
    ids: np.ndarray,
    mask: np.ndarray,
    style_dp: np.ndarray,
    style_ttl: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    duration_value = np.ascontiguousarray(
        duration.run(
            None, {"text_ids": ids, "style_dp": style_dp, "text_mask": mask}
        )[0],
        dtype=np.float32,
    )
    embedding = np.ascontiguousarray(
        text.run(
            None, {"text_ids": ids, "style_ttl": style_ttl, "text_mask": mask}
        )[0],
        dtype=np.float32,
    )
    return duration_value, embedding


def passed_limits(result: dict[str, Any], policy: dict[str, Any]) -> dict[str, bool]:
    oracle = result["comparisons"]["dynamic_t235_oracle_vs_dynamic_t239_masked"]
    frozen = result["comparisons"]["dynamic_t239_masked_vs_frozen_t239_masked"]
    ol = policy["oracle_equivalence_limits"]
    fl = policy["frozen_reproduction_limits"]
    checks = {
        "oracle_duration": oracle["duration"]["max_abs"] <= ol["duration_max_abs_lte"],
        "oracle_text_max_abs": oracle["text_embedding_semantic_prefix"]["max_abs"]
        <= ol["text_embedding_semantic_prefix_max_abs_lte"],
        "oracle_text_rmse": oracle["text_embedding_semantic_prefix"]["rmse"]
        <= ol["text_embedding_semantic_prefix_rmse_lte"],
        "oracle_text_cosine": oracle["text_embedding_semantic_prefix"]["cosine"]
        >= ol["text_embedding_semantic_prefix_cosine_gte"],
        "oracle_padded_embedding_zero": oracle["padded_text_embedding_abs_max"]
        <= ol["padded_text_embedding_abs_max_lte"],
        "frozen_duration": frozen["duration"]["max_abs"]
        <= fl["duration_max_abs_lte"],
        "frozen_text_max_abs": frozen["text_embedding"]["max_abs"]
        <= fl["text_embedding_max_abs_lte"],
        "frozen_text_rmse": frozen["text_embedding"]["rmse"]
        <= fl["text_embedding_rmse_lte"],
        "frozen_text_cosine": frozen["text_embedding"]["cosine"]
        >= fl["text_embedding_cosine_gte"],
        "pad_payload_invariant": result["pad_payload_probe"]["byte_identical_outputs"],
    }
    return checks


def run(args: argparse.Namespace) -> None:
    policy = json.loads(args.policy.read_text(encoding="utf-8"))
    transcript = args.transcript.read_bytes()
    if len(transcript) != 226 or transcript.endswith(b"\n") or sha_bytes(transcript) != TRANSCRIPT_SHA:
        raise SystemExit("canonical transcript bytes/hash contract failed")
    raw_text = transcript.decode("utf-8")
    processed = f"<en>{raw_text}</en>"
    if len(processed) != 235:
        raise SystemExit(f"expected processed T235, got {len(processed)}")

    source_records = require_hashes(args.source_onnx, SOURCE_HASHES)
    frozen_records = require_hashes(args.frozen, FROZEN_HASHES)
    if sha_file(args.voice) != VOICE_SHA:
        raise SystemExit("M1 voice hash mismatch")

    indexer = np.asarray(
        json.loads((args.source_onnx / "unicode_indexer.json").read_text()),
        dtype=np.int64,
    )
    codepoints = [
        ord(item)
        for character in processed
        for item in unicodedata.normalize("NFKD", character)
        if ord(item) <= 0xFFFF
    ]
    semantic_ids = np.ascontiguousarray(indexer[codepoints].reshape(1, -1))
    if semantic_ids.shape != (1, 235) or np.any(semantic_ids < 0):
        raise SystemExit("canonical text mapping contract failed")
    semantic_mask = np.ones((1, 1, 235), dtype=np.float32)
    candidate_ids = np.pad(semantic_ids, ((0, 0), (0, 4)), constant_values=0)
    candidate_mask = np.pad(
        semantic_mask, ((0, 0), (0, 0), (0, 4)), constant_values=0.0
    )

    voice = json.loads(args.voice.read_text(encoding="utf-8"))
    style_ttl = np.asarray(
        list(flatten(voice["style_ttl"]["data"])), dtype=np.float32
    ).reshape(1, 50, 256)
    style_dp = np.asarray(
        list(flatten(voice["style_dp"]["data"])), dtype=np.float32
    ).reshape(1, 8, 16)

    dynamic_duration = make_session(args.source_onnx / "duration_predictor.onnx")
    dynamic_text = make_session(args.source_onnx / "text_encoder.onnx")
    frozen_duration = make_session(args.frozen / "duration_predictor.onnx")
    frozen_text = make_session(args.frozen / "text_encoder.onnx")

    oracle_duration, oracle_embedding = evaluate(
        dynamic_duration,
        dynamic_text,
        semantic_ids,
        semantic_mask,
        style_dp,
        style_ttl,
    )
    padded_duration, padded_embedding = evaluate(
        dynamic_duration,
        dynamic_text,
        candidate_ids,
        candidate_mask,
        style_dp,
        style_ttl,
    )
    frozen_duration_value, frozen_embedding = evaluate(
        frozen_duration,
        frozen_text,
        candidate_ids,
        candidate_mask,
        style_dp,
        style_ttl,
    )

    payload_records = []
    for filler_id in policy["pad_payload_invariance"]["probe_ids"]:
        probe_ids = candidate_ids.copy()
        probe_ids[:, 235:] = filler_id
        duration_value, embedding = evaluate(
            dynamic_duration,
            dynamic_text,
            probe_ids,
            candidate_mask,
            style_dp,
            style_ttl,
        )
        payload_records.append(
            {
                "filler_id": filler_id,
                "duration_sha256": array_record(duration_value)["sha256"],
                "text_embedding_sha256": array_record(embedding)["sha256"],
            }
        )
    payload_invariant = len(
        {(item["duration_sha256"], item["text_embedding_sha256"]) for item in payload_records}
    ) == 1

    result: dict[str, Any] = {
        "schema_version": 1,
        "experiment": "0022-supertonic-canonical-v2-precompiled-qnn-context",
        "recorded_date": "2026-08-22",
        "gate": "T235 canonical-v2 to frozen T239 masked-padding compatibility",
        "policy": {
            "path": args.policy.as_posix(),
            "sha256": sha_file(args.policy),
        },
        "runtime": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "numpy": np.__version__,
            "onnxruntime": ort.__version__,
            "pybind_module": {
                "file": Path(ort_state.__file__).name,
                "sha256": sha_file(Path(ort_state.__file__)),
            },
            "available_providers": ort.get_available_providers(),
            "selected_provider": "CPUExecutionProvider",
            "threads": {"intra_op": 1, "inter_op": 1},
            "execution_mode": "ORT_SEQUENTIAL",
            "graph_optimization": "ORT_ENABLE_ALL",
        },
        "lineage": {
            "official_assets_revision": "724fb5abbf5502583fb520898d45929e62f02c0b",
            "source_onnx": source_records,
            "frozen_graphs": frozen_records,
            "voice": {
                "path": args.voice.as_posix(),
                "bytes": args.voice.stat().st_size,
                "sha256": VOICE_SHA,
                "identity": "official public M1 / semantic SID5",
            },
        },
        "canonical_input": {
            "transcript": {
                "path": args.transcript.as_posix(),
                "bytes": len(transcript),
                "sha256": TRANSCRIPT_SHA,
                "trailing_newline": False,
            },
            "language_wrapper": "<en>...</en>",
            "processed_utf8_bytes": len(processed.encode("utf-8")),
            "processed_sha256": sha_bytes(processed.encode("utf-8")),
            "codepoints": codepoints,
            "semantic_text_ids": array_record(semantic_ids, include_values=True),
            "semantic_text_mask": array_record(semantic_mask, include_values=True),
            "style_ttl": array_record(style_ttl),
            "style_dp": array_record(style_dp),
        },
        "candidate_t239_input": {
            "padding_side": "right_after_complete_language_wrapper",
            "zero_based_padding_positions": [235, 236, 237, 238],
            "filler_id": 0,
            "filler_is_not_transcript_content": True,
            "semantic_mask_value": 1.0,
            "padding_mask_value": 0.0,
            "text_ids": array_record(candidate_ids, include_values=True),
            "text_mask": array_record(candidate_mask, include_values=True),
        },
        "outputs": {
            "dynamic_t235_oracle": {
                "duration": array_record(oracle_duration, include_values=True),
                "text_embedding": array_record(oracle_embedding),
            },
            "dynamic_t239_masked": {
                "duration": array_record(padded_duration, include_values=True),
                "text_embedding": array_record(padded_embedding),
            },
            "frozen_t239_masked": {
                "duration": array_record(frozen_duration_value, include_values=True),
                "text_embedding": array_record(frozen_embedding),
            },
        },
        "comparisons": {
            "dynamic_t235_oracle_vs_dynamic_t239_masked": {
                "duration": metrics(oracle_duration, padded_duration),
                "text_embedding_semantic_prefix": metrics(
                    oracle_embedding, padded_embedding[:, :, :235]
                ),
                "padded_text_embedding_abs_max": float(
                    np.max(np.abs(padded_embedding[:, :, 235:]))
                ),
            },
            "dynamic_t239_masked_vs_frozen_t239_masked": {
                "duration": metrics(padded_duration, frozen_duration_value),
                "text_embedding": metrics(padded_embedding, frozen_embedding),
            },
        },
        "pad_payload_probe": {
            "records": payload_records,
            "byte_identical_outputs": payload_invariant,
            "interpretation": "Zero masks remove filler-ID payload, but this does not establish sequence-length neutrality.",
        },
    }
    checks = passed_limits(result, policy)
    oracle_checks = [value for name, value in checks.items() if name.startswith("oracle_")]
    frozen_checks = [value for name, value in checks.items() if name.startswith("frozen_")]
    compatible = all(checks.values())
    result["checks"] = checks
    result["decision"] = {
        "compatible": compatible,
        "result": "passed" if compatible else "failed_joint_constraint_incompatibility",
        "oracle_equivalence_passed": all(oracle_checks),
        "frozen_t239_reproduction_passed": all(frozen_checks),
        "pad_payload_invariance_passed": checks["pad_payload_invariant"],
        "reason": (
            "All compatibility checks passed."
            if compatible
            else "Four zero-masked right-padding slots make the filler ID irrelevant, but changing the model text extent from T235 to T239 materially changes the duration and the first 235 text-embedding positions. The exact frozen T239 graphs reproduce that altered T239 calculation, not the dynamic T235 canonical-v2 oracle."
        ),
        "required_action": (
            "continue_to_next_gate"
            if compatible
            else "stop_before_runner_implementation_context_generation_output_or_phone_access"
        ),
        "forbidden_workarounds": [
            "legacy transcript substitution",
            "differently hashed graph re-specialization",
            "calling masked T239 output exact canonical-v2 semantics",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result["decision"], indent=2, sort_keys=True))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-onnx", type=Path, required=True)
    parser.add_argument("--voice", type=Path, required=True)
    parser.add_argument("--frozen", type=Path, required=True)
    parser.add_argument("--transcript", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
