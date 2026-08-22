#!/usr/bin/env python3
"""Summarize a complete 18-process Kokoro staged QNN host run."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

import numpy as np


POLICY_SHA256 = "886bd22eb278b884ccf50e41bb1792d1d36a9612667d8080e90ccd8e3f71231e"
BASELINE_SHA256 = "0aff238d1cc45b7729c59a24a5938230491333c42290e9a1fef8d87da4a2ccd9"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def local(path: str) -> Path:
    return Path(path.removeprefix("/repo/"))


def parse_labeled_path(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("expected label=path")
    label, path = value.split("=", 1)
    if not label or not path:
        raise argparse.ArgumentTypeError("expected label=path")
    return label, Path(path)


def qnn_csv_metrics(path: Path) -> dict[str, object]:
    selected: dict[str, dict[str, int]] = {}
    wanted = {
        "QNN (finalize) time",
        "Number of HVX threads used",
        "Accelerator (execute) time (cycles)",
        "Accelerator (execute) time",
        "QNN (execute) time",
    }
    with path.open(newline="") as stream:
        for row in csv.DictReader(stream):
            event = row["Event Identifier"]
            if event not in wanted:
                continue
            selected.setdefault(event, {})[row["Unit of Measurement"]] = int(
                row["Time"]
            )
    missing = wanted - set(selected)
    if missing:
        raise RuntimeError(f"missing QNN CSV events in {path}: {sorted(missing)}")
    return selected


def tensor(path: Path) -> np.ndarray:
    dtype = "<i8" if path.suffix == ".i64" else "<f4"
    return np.fromfile(path, dtype=dtype)


def compare(reference: np.ndarray, candidate: np.ndarray) -> dict[str, object]:
    if reference.shape != candidate.shape:
        raise RuntimeError("stage tensor shape mismatch")
    if reference.dtype == np.int64:
        indices = np.flatnonzero(reference != candidate)
        return {
            "bit_exact": bool(np.array_equal(reference, candidate)),
            "mismatch_count": int(indices.size),
            "mismatch_indices": indices.tolist(),
            "reference_sum": int(reference.sum()),
            "candidate_sum": int(candidate.sum()),
            "maximum_absolute_difference": int(
                np.max(np.abs(reference - candidate), initial=0)
            ),
        }
    x = reference.astype(np.float64)
    y = candidate.astype(np.float64)
    delta = y - x
    x_norm = np.linalg.norm(x)
    y_norm = np.linalg.norm(y)
    return {
        "bit_exact": bool(np.array_equal(reference, candidate)),
        "all_finite": bool(np.isfinite(candidate).all()),
        "reference_absolute_peak": float(np.max(np.abs(x))),
        "candidate_absolute_peak": float(np.max(np.abs(y))),
        "reference_rms": float(np.sqrt(np.mean(x * x))),
        "candidate_rms": float(np.sqrt(np.mean(y * y))),
        "cosine": float(np.dot(x, y) / (x_norm * y_norm))
        if x_norm and y_norm
        else None,
        "nrmse": float(np.linalg.norm(delta) / x_norm) if x_norm else None,
        "rmse": float(np.sqrt(np.mean(delta * delta))),
        "maximum_absolute_error": float(np.max(np.abs(delta))),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--cpu-checkpoint", type=Path, required=True)
    parser.add_argument("--reconstruction-policy", type=Path, required=True)
    parser.add_argument("--reconstruction-baseline", type=Path, required=True)
    parser.add_argument("--route", required=True)
    parser.add_argument("--transcript-sha256", required=True)
    parser.add_argument("--comparability", choices=("canonical_v2", "noncanonical"), required=True)
    parser.add_argument("--expected-audio-elements", type=int, required=True)
    parser.add_argument("--expected-duration-elements", type=int, required=True)
    parser.add_argument("--expected-duration-sum", type=int, required=True)
    parser.add_argument("--acoustic-record", action="append", default=[], type=parse_labeled_path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text())
    run = json.loads(args.checkpoint.read_text())
    cpu = json.loads(args.cpu_checkpoint.read_text())
    policy = json.loads(args.reconstruction_policy.read_text())
    baseline = json.loads(args.reconstruction_baseline.read_text())
    if sha256(args.reconstruction_policy) != POLICY_SHA256:
        raise RuntimeError("canonical-v2 reconstruction policy hash drift")
    if sha256(args.reconstruction_baseline) != BASELINE_SHA256:
        raise RuntimeError("canonical-v2 reconstruction baseline hash drift")
    if not policy.get("frozen_before_new_qnn_outputs"):
        raise RuntimeError("canonical-v2 reconstruction policy was not frozen")
    if policy["current_environment_baseline"]["record"]["sha256"] != BASELINE_SHA256:
        raise RuntimeError("canonical-v2 reconstruction baseline reference drift")
    if not (
        baseline["fresh_reconstruction_runs"][0]["final_audio_sha256"]
        == baseline["fresh_reconstruction_runs"][1]["final_audio_sha256"]
        == policy["current_environment_baseline"]["audio"]["sha256"]
        and baseline["numerical_comparisons"][
            "final_staged_vs_current_full_qnn_compat_cpu"
        ]["bit_exact"]
        and baseline["current_final_audio_structural"][
            "valid_under_committed_structural_policy"
        ]
    ):
        raise RuntimeError("canonical-v2 reconstruction baseline content drift")
    if (
        policy["historical_evidence"]["wsl_audio_sha256"]
        != "fb8895f6bb9c2ee94dd18f8b9bfdc6f1b36f99e01c40f5806bdd71076acd6d36"
    ):
        raise RuntimeError("historical WSL baseline preservation drift")
    if (
        policy["historical_evidence"]["cross_environment_bit_reproducibility"]
        != "unproven"
    ):
        raise RuntimeError("cross-environment claim boundary drift")
    if run.get("status") != "passed" or run.get("completed_stages") != 18:
        raise RuntimeError("QNN checkpoint is not a complete 18-stage pass")
    if not (
        cpu.get("status") == "passed"
        and cpu.get("completed_stages") == 18
        and cpu.get("provider") == "cpu"
        and cpu.get("optimization") == "disabled"
        and cpu.get("separate_process_per_stage") is True
        and cpu.get("runs_per_stage") == 1
        and len(cpu.get("stages", [])) == 18
    ):
        raise RuntimeError("CPU checkpoint is not the complete current-environment contract")
    manifest_sha = sha256(args.manifest)
    if (
        run["manifest"]["sha256"] != manifest_sha
        or cpu["manifest"]["sha256"] != manifest_sha
    ):
        raise RuntimeError("QNN/CPU manifest hash drift")
    expected_runner = policy["current_environment_baseline"]["runner_sha256"]
    if (
        run["runner"]["sha256"] != expected_runner
        or cpu["runner"]["sha256"] != expected_runner
    ):
        raise RuntimeError("QNN/CPU runner hash drift")
    if run["provider"] != "qnn" or not run["separate_process_per_stage"]:
        raise RuntimeError("QNN execution contract drift")
    if (
        cpu["pipeline_outputs"]["audio"]["sha256"]
        != policy["current_environment_baseline"]["audio"]["sha256"]
    ):
        raise RuntimeError("current-environment CPU audio baseline drift")
    if (
        cpu["pipeline_outputs"]["pred_dur"]["sha256"]
        != policy["current_environment_baseline"]["duration"]["sha256"]
    ):
        raise RuntimeError("current-environment CPU duration baseline drift")

    stages = []
    total_provider_counts: Counter[str] = Counter()
    expected_cpu_stages = policy["current_environment_baseline"]["stage_output_sha256"]
    for spec, frozen_cpu, cpu_stage, qnn_stage in zip(
        manifest["stages"], expected_cpu_stages, cpu["stages"], run["stages"]
    ):
        if not (
            spec["name"]
            == frozen_cpu["name"]
            == cpu_stage["name"]
            == qnn_stage["name"]
            and spec["index"]
            == frozen_cpu["index"]
            == cpu_stage["index"]
            == qnn_stage["index"]
            and spec["model"]["sha256"]
            == cpu_stage["model_sha256"]
            == qnn_stage["model_sha256"]
        ):
            raise RuntimeError("stage identity/model hash drift")
        if cpu_stage["exit_code"] != 0 or cpu_stage["runtime"]["provider"] != "cpu":
            raise RuntimeError(f"current-environment CPU stage did not pass: {spec['name']}")
        cpu_hashes = {
            name: item["sha256"] for name, item in cpu_stage["outputs"].items()
        }
        if cpu_hashes != frozen_cpu["outputs"]:
            raise RuntimeError(f"current-environment CPU stage output drift: {spec['name']}")
        if qnn_stage["exit_code"] != 0 or qnn_stage["runtime"]["provider"] != "qnn":
            raise RuntimeError(f"stage did not pass: {spec['name']}")
        profile_paths = [local(item["path"]) for item in qnn_stage["profile_files"]]
        ort_profiles = [path for path in profile_paths if path.suffix == ".json"]
        qnn_csvs = [path for path in profile_paths if path.name.endswith(".qnn.csv")]
        qnn_logs = [path for path in profile_paths if path.name.endswith("_qnn.log")]
        if len(ort_profiles) != 1 or len(qnn_csvs) != 1 or len(qnn_logs) != 1:
            raise RuntimeError(f"profile file set drift: {spec['name']}")
        provider_counts: Counter[str] = Counter()
        for event in json.loads(ort_profiles[0].read_text()):
            if event.get("cat") == "Node":
                provider_counts[event.get("args", {}).get("provider", "<none>")] += 1
        if provider_counts != {"QNNExecutionProvider": 1}:
            raise RuntimeError(
                f"provider proof failed for {spec['name']}: {provider_counts}"
            )
        total_provider_counts.update(provider_counts)

        comparisons = {}
        for name, qnn_output in qnn_stage["outputs"].items():
            cpu_output = cpu_stage["outputs"][name]
            comparisons[name] = compare(
                tensor(local(cpu_output["path"])), tensor(local(qnn_output["path"]))
            )
        stages.append(
            {
                "index": spec["index"],
                "name": spec["name"],
                "role": spec["role"],
                "model": {
                    "bytes": spec["model"]["bytes"],
                    "sha256": spec["model"]["sha256"],
                    "source_nodes": spec["structure"]["nodes"],
                },
                "execution": {
                    "exit_code": qnn_stage["exit_code"],
                    "wall_seconds": qnn_stage["wall_seconds"],
                    "session_creation_seconds": qnn_stage["runtime"][
                        "session_creation_seconds"
                    ],
                    "run_seconds": qnn_stage["runtime"]["run_seconds"],
                    "ru_maxrss_kib": qnn_stage["runtime"]["max_rss_kib"],
                    "provider_counts": dict(provider_counts),
                    "qnn_profile_metrics": qnn_csv_metrics(qnn_csvs[0]),
                },
                "outputs": qnn_stage["outputs"],
                "comparison_to_same_stage_cpu": comparisons,
                "evidence": {
                    "stdout": qnn_stage["stdout"],
                    "stderr": qnn_stage["stderr"],
                    "ort_profile": {
                        "ignored_path": str(ort_profiles[0]),
                        "bytes": ort_profiles[0].stat().st_size,
                        "sha256": sha256(ort_profiles[0]),
                    },
                    "qnn_csv": {
                        "ignored_path": str(qnn_csvs[0]),
                        "bytes": qnn_csvs[0].stat().st_size,
                        "sha256": sha256(qnn_csvs[0]),
                    },
                    "qnn_log": {
                        "ignored_path": str(qnn_logs[0]),
                        "bytes": qnn_logs[0].stat().st_size,
                        "sha256": sha256(qnn_logs[0]),
                    },
                },
            }
        )

    audio_path = local(run["pipeline_outputs"]["audio"]["path"])
    duration_path = local(run["pipeline_outputs"]["pred_dur"]["path"])
    audio = np.fromfile(audio_path, dtype="<f4")
    duration = np.fromfile(duration_path, dtype="<i8")
    if audio.size != args.expected_audio_elements or duration.size != args.expected_duration_elements:
        raise RuntimeError("final output element count drift")
    peak = float(np.max(np.abs(audio)))
    rms = float(np.sqrt(np.mean(audio.astype(np.float64) ** 2)))
    clipped = int(np.count_nonzero(np.abs(audio) >= 1.0))
    structural = {
        "all_finite": bool(np.isfinite(audio).all()),
        "absolute_peak": peak,
        "rms": rms,
        "samples_abs_ge_1": clipped,
        "valid": bool(
            np.isfinite(audio).all()
            and 1e-4 <= peak < 1.0
            and rms >= 1e-5
            and clipped == 0
        ),
    }
    acoustic_records = {}
    for label, path in args.acoustic_record:
        acoustic_records[label] = {
            "record": json.loads(path.read_text()),
            "path": str(path),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
    result = {
        "schema_version": 1,
        "status": "passed_host_qnn_execution",
        "route": args.route,
        "comparability": args.comparability,
        "transcript_sha256": args.transcript_sha256,
        "source": {
            "manifest": {
                "ignored_path": str(args.manifest),
                "bytes": args.manifest.stat().st_size,
                "sha256": sha256(args.manifest),
            },
            "qnn_checkpoint": {
                "ignored_path": str(args.checkpoint),
                "bytes": args.checkpoint.stat().st_size,
                "sha256": sha256(args.checkpoint),
            },
            "cpu_checkpoint": {
                "ignored_path": str(args.cpu_checkpoint),
                "bytes": args.cpu_checkpoint.stat().st_size,
                "sha256": sha256(args.cpu_checkpoint),
                "baseline_audio_sha256": policy["current_environment_baseline"][
                    "audio"
                ]["sha256"],
                "historical_wsl_audio_sha256": policy["historical_evidence"][
                    "wsl_audio_sha256"
                ],
                "cross_environment_bit_reproducibility": policy[
                    "historical_evidence"
                ]["cross_environment_bit_reproducibility"],
            },
            "reconstruction_policy": {
                "path": str(args.reconstruction_policy),
                "bytes": args.reconstruction_policy.stat().st_size,
                "sha256": sha256(args.reconstruction_policy),
            },
            "reconstruction_baseline": {
                "path": str(args.reconstruction_baseline),
                "bytes": args.reconstruction_baseline.stat().st_size,
                "sha256": sha256(args.reconstruction_baseline),
            },
            "runner": run["runner"],
        },
        "execution": {
            "provider": "QNNExecutionProvider",
            "fallback_disabled": True,
            "separate_process_per_stage": True,
            "completed_stages": len(stages),
            "provider_counts": dict(total_provider_counts),
            "cpu_provider_node_events": total_provider_counts.get(
                "CPUExecutionProvider", 0
            ),
            "sum_session_creation_seconds": sum(
                stage["execution"]["session_creation_seconds"] for stage in stages
            ),
            "sum_single_run_seconds": sum(
                stage["execution"]["run_seconds"][0] for stage in stages
            ),
            "sum_stage_wall_seconds": sum(
                stage["execution"]["wall_seconds"] for stage in stages
            ),
            "maximum_per_process_ru_maxrss_kib": max(
                stage["execution"]["ru_maxrss_kib"] for stage in stages
            ),
            "memory_semantics": "maximum of separate process-lifetime ru_maxrss high-water marks; not additive, not steady PSS, and not component-isolated",
        },
        "stages": stages,
        "outputs": {
            "audio": {
                "ignored_path": str(audio_path),
                "elements": int(audio.size),
                "bytes": audio_path.stat().st_size,
                "sha256": sha256(audio_path),
                "structural": structural,
            },
            "duration": {
                "ignored_path": str(duration_path),
                "elements": int(duration.size),
                "sum": int(duration.sum()),
                "expected_sum": args.expected_duration_sum,
                "bytes": duration_path.stat().st_size,
                "sha256": sha256(duration_path),
            },
        },
        "acoustic_records": acoustic_records,
        "claim_boundary": "Fallback-disabled host QNN session finalization and complete-input execution for all stages, compared to the frozen current-environment 56ce6a CPU baseline. The historical fb8895 WSL record remains separate and cross-environment bit reproducibility is unproven. This is assignment/host execution evidence, not physical phone HTP RPC/HVX proof, benchmark performance, or a listening verdict. Numerical/EOS differences are descriptive, while the structural WAV gate remains separate.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "status": result["status"],
                "execution": result["execution"],
                "outputs": result["outputs"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
