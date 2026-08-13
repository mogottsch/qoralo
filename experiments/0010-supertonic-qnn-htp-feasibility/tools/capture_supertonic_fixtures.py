#!/usr/bin/env python3
"""Capture deterministic, production-shaped Supertonic component fixtures.

This replays the public Supertonic 3 inference contract with the exact
experiment-0008 assets. Raw tensors and audio are local-only; the emitted
manifest contains the hashes and shapes needed for provenance.

Text preprocessing and inference flow follow sherpa-onnx commit
3dc7c569f31ca2cd4a20ed6f7db780327e6714c5 and Supertonic commit
0a98c9f. Both source projects license this logic permissively.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import struct
import sys
import unicodedata
import wave
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import numpy as np
import onnxruntime as ort

EXPECTED_SHA256 = {
    "duration_predictor.int8.onnx": "c3eb91414d5ff8a7a239b7fe9e34e7e2bf8a8140d8375ffb14718b1c639325db",
    "text_encoder.int8.onnx": "c7befd5ea8c3119769e8a6c1486c4edc6a3bc8365c67621c881bbb774b9902ff",
    "vector_estimator.int8.onnx": "20cd86fa5c6effedfda0e7cffe5b0569ca401c440a0c3a1d72bf39286c0db3fd",
    "vocoder.int8.onnx": "e923d60f53f95eb1ce235f1dc33ec56d9c057823c96fa6f8acf98f32b0da6152",
    "tts.json": "42078d3aef1cd43ab43021f3c54f47d2d75ceb4e75f627f118890128b06a0d09",
    "unicode_indexer.bin": "8402ca48e5189a8950138580b0fff64db6f072f24ac07cd54ba8b2fbb9883b30",
    "voice.bin": "67d5209b0ee8ce6c74105ffbe12fe6a7628aea3b4ba2fcb308a4a67938a93ce8",
}
EXPECTED_TRANSCRIPT_SHA256 = (
    "350c8d3d57525e65085b1d7c5ec733985c5467797cf50508b5e2a4eee313471f"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require_exact_inputs(model_root: Path, transcript: Path) -> dict[str, Any]:
    files: dict[str, Any] = {}
    for name, expected in EXPECTED_SHA256.items():
        path = model_root / name
        if not path.is_file():
            raise SystemExit(f"missing exact model asset: {path}")
        actual = sha256_file(path)
        if actual != expected:
            raise SystemExit(
                f"hash mismatch for {path}: expected {expected}, got {actual}"
            )
        files[name] = {"bytes": path.stat().st_size, "sha256": actual}
    transcript_hash = sha256_file(transcript)
    if transcript_hash != EXPECTED_TRANSCRIPT_SHA256:
        raise SystemExit(
            f"transcript hash mismatch: expected {EXPECTED_TRANSCRIPT_SHA256}, "
            f"got {transcript_hash}"
        )
    return files


def preprocess_text(text: str, language: str) -> str:
    """Mirror sherpa-onnx's Supertonic preprocessing for one text chunk."""
    replacements = (
        ("–", "-"),
        ("‑", "-"),
        ("—", "-"),
        ("_", " "),
        ("\u201c", '"'),
        ("\u201d", '"'),
        ("\u2018", "'"),
        ("\u2019", "'"),
        ("´", "'"),
        ("`", "'"),
        ("[", " "),
        ("]", " "),
        ("|", " "),
        ("/", " "),
        ("#", " "),
        ("→", " "),
        ("←", " "),
        ("♥", ""),
        ("☆", ""),
        ("♡", ""),
        ("©", ""),
        ("\\", ""),
        ("@", " at "),
        ("e.g.,", "for example, "),
        ("i.e.,", "that is, "),
    )
    result = text
    for old, new in replacements:
        result = result.replace(old, new)

    result = "".join(ch for ch in result if not 0x1F000 <= ord(ch) <= 0x1FFFF)
    result = re.sub(r" ([,.!?;:'])", r"\1", result)
    result = result.replace("`", "")
    result = re.sub(r'""', '"', result)
    result = re.sub(r"''", "'", result)
    result = re.sub(r"\s+", " ", result).strip()
    terminal_punctuation = set(".!?;:,'\")]}>") | set("…。」』】〉》›»“”‘’")
    if result and result[-1] not in terminal_punctuation:
        result += "."
    return f"<{language}>{result}</{language}>"


def text_tensors(
    text: str, language: str, indexer_path: Path
) -> tuple[np.ndarray, np.ndarray, str]:
    processed = preprocess_text(text, language)
    indexer = np.fromfile(indexer_path, dtype="<i4")
    if indexer.shape != (65536,):
        raise SystemExit(f"unexpected unicode indexer shape: {indexer.shape}")

    codepoints: list[int] = []
    for char in processed:
        for decomposed in unicodedata.normalize("NFKD", char):
            value = ord(decomposed)
            if value <= 0xFFFF:
                codepoints.append(value)
    ids = indexer[np.asarray(codepoints, dtype=np.int64)]
    if np.any(ids < 0):
        bad = [hex(codepoints[i]) for i in np.flatnonzero(ids < 0)[:8]]
        raise SystemExit(f"processed text contains unmapped codepoints: {bad}")
    text_ids = np.ascontiguousarray(ids.reshape(1, -1), dtype=np.int64)
    text_mask = np.ones((1, 1, text_ids.shape[1]), dtype=np.float32)
    return text_ids, text_mask, processed


def load_style(
    voice_path: Path, speaker_id: int
) -> tuple[np.ndarray, np.ndarray, list[int]]:
    payload = voice_path.read_bytes()
    if len(payload) < 6 * 8:
        raise SystemExit("voice.bin is shorter than its six-int64 header")
    dims = list(struct.unpack("<6q", payload[:48]))
    if any(dim <= 0 for dim in dims):
        raise SystemExit(f"invalid voice dimensions: {dims}")
    if speaker_id < 0 or speaker_id >= dims[0] or dims[0] != dims[3]:
        raise SystemExit(f"speaker {speaker_id} is invalid for voice dimensions {dims}")

    ttl_count = math.prod(dims[:3])
    dp_count = math.prod(dims[3:])
    data = np.frombuffer(payload, dtype="<f4", offset=48)
    if data.size != ttl_count + dp_count:
        raise SystemExit(
            f"voice payload mismatch: expected {ttl_count + dp_count} floats, got {data.size}"
        )
    ttl_all = data[:ttl_count].reshape(dims[:3])
    dp_all = data[ttl_count:].reshape(dims[3:])
    style_ttl = np.ascontiguousarray(ttl_all[speaker_id : speaker_id + 1])
    style_dp = np.ascontiguousarray(dp_all[speaker_id : speaker_id + 1])
    return style_ttl, style_dp, dims


def make_session(path: Path) -> ort.InferenceSession:
    options = ort.SessionOptions()
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    return ort.InferenceSession(
        str(path), sess_options=options, providers=["CPUExecutionProvider"]
    )


def clean_name(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("_")
    return cleaned or "tensor"


def array_summary(array: np.ndarray) -> dict[str, Any]:
    values = np.asarray(array)
    finite = (
        bool(np.all(np.isfinite(values)))
        if np.issubdtype(values.dtype, np.floating)
        else True
    )
    summary: dict[str, Any] = {
        "dtype": values.dtype.name,
        "shape": list(values.shape),
        "elements": int(values.size),
        "bytes": int(values.nbytes),
        "finite": finite,
    }
    if values.size and np.issubdtype(values.dtype, np.number):
        numeric = values.astype(np.float64, copy=False)
        summary.update(
            min=float(np.min(numeric)),
            max=float(np.max(numeric)),
            mean=float(np.mean(numeric)),
            rms=float(np.sqrt(np.mean(np.square(numeric)))),
        )
    return summary


def write_array(root: Path, relative: Path, array: np.ndarray) -> dict[str, Any]:
    values = np.ascontiguousarray(array)
    if sys.byteorder != "little":
        raise SystemExit(
            "raw QNN fixture writer currently requires a little-endian host"
        )
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    values.tofile(path)
    result = array_summary(values)
    result.update(path=relative.as_posix(), sha256=sha256_file(path))
    if path.stat().st_size != values.nbytes:
        raise SystemExit(f"short tensor write: {path}")
    return result


def write_named_input_list(path: Path, entries: Iterable[dict[str, str]]) -> None:
    parts = [f"{entry['name']}:={entry['path']}" for entry in entries]
    path.write_text(" ".join(parts) + "\n", encoding="utf-8")


def save_pcm16_wav(path: Path, samples: np.ndarray, sample_rate: int) -> None:
    values = np.asarray(samples, dtype=np.float32).reshape(-1)
    pcm = np.clip(np.rint(values * 32767.0), -32768, 32767).astype("<i2")
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(pcm.tobytes())


def run(args: argparse.Namespace) -> None:
    model_root = args.model_root.resolve()
    transcript_path = args.transcript.resolve()
    output_root = args.output.resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    source_files = require_exact_inputs(model_root, transcript_path)
    raw_text = transcript_path.read_text(encoding="utf-8").strip()
    if not raw_text or len(raw_text) > 300:
        raise SystemExit(
            "the frozen probe expects exactly one non-empty <=300-character chunk"
        )

    config = json.loads((model_root / "tts.json").read_text(encoding="utf-8"))
    sample_rate = int(config["ae"]["sample_rate"])
    base_chunk_size = int(config["ae"]["base_chunk_size"])
    compress = int(config["ttl"]["chunk_compress_factor"])
    latent_dim = int(config["ttl"]["latent_dim"]) * compress

    text_ids, text_mask, processed_text = text_tensors(
        raw_text, args.language, model_root / "unicode_indexer.bin"
    )
    style_ttl, style_dp, voice_dims = load_style(
        model_root / "voice.bin", args.speaker_id
    )

    duration_session = make_session(model_root / "duration_predictor.int8.onnx")
    text_session = make_session(model_root / "text_encoder.int8.onnx")
    vector_session = make_session(model_root / "vector_estimator.int8.onnx")
    vocoder_session = make_session(model_root / "vocoder.int8.onnx")

    duration = np.asarray(
        duration_session.run(
            None,
            {"text_ids": text_ids, "style_dp": style_dp, "text_mask": text_mask},
        )[0],
        dtype=np.float32,
    )
    if duration.size != 1 or not np.all(np.isfinite(duration)) or np.any(duration <= 0):
        raise SystemExit(f"invalid duration predictor output: {duration}")
    duration = np.ascontiguousarray(duration / np.float32(args.speed))

    text_emb = np.ascontiguousarray(
        text_session.run(
            None,
            {"text_ids": text_ids, "style_ttl": style_ttl, "text_mask": text_mask},
        )[0],
        dtype=np.float32,
    )

    predicted_wav_lengths = np.asarray(
        duration * np.float32(sample_rate), dtype=np.int64
    )
    chunk_size = base_chunk_size * compress
    predicted_latent_len = int(
        (float(np.max(duration) * sample_rate) + chunk_size - 1) / chunk_size
    )
    latent_len = args.latent_length or predicted_latent_len
    wav_lengths = (
        np.asarray([args.requested_audio_samples], dtype=np.int64)
        if args.requested_audio_samples
        else predicted_wav_lengths
    )
    if latent_len <= 0 or latent_len > 10000:
        raise SystemExit(f"invalid latent length: {latent_len}")
    if np.any(wav_lengths <= 0) or np.any(wav_lengths > latent_len * chunk_size):
        raise SystemExit(
            f"requested audio length {wav_lengths.tolist()} is incompatible with "
            f"latent length {latent_len} and chunk size {chunk_size}"
        )
    latent_lengths = (wav_lengths + chunk_size - 1) // chunk_size
    positions = np.arange(latent_len, dtype=np.int64)
    latent_mask = np.ascontiguousarray(
        (positions[None, None, :] < latent_lengths[:, None, None]).astype(np.float32)
    )

    rng = np.random.default_rng(args.seed)
    noisy_latent = rng.standard_normal((1, latent_dim, latent_len)).astype(np.float32)
    noisy_latent = np.ascontiguousarray(noisy_latent * latent_mask)
    total_step = np.asarray([args.steps], dtype=np.float32)

    shared_dir = output_root / "shared"
    shared_dir.mkdir(exist_ok=True)
    shared_entries: dict[str, dict[str, Any]] = {}
    for name, value in (
        ("text_emb", text_emb),
        ("style_ttl", style_ttl),
        ("latent_mask", latent_mask),
        ("text_mask", text_mask),
        ("total_step", total_step),
    ):
        shared_entries[name] = write_array(
            output_root, Path("shared") / f"{clean_name(name)}.raw", value
        )

    vector_runs: list[dict[str, Any]] = []
    xt = noisy_latent
    vector_input_names = [item.name for item in vector_session.get_inputs()]
    for step in range(args.steps):
        current_step = np.asarray([step], dtype=np.float32)
        feed = {
            "noisy_latent": xt,
            "text_emb": text_emb,
            "style_ttl": style_ttl,
            "latent_mask": latent_mask,
            "text_mask": text_mask,
            "current_step": current_step,
            "total_step": total_step,
        }
        if set(feed) != set(vector_input_names):
            raise SystemExit(
                f"vector estimator input mismatch: model={vector_input_names}, fixture={list(feed)}"
            )
        step_dir = Path("vector_estimator") / f"step-{step:02d}"
        input_records: dict[str, dict[str, Any]] = {}
        list_entries: list[dict[str, str]] = []
        for name in vector_input_names:
            if name in shared_entries:
                record = shared_entries[name]
            else:
                record = write_array(
                    output_root, step_dir / f"input-{clean_name(name)}.raw", feed[name]
                )
            input_records[name] = record
            list_entries.append({"name": name, "path": record["path"]})
        output = np.ascontiguousarray(
            vector_session.run(None, feed)[0], dtype=np.float32
        )
        if output.shape != xt.shape or not np.all(np.isfinite(output)):
            raise SystemExit(
                f"invalid vector output at step {step}: {output.shape}, expected {xt.shape}"
            )
        output_record = write_array(
            output_root, step_dir / "reference-output.raw", output
        )
        input_list = output_root / step_dir / "input-list.txt"
        write_named_input_list(input_list, list_entries)
        vector_runs.append(
            {
                "step": step,
                "inputs": input_records,
                "input_list": input_list.relative_to(output_root).as_posix(),
                "output": output_record,
            }
        )
        xt = output

    vocoder_input_names = [item.name for item in vocoder_session.get_inputs()]
    if vocoder_input_names != ["latent"]:
        raise SystemExit(f"unexpected vocoder inputs: {vocoder_input_names}")
    vocoder_dir = Path("vocoder")
    vocoder_input = write_array(output_root, vocoder_dir / "input-latent.raw", xt)
    vocoder_input_list = output_root / vocoder_dir / "input-list.txt"
    write_named_input_list(
        vocoder_input_list, [{"name": "latent", "path": vocoder_input["path"]}]
    )
    waveform = np.ascontiguousarray(
        vocoder_session.run(None, {"latent": xt})[0], dtype=np.float32
    )
    if not waveform.size or not np.all(np.isfinite(waveform)):
        raise SystemExit("vocoder emitted invalid audio")
    vocoder_output = write_array(
        output_root, vocoder_dir / "reference-output.raw", waveform
    )
    trimmed = waveform.reshape(-1)[: int(wav_lengths[0])]
    wav_path = output_root / vocoder_dir / "reference-trimmed.wav"
    save_pcm16_wav(wav_path, trimmed, sample_rate)

    manifest = {
        "schema_version": 1,
        "evidence_type": "deterministic_host_component_fixture_not_android_performance",
        "source": {
            "model_root": str(model_root),
            "files": source_files,
            "transcript": {
                "path": str(transcript_path),
                "bytes": transcript_path.stat().st_size,
                "sha256": EXPECTED_TRANSCRIPT_SHA256,
            },
            "sherpa_onnx_revision": "3dc7c569f31ca2cd4a20ed6f7db780327e6714c5",
            "supertonic_reference_revision": "0a98c9f",
        },
        "runtime": {
            "python": sys.version.split()[0],
            "numpy": np.__version__,
            "onnxruntime": ort.__version__,
            "providers": ort.get_available_providers(),
            "selected_provider": "CPUExecutionProvider",
            "intra_op_threads": 1,
            "inter_op_threads": 1,
            "graph_optimization": "ORT_ENABLE_ALL",
        },
        "generation": {
            "speaker_id": args.speaker_id,
            "voice": "M1",
            "language": args.language,
            "steps": args.steps,
            "speed": args.speed,
            "seed": args.seed,
            "rng": "numpy.random.Generator(PCG64)",
            "processed_text": processed_text,
            "processed_text_sha256": hashlib.sha256(
                processed_text.encode()
            ).hexdigest(),
            "voice_dimensions": voice_dims,
            "cpu_duration_seconds": float(duration.reshape(-1)[0]),
            "cpu_predicted_audio_samples": int(predicted_wav_lengths[0]),
            "cpu_predicted_latent_length": predicted_latent_len,
            "requested_audio_samples": int(wav_lengths[0]),
            "requested_audio_samples_source": (
                "experiment-0008 exact host/device output"
                if args.requested_audio_samples
                else "fixture CPU duration predictor"
            ),
            "latent_length": latent_len,
            "latent_length_source": (
                "experiment-0008 exact vocoder output shape"
                if args.latent_length
                else "fixture CPU duration predictor"
            ),
        },
        "text_ids": array_summary(text_ids),
        "shared_inputs": shared_entries,
        "vector_estimator": {
            "model_inputs": vector_input_names,
            "runs": vector_runs,
        },
        "vocoder": {
            "model_inputs": vocoder_input_names,
            "input": vocoder_input,
            "input_list": vocoder_input_list.relative_to(output_root).as_posix(),
            "output": vocoder_output,
            "trimmed_wav": {
                "path": wav_path.relative_to(output_root).as_posix(),
                "bytes": wav_path.stat().st_size,
                "sha256": sha256_file(wav_path),
                "sample_rate_hz": sample_rate,
                "samples": int(trimmed.size),
                "peak_abs": float(np.max(np.abs(trimmed))),
                "rms": float(np.sqrt(np.mean(np.square(trimmed.astype(np.float64))))),
            },
        },
    }
    manifest_path = output_root / "fixture-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "manifest": str(manifest_path),
                "latent_length": latent_len,
                "duration_seconds": float(duration.reshape(-1)[0]),
                "vector_steps": len(vector_runs),
                "vocoder_output_shape": list(waveform.shape),
                "reference_wav": str(wav_path),
            },
            indent=2,
        )
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-root", type=Path, required=True)
    parser.add_argument("--transcript", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--speaker-id", type=int, default=5)
    parser.add_argument("--language", default="en")
    parser.add_argument("--steps", type=int, default=5)
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=20260813)
    parser.add_argument(
        "--latent-length",
        type=int,
        default=0,
        help="Override with an independently proven production latent length",
    )
    parser.add_argument(
        "--requested-audio-samples",
        type=int,
        default=0,
        help="Override with an independently proven production trim length",
    )
    args = parser.parse_args()
    if (
        args.steps <= 0
        or args.speed <= 0
        or args.latent_length < 0
        or args.requested_audio_samples < 0
    ):
        parser.error("steps/speed must be positive and shape overrides non-negative")
    return args


if __name__ == "__main__":
    run(parse_args())
