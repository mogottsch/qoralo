#!/usr/bin/env python3
"""CPU-only structural/E2E gate for the documented 0024 graph derivative."""
from __future__ import annotations

import argparse
import hashlib
import json
import time
import wave
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import onnx
import onnxruntime as ort


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def session(path: Path) -> ort.InferenceSession:
    options = ort.SessionOptions()
    options.intra_op_num_threads = options.inter_op_num_threads = 1
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    return ort.InferenceSession(str(path), options, providers=["CPUExecutionProvider"])


def init_decoder(model: ort.InferenceSession) -> dict[str, np.ndarray]:
    result: dict[str, np.ndarray] = {}
    types = {"tensor(float)": np.float32, "tensor(int64)": np.int64, "tensor(bool)": np.bool_}
    for meta in model.get_inputs()[1:]:
        dtype = types[meta.type]
        fill = True if dtype == np.bool_ else 0
        result[meta.name] = np.full(tuple(int(x) for x in meta.shape), fill, dtype=dtype)
    if len(result) != 56:
        raise SystemExit(f"decoder state ABI drift: {len(result)}")
    return result


def update_decoder(state: dict[str, np.ndarray], outputs: list[np.ndarray]) -> None:
    for name, value in zip(state, outputs[1:]):
        state[name] = value


def write_wav(path: Path, audio: np.ndarray) -> dict[str, Any]:
    flat = np.asarray(audio, np.float32).reshape(-1)
    if not flat.size or not np.isfinite(flat).all() or not np.any(flat) or np.max(np.abs(flat)) >= 1:
        raise SystemExit("audio structural validity failed")
    pcm = np.clip(np.rint(flat * 32767), -32768, 32767).astype("<i2")
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1); stream.setsampwidth(2); stream.setframerate(24000)
        stream.writeframes(pcm.tobytes())
    return {"path": path.name, "sha256": sha(path), "bytes": path.stat().st_size,
            "samples": int(flat.size), "seconds": flat.size / 24000,
            "peak_float": float(np.max(np.abs(flat))),
            "rms_float": float(np.sqrt(np.mean(flat * flat))),
            "finite": True, "non_silent": True, "unclipped": True}


def graph_contract(path: Path) -> dict[str, Any]:
    model = onnx.load(str(path), load_external_data=False)
    initializers = []
    for value in model.graph.initializer:
        raw = value.raw_data or value.SerializeToString()
        initializers.append(hashlib.sha256(raw).hexdigest())
    return {"path": path.name, "sha256": sha(path), "bytes": path.stat().st_size,
            "nodes": len(model.graph.node), "operators": dict(sorted(Counter(node.op_type for node in model.graph.node).items())),
            "initializers": len(model.graph.initializer),
            "initializer_payload_sha256_multiset": hashlib.sha256("\n".join(sorted(initializers)).encode()).hexdigest(),
            "inputs": [value.name for value in model.graph.input],
            "outputs": [value.name for value in model.graph.output]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--graphs", type=Path, required=True)
    parser.add_argument("--assets", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()
    names = ["text_conditioner.onnx", "flow_prefill_text64.onnx", "flow_ar_bos1.onnx",
             "flow_ar_latent1.onnx", "flow.onnx", "mimi_decoder12.onnx",
             "mimi_decoder6.onnx", "mimi_decoder1.onnx"]
    sessions = {name: session(args.graphs / name) for name in names}
    setup_seconds = time.perf_counter() - start

    ids = np.fromfile(args.assets / "canonical-token-ids-64.i64", dtype="<i8").reshape(1, 64)
    noise = np.fromfile(args.assets / "numpy-randomstate-seed0-temp0p3-292x32.f32", dtype="<f4").reshape(292, 32)
    packed = np.fromfile(args.assets / "alba-flow-cache-v1.f32", dtype="<f4").reshape(6, 2, 1, 126, 16, 64)
    text = sessions["text_conditioner.onnx"].run(None, {"token_ids": ids})[0]
    cache = []
    for layer in range(6):
        for kv in range(2):
            value = np.zeros((1, 16, 512, 64), np.float32)
            value[:, :, -126:] = packed[layer, kv].transpose(0, 2, 1, 3)
            cache.append(value)
    mask = np.full((1, 1, 1, 512), -10000, np.float32)
    mask[..., -126:] = 0
    cache_names = [name for layer in range(6) for name in (f"k_cache_{layer}", f"v_cache_{layer}")]
    result = sessions["flow_prefill_text64.onnx"].run(None, {
        "embeddings": text, "positions": np.arange(126, 190, dtype=np.int64),
        "valid_mask": mask, **dict(zip(cache_names, cache))})
    cache, mask = list(result[:12]), result[12]

    latents: list[np.ndarray] = []
    logits: list[float] = []
    eos: int | None = None
    current: np.ndarray | None = None
    generation_start = time.perf_counter()
    for step in range(292):
        feed = {"positions": np.asarray([190 + step], np.int64), "valid_mask": mask,
                **dict(zip(cache_names, cache))}
        if step == 0:
            result = sessions["flow_ar_bos1.onnx"].run(None, feed)
        else:
            result = sessions["flow_ar_latent1.onnx"].run(None, {"sequence": current, **feed})
        cache, mask = list(result[2:14]), result[14]
        logit = float(result[1][0, 0])
        logits.append(logit)
        if eos is None and logit > -4:
            eos = step
        if eos is not None and step >= eos + 3:
            break
        row = noise[step:step + 1]
        direction = sessions["flow.onnx"].run(None, {"c": result[0], "s": np.asarray([[0]], np.float32),
                                                      "t": np.asarray([[1]], np.float32), "x": row})[0]
        current = (row + direction).reshape(1, 1, 32)
        latents.append(current)
    latent = np.concatenate(latents, axis=1)

    state = init_decoder(sessions["mimi_decoder12.onnx"])
    audio: list[np.ndarray] = []
    frame = 0
    calls = Counter()
    while frame < latent.shape[1]:
        remaining = latent.shape[1] - frame
        frames = 12 if remaining >= 12 else (6 if remaining == 6 else 1)
        model = sessions[f"mimi_decoder{frames}.onnx"]
        result = model.run(None, {"latent": latent[:, frame:frame + frames], **state})
        audio.append(result[0].reshape(-1))
        update_decoder(state, result)
        calls[f"decoder{frames}"] += 1
        frame += frames
    generation_seconds = time.perf_counter() - generation_start
    wav = write_wav(args.output / "host-cpu-derivative.wav", np.concatenate(audio))
    contracts = {name: graph_contract(args.graphs / name) for name in names}
    behavior_matches = eos == 160 and latent.shape[1] == 163 and wav["samples"] == 312960
    report = {
        "schema_version": 1, "result": "passed" if behavior_matches else "failed",
        "route": "0024 documented reconstruction derivative of Pocket fixed-Alba text64/cache512 canonical-v2",
        "provider": "CPUExecutionProvider", "setup_seconds": setup_seconds,
        "generation_seconds": generation_seconds, "rtf": generation_seconds / wav["seconds"],
        "eos_step": eos, "latent_frames": int(latent.shape[1]), "decoder_calls": dict(calls),
        "wav": wav, "expected_0014_behavior": {"eos_step": 160, "latent_frames": 163, "samples": 312960},
        "behavior_matches_0014_structure": behavior_matches,
        "graph_contracts": contracts,
        "historical_qnn_assignment_counts_not_raw_onnx_counts": {
            "reason": "0014 reports QNN assignment counts after ORT transformation/constant folding; they are not comparable to raw serialized ONNX node counts recorded here.",
            "validation": "Fresh fallback-disabled QNN assignment remains required for every 0024 derivative before phone use."
        },
        "reconstruction_boundary": "Raw ONNX hashes differ from 0014; pinned weights/exporter and learned operator/initializer ABI are reconstructed and require fresh QNN/E2E/audio validation.",
        "eos_logits": logits,
    }
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: report[key] for key in ("result", "setup_seconds", "generation_seconds", "rtf", "eos_step", "latent_frames", "wav", "behavior_matches_0014_structure")}, indent=2))
    if report["result"] != "passed":
        raise SystemExit("host E2E derivative gate failed")


if __name__ == "__main__":
    main()
