#!/usr/bin/env python3
"""Build results.json from the raw phone-run files in this directory.
Run from the repository root:  python3 experiments/0014-pocket-fp-onnx-qnn-htp/evidence/phone-bos-check/summarize.py
"""
import json, re, hashlib
from pathlib import Path

E = Path(__file__).resolve().parent
RAW = E / "raw"
RETAINED_FAIL = "cdf77f6ecaecdbb1a95992326675972366b57da864864f7359890b7e2df5c4b6"
ACCEPTED_FIXED_CACHE = "e0638f35870b24fbe675649a0cd49fa69ca6d74060557bfec5336d2d03a21c9a"
assert hashlib.sha256(Path("docs/android-benchmarks/media/0014-pocket-alba-original-dynamic-cpu.wav").read_bytes()).hexdigest() == RETAINED_FAIL
wav = {l.split()[1].removesuffix(".wav"): l.split()[0] for l in (E / "wav-sha256.txt").read_text().splitlines()}
runs = []
for variant in ("runner_orig", "runner_dump", "runner_fixed", "runner_fixed_dump"):
    for rnd in (1, 2):
        tag = f"{variant}-{rnd}"
        r = json.loads((RAW / f"{tag}.json").read_text())
        err = (RAW / f"{tag}.err").read_text().strip()
        words = re.findall(r"\b[0-9a-f]{8}\b", err.split("ptr=")[1].split(" ", 1)[1]) if err.startswith("BOS_AT_RUN") else None
        logits = r["eos_logits"]
        runs.append({
            "run": tag, "exit": int((E / f"{tag}.exit").read_text()),
            "bos_words_before_run": words,
            "bos_all_zero": (set(words) == {"00000000"} and len(words) == 32) if words else None,
            "bos_all_nan": (set(words) == {"7fc00000"} and len(words) == 32) if words else None,
            "first_stop_score": logits[0], "eos_step": r["eos_step"], "frames": r["latent_frames"],
            "audio_seconds": r["audio_seconds"], "max_stop_score": max(logits),
            "wav_sha256": wav[tag],
            "wav_identical_to_retained_failure": wav[tag] == RETAINED_FAIL,
        })
by = {r["run"]: r for r in runs}
summary = {
    "schema_version": 1,
    "device": dict(l.split("=", 1) for l in (E / "identity.txt").read_text().split()),
    "plan": "4 variants x 2 repeats, one window, no retries",
    "retained_failure_wav_sha256": RETAINED_FAIL, "accepted_fixed_cache_wav_sha256": ACCEPTED_FIXED_CACHE,
    "runs": runs,
    "observations": {
        "original_lifetime_bos_all_zero_runs": sum(bool(by[f"runner_dump-{i}"]["bos_all_zero"]) for i in (1, 2)),
        "fixed_lifetime_bos_all_nan_runs": sum(bool(by[f"runner_fixed_dump-{i}"]["bos_all_nan"]) for i in (1, 2)),
        "unmodified_original_run1_wav_identical_to_retained_failure": by["runner_orig-1"]["wav_identical_to_retained_failure"],
        "unmodified_original_run2_wav_identical_to_retained_failure": by["runner_orig-2"]["wav_identical_to_retained_failure"],
        "unmodified_original_runs_differ": by["runner_orig-1"]["first_stop_score"] != by["runner_orig-2"]["first_stop_score"],
        "fixed_runs_all_stop_at_53": all(by[f"{v}-{i}"]["eos_step"] == 53 for v in ("runner_fixed", "runner_fixed_dump") for i in (1, 2)),
        "fixed_runs_identical_wav": len({by[f"{v}-{i}"]["wav_sha256"] for v in ("runner_fixed", "runner_fixed_dump") for i in (1, 2)}) == 1,
        "original_runs_never_stop": all(by[f"{v}-{i}"]["eos_step"] == -1 for v in ("runner_orig", "runner_dump") for i in (1, 2)),
    },
    "limits": [
        "Old phone executable a11685f5... is not retained; the unmodified retained source was rebuilt (NDK 27.0.12077973, same ORT 1.27.1 android library).",
        "Graphs are the 0024 same-size reconstruction (flow_lm_main ce8d8701...), not the lost original 021288bd...; the failing run still reproduced the retained WAV byte for byte.",
        "The BOS dump is only in the dump builds; it may perturb allocation. The unmodified original's BOS bytes were not observed in run 1 or run 2.",
        "Unmodified original run 2 produced a different wrong result, so the original failure is nondeterministic undefined behaviour.",
        "No explanation is given for why this allocator returned zeros. No new listening verdicts.",
    ],
}
(E / "results.json").write_text(json.dumps(summary, indent=1) + "\n")
print(json.dumps(summary["observations"], indent=1))
for r in runs: print(r["run"], r["first_stop_score"], r["eos_step"], r["frames"], r["bos_all_zero"], r["bos_all_nan"], r["wav_identical_to_retained_failure"])
