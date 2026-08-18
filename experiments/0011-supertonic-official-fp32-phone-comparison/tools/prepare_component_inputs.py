#!/usr/bin/env python3
"""Prepare deterministic real component inputs by executing the official FP32 chain."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from pathlib import Path

import numpy as np
import onnxruntime as ort

T = 239
L = 238
SAMPLES = 729746
SEED = 20260813


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def flatten(value):
    if isinstance(value, list):
        for child in value:
            yield from flatten(child)
    else:
        yield value


def preprocess(text: str) -> str:
    replacements = (("–", "-"), ("‑", "-"), ("—", "-"), ("_", " "), ("“", '"'), ("”", '"'), ("‘", "'"), ("’", "'"), ("´", "'"), ("`", "'"), ("[", " "), ("]", " "), ("|", " "), ("/", " "), ("#", " "), ("→", " "), ("←", " "), ("♥", ""), ("☆", ""), ("♡", ""), ("©", ""), ("\\", ""), ("@", " at "), ("e.g.,", "for example, "), ("i.e.,", "that is, "))
    for old, new in replacements:
        text = text.replace(old, new)
    text = "".join(c for c in text if not 0x1F000 <= ord(c) <= 0x1FFFF)
    text = re.sub(r" ([,.!?;:'])", r"\1", text)
    text = re.sub(r'""', '"', text)
    text = re.sub(r"''", "'", text)
    text = re.sub(r"\s+", " ", text).strip()
    if text and text[-1] not in set(".!?;:,'\")]}>…。」』】〉》›»“”‘’"):
        text += "."
    return f"<en>{text}</en>"


def save(path: Path, value: np.ndarray) -> dict:
    value = np.ascontiguousarray(value)
    value.tofile(path)
    return {"path": path.name, "shape": list(value.shape), "dtype": value.dtype.name, "sha256": sha(path)}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--assets", type=Path, required=True)
    p.add_argument("--transcript", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=True)
    text = preprocess(a.transcript.read_text().strip())
    indexer = json.loads((a.assets / "onnx/unicode_indexer.json").read_text())
    codepoints = [ord(c) for char in text for c in unicodedata.normalize("NFKD", char) if ord(c) <= 0xFFFF]
    ids = np.asarray([indexer[c] for c in codepoints], dtype=np.int64).reshape(1, -1)
    assert ids.shape == (1, T) and np.all(ids >= 0)
    mask = np.ones((1, 1, T), dtype=np.float32)
    voice = json.loads((a.assets / "voice_styles/M1.json").read_text())
    ttl = np.asarray(list(flatten(voice["style_ttl"]["data"])), dtype=np.float32).reshape(1, 50, 256)
    dp = np.asarray(list(flatten(voice["style_dp"]["data"])), dtype=np.float32).reshape(1, 8, 16)
    models = a.assets / "onnx"
    options = ort.SessionOptions()
    options.intra_op_num_threads = options.inter_op_num_threads = 1
    def session(name): return ort.InferenceSession(str(models / f"{name}.onnx"), options, providers=["CPUExecutionProvider"])
    duration = np.asarray(session("duration_predictor").run(None, {"text_ids": ids, "style_dp": dp, "text_mask": mask})[0], dtype=np.float32)
    assert duration.shape == (1,) and np.isfinite(duration).all() and duration[0] > 0
    emb = np.asarray(session("text_encoder").run(None, {"text_ids": ids, "style_ttl": ttl, "text_mask": mask})[0], dtype=np.float32)
    latent_mask = np.ones((1, 1, L), dtype=np.float32)
    latent = np.random.default_rng(SEED).standard_normal((1, 144, L)).astype(np.float32)
    total = np.asarray([5], dtype=np.float32)
    vector = session("vector_estimator")
    step0_input = latent.copy()
    for step in range(5):
        latent = np.asarray(vector.run(None, {"noisy_latent": latent, "text_emb": emb, "style_ttl": ttl, "latent_mask": latent_mask, "text_mask": mask, "current_step": np.asarray([step], dtype=np.float32), "total_step": total})[0], dtype=np.float32)
    wave = np.asarray(session("vocoder").run(None, {"latent": latent})[0], dtype=np.float32)
    assert wave.shape == (1, 731136) and np.isfinite(wave).all()
    records = {}
    for name, value in (("text_ids", ids), ("text_mask", mask), ("style_dp", dp), ("style_ttl", ttl), ("duration", duration), ("text_emb", emb), ("step0_noisy_latent", step0_input), ("latent_mask", latent_mask), ("current_step", np.asarray([0], dtype=np.float32)), ("total_step", total), ("final_latent", latent), ("waveform", wave)):
        records[name] = save(a.output / f"{name}.raw", value)
    manifest = {"schema_version": 1, "evidence_type": "real_inputs_from_complete_official_fp32_host_cpu_chain", "contract": {"text_length": T, "latent_length": L, "trimmed_samples": SAMPLES, "seed": SEED, "rng": "numpy PCG64", "vector_steps": 5}, "processed_text": text, "predicted_duration_seconds": float(duration[0]), "records": records, "runtime": {"onnxruntime": ort.__version__, "providers": ort.get_available_providers()}}
    (a.output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
