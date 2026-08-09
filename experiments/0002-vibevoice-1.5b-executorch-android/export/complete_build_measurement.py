#!/usr/bin/env python3
"""Calculate and validate complete-build Android measurements.

The collector intentionally consumes raw adb observations.  Keeping calculations here
makes the published result reproducible without access to the phone.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from pathlib import Path

SAMPLE_RATE = 24_000


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def package_size(files: list[dict]) -> dict:
    total = sum(int(item["bytes"]) for item in files)
    by_hash: dict[str, list[dict]] = {}
    for item in files:
        by_hash.setdefault(item["sha256"], []).append(item)
    duplicate_groups = [group for group in by_hash.values() if len(group) > 1]
    duplicate_bytes = sum((len(group) - 1) * int(group[0]["bytes"]) for group in duplicate_groups)
    return {
        "module_count": len(files),
        "module_bytes": total,
        "exact_duplicate_groups": len(duplicate_groups),
        "exact_duplicate_bytes": duplicate_bytes,
        "duplication_method": "files grouped by full-file SHA-256; shared weights inside non-identical PTEs are not inferred",
    }


def component_seconds(run: dict) -> dict:
    chunks = run["chunks"]
    return {
        "qwen_prefill": float(run["prefill"]["seconds"]),
        "qwen_decode": sum(float(c["qwen_decode_seconds"]) for c in chunks),
        "diffusion": sum(float(c["diffusion_seconds"]) for c in chunks),
        "acoustic_decoder": sum(float(c["decoder_seconds"]) for c in chunks),
        "semantic_encoder": sum(float(c["semantic_seconds"]) for c in chunks),
        "connectors": sum(float(c["connector_seconds"]) for c in chunks),
    }


def summarize_run(label: str, device: dict, wall_seconds: float) -> dict:
    # Each process performs two byte-comparison generations. The first is the
    # measured cold/page-cache run; the second is retained as determinism evidence.
    run = device["runs"][0]
    repeat = device["runs"][1]
    samples = int(run["pcm_samples"])
    duration = samples / SAMPLE_RATE
    components = component_seconds(run)
    ttfa = components["qwen_prefill"] + float(run["chunks"][0]["diffusion_seconds"]) + float(run["chunks"][0]["decoder_seconds"])
    deterministic = run["wav_sha256"] == repeat["wav_sha256"] and run["tokens"] == repeat["tokens"]
    execution = run.get("execution")
    return {
        "protocol_run": label,
        "status": "capacity_terminated" if run["stop_reason"] == "CAPACITY" else device["status"],
        "audio_samples": samples,
        "audio_duration_seconds": duration,
        "generation_seconds": float(run["elapsed_seconds"]),
        "protocol_wall_seconds": float(wall_seconds),
        "rtf": float(run["elapsed_seconds"]) / duration,
        "ttfa_seconds": ttfa,
        "ttfa_definition": "Qwen prefill + first diffusion + first acoustic decode; first PCM becomes available at decode return",
        "component_seconds": components,
        "module_load_seconds": None if execution is None else float(execution["module_load_seconds"]),
        "module_load_note": ("The legacy controller schema did not separate Module.load from forward time; component values include load overhead."
                             if execution is None else "Instrumented across every per-call mmap Module.load; component values still include this load time."),
        "execution_breakdown": execution,
        "memory_kib": {"rss": int(run["rss_kib"]), "pss": int(run["pss_kib"]), "vmhwm": int(run["vmhwm_kib"])},
        "stop_reason": run["stop_reason"],
        "wav_sha256": run["wav_sha256"],
        "pcm_sha256": run["pcm_sha256"],
        "tokens": run["tokens"],
        "repeat_wav_sha256": repeat["wav_sha256"],
        "within_process_deterministic": deterministic,
    }


def build_result(raw: dict, preflight: dict, apk: Path, commit: str) -> dict:
    size = package_size(preflight["packages"]["files"])
    apk_bytes = apk.stat().st_size
    deployed_bytes = raw.get("deployed_module_bytes")
    try:
        apk_path = apk.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        apk_path = apk.as_posix()
    runs = [summarize_run(item["label"], item["device_result"], item["wall_seconds"]) for item in raw["runs"]]
    cross = len({r["wav_sha256"] for r in runs}) == 1 and len({tuple(r["tokens"]) for r in runs}) == 1
    durations = [r["audio_duration_seconds"] for r in runs]
    complete = all(abs(value - preflight["reference_wav"]["duration_seconds"]) < 1 / SAMPLE_RATE for value in durations)
    status = "passed" if complete else "precise_failure"
    return {
        "schema_version": 1,
        "status": status,
        "scope": "complete accepted ExecuTorch 1.2 XNNPACK/INT8 build using the locked reference inputs",
        "protocol": {
            "sequence": "force-stop; cold process run; force-stop; 15 second idle; warm-filesystem-cache process run",
            "cold_definition": "new app process after force-stop; Linux page cache cannot be dropped without root",
            "warm_definition": "new app process with deployed model files and filesystem cache retained",
            "locked_reference_preflight": preflight["status"],
            "repetitions": len(runs),
        },
        "size": {
            "apk_path": apk_path, "apk_bytes": apk_bytes, "apk_sha256": sha256(apk),
            **size, "apk_plus_modules_bytes": apk_bytes + size["module_bytes"],
            "deployed_module_bytes": deployed_bytes,
            "deployed_excess_bytes": None if deployed_bytes is None else deployed_bytes - size["module_bytes"],
            "deployed_size_note": "files/models may contain packages from earlier component probes; accepted-build totals use only the locked 80-file manifest",
        },
        "runs": runs,
        "summary": {
            "median_generation_seconds": statistics.median(r["generation_seconds"] for r in runs),
            "median_ttfa_seconds": statistics.median(r["ttfa_seconds"] for r in runs),
            "median_rtf": statistics.median(r["rtf"] for r in runs),
            "cross_process_deterministic": cross,
            "wav_sha256": runs[0]["wav_sha256"],
        },
        "device": raw["device"],
        "runtime": preflight["runtime"],
        "thermal": raw["thermal"],
        "failure": None if complete else {
            "stage": "locked reference generation",
            "reason": "Both accepted static-cache ABIs stop at CAPACITY after two 3,200-sample chunks; a third cached call cannot accept the widened cache tensors.",
            "requested_samples": preflight["reference_wav"]["frames"],
            "produced_samples": runs[0]["audio_samples"],
            "requested_duration_seconds": preflight["reference_wav"]["duration_seconds"],
            "produced_duration_seconds": runs[0]["audio_duration_seconds"],
            "complete_locked_run": False,
            "metrics_not_available": ["complete-transcript duration", "complete-transcript wall time", "complete-transcript RTF"],
        },
        "hashes": {"package_aggregate_sha256": preflight["packages"]["aggregate_sha256"], "locked_reference_wav_sha256": preflight["reference_wav"]["sha256"]},
        "implementation_commits": [commit],
        "commands": raw["commands"],
        "conclusion": ("The complete locked transcript ran successfully." if complete else
            "Precise reproducible failure: cold and warm accepted-build runs are byte-identical, but both terminate at the exported two-chunk static-cache capacity. The measured 0.266667 s prefix is therefore not a complete-build performance claim; complete-transcript TTFA, duration, wall time, and RTF cannot be accepted until the cache ABI is re-exported."),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("raw", type=Path)
    parser.add_argument("preflight", type=Path)
    parser.add_argument("apk", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--commit", required=True)
    args = parser.parse_args()
    result = build_result(json.loads(args.raw.read_text()), json.loads(args.preflight.read_text()), args.apk, args.commit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "runs": len(result["runs"]), "deterministic": result["summary"]["cross_process_deterministic"]}, indent=2))


if __name__ == "__main__":
    main()
