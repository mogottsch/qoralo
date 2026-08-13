#!/usr/bin/env python3
"""Run matched sherpa-onnx CPU synthesis for one model variant."""
from __future__ import annotations

import argparse
import importlib.metadata
import platform
import time
from pathlib import Path
from typing import Any

from common import (
    EXPERIMENT_ROOT,
    PROJECT_ROOT,
    analyze_wav,
    load_corpus,
    load_json,
    sha256_bytes,
    sha256_file,
    validate_source,
    write_json,
    write_pcm16_wav,
)


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(EXPERIMENT_ROOT).as_posix()
    except ValueError:
        return resolved.relative_to(PROJECT_ROOT).as_posix()


def expected_model(variant: str, source_root: Path, quantization_report: Path) -> tuple[Path, str]:
    if variant == "fp32":
        model = source_root / "model.onnx"
        return model, sha256_file(model)
    report = load_json(quantization_report)
    candidate = report["candidate"]
    model = EXPERIMENT_ROOT / candidate["path"]
    if not model.is_file() or model.stat().st_size != candidate["bytes"] or sha256_file(model) != candidate["sha256"]:
        raise RuntimeError("INT8 candidate does not match quantization report")
    return model, candidate["sha256"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", choices=("fp32", "int8"), required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, default=EXPERIMENT_ROOT / "corpus.json")
    parser.add_argument("--source-manifest", type=Path, default=EXPERIMENT_ROOT / "source-manifest.json")
    parser.add_argument("--quantization-report", type=Path, default=EXPERIMENT_ROOT / "reports" / "quantization-report.json")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    source_root = args.source_root.resolve()
    validate_source(source_root, args.source_manifest, verify_archive=True)
    corpus = load_corpus(args.corpus)
    model, model_digest = expected_model(args.variant, source_root, args.quantization_report)
    output_dir = args.output_dir or EXPERIMENT_ROOT / "generated" / "audio" / args.variant
    report_path = args.report or EXPERIMENT_ROOT / "reports" / f"synthesis-{args.variant}.json"
    output_dir.mkdir(parents=True, exist_ok=True)
    for stale in output_dir.glob("*.wav"):
        stale.unlink()

    import sherpa_onnx

    if importlib.metadata.version("sherpa-onnx") != "1.13.5" or importlib.metadata.version("sherpa-onnx-core") != "1.13.5":
        raise RuntimeError("synthesis requires exact sherpa-onnx 1.13.5 wheels")
    model_config = sherpa_onnx.OfflineTtsModelConfig(
        kokoro=sherpa_onnx.OfflineTtsKokoroModelConfig(
            model=str(model),
            voices=str(source_root / "voices.bin"),
            tokens=str(source_root / "tokens.txt"),
            data_dir=str(source_root / "espeak-ng-data"),
            lexicon=str(source_root / "lexicon-us-en.txt"),
        ),
        provider="cpu",
        num_threads=1,
        debug=False,
    )
    config = sherpa_onnx.OfflineTtsConfig(model=model_config)
    if not config.validate():
        raise RuntimeError(f"sherpa rejected {args.variant} configuration")
    load_started = time.perf_counter()
    tts = sherpa_onnx.OfflineTts(config)
    load_seconds = time.perf_counter() - load_started

    outputs: list[dict[str, Any]] = []
    for utterance in corpus["evaluation"]:
        generation = sherpa_onnx.GenerationConfig()
        generation.sid = 3
        generation.speed = 1.0
        started = time.perf_counter()
        audio = tts.generate(utterance["text"], generation)
        generation_seconds = time.perf_counter() - started
        samples = list(audio.samples)
        temporary = output_dir / f"{utterance['id']}.wav"
        source_metrics = write_pcm16_wav(temporary, samples, audio.sample_rate)
        digest = sha256_file(temporary)
        final_path = output_dir / f"{utterance['id']}--sha256-{digest}.wav"
        temporary.replace(final_path)
        decoded = analyze_wav(final_path)
        if not decoded["integrity"]["non_silent"] or decoded["integrity"]["pcm_clip_count"]:
            raise RuntimeError(f"{args.variant} produced silent or clipped audio: {utterance['id']}")
        outputs.append(
            {
                "id": utterance["id"],
                "text": utterance["text"],
                "text_sha256": sha256_bytes(utterance["text"].encode("utf-8")),
                "wav": decoded,
                "source_float": source_metrics,
                "host_timing_context_only": {
                    "generation_seconds": generation_seconds,
                    "audio_seconds": decoded["format"]["duration_seconds"],
                    "rtf": generation_seconds / decoded["format"]["duration_seconds"],
                },
            }
        )

    report = {
        "schema_version": 1,
        "status": "matched_host_synthesis_passed",
        "variant": args.variant,
        "model": {"path": display_path(model), "bytes": model.stat().st_size, "sha256": model_digest},
        "exact_shared_inputs": {
            "deployment_variant": "kokoro-multi-lang-v1_0",
            "corpus_path": args.corpus.name,
            "corpus_sha256": sha256_file(args.corpus),
            "partition": "evaluation",
            "frontend_and_runtime": "sherpa-onnx 1.13.5 OfflineTts Kokoro",
            "provider": "cpu",
            "num_threads": 1,
            "speaker_id": 3,
            "speaker": "af_heart",
            "speed": 1.0,
            "language": "en-us",
            "utterance_handling": "each corpus entry passed whole; no text splitting",
            "corpus_order": [item["id"] for item in corpus["evaluation"]],
            "session_policy": "fresh OfflineTts session per variant; identical corpus order",
        },
        "runtime": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "python": f"CPython {platform.python_version()}",
            "sherpa_onnx": sherpa_onnx.__version__,
            "sherpa_embedded_onnxruntime": sherpa_onnx.onnxruntime_version,
        },
        "outputs": outputs,
        "host_timing_context_only": {
            "model_load_seconds": load_seconds,
            "median_warmth_not_controlled": True,
            "not_android_evidence": True,
        },
        "android_rtf_pss": {
            "status": "deferred_until_candidate_passes_user_listening_and_is_deployed",
            "evidence_in_this_report": False,
        },
    }
    write_json(report_path, report)
    print(f"wrote {len(outputs)} hash-addressed WAVs and {report_path}")


if __name__ == "__main__":
    main()
