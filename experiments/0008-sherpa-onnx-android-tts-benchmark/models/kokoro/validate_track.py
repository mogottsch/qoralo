#!/usr/bin/env python3
"""Fail-closed validation for the exact Kokoro v1.0 Android deployment track."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any

HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parents[1]
EXACT_VARIANT = "kokoro-multi-lang-v1_0"
EXACT_ARCHIVE_SHA256 = "c133d26353d776da730870dac7da07dbfc9a5e3bc80cc5e8e83ab6e823be7046"
EXACT_MODEL_SHA256 = "c436dc6a842b62aba06af67e40bafcfb9c60ac3af895358f1974ad9a7f7c026b"
EXACT_SOURCE_SHA256 = "c4dff7e15d776bbf8c369f4f056b3bed2f30299d12a3613123598d59a8dce59f"
REQUIRED_FILES = {
    "LICENSE", "model.onnx", "voices.bin", "tokens.txt", "lexicon-us-en.txt",
    "lexicon-gb-en.txt", "lexicon-zh.txt", "date-zh.fst", "number-zh.fst",
    "phone-zh.fst", "espeak-ng-data/en_dict", "espeak-ng-data/phondata",
    "espeak-ng-data/phonindex", "espeak-ng-data/phontab",
    "espeak-ng-data/lang/gmw/en", "espeak-ng-data/lang/gmw/en-US",
}

class TrackError(ValueError):
    pass


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TrackError(f"{path.name} must contain an object")
    return value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_relative(value: str) -> None:
    path = PurePosixPath(value)
    if not value or "\\" in value or path.is_absolute() or ".." in path.parts or "://" in value:
        raise TrackError(f"filesystem path must be relative and asset-free: {value!r}")


def inventory_map(inventory: dict[str, Any]) -> dict[str, dict[str, Any]]:
    files = inventory.get("files")
    if not isinstance(files, list) or len(files) != 377 or inventory.get("total_bytes") != 400786089:
        raise TrackError("inventory count or deployed byte total drifted")
    result: dict[str, dict[str, Any]] = {}
    for item in files:
        if not isinstance(item, dict) or set(item) != {"path", "bytes", "sha256"}:
            raise TrackError("malformed inventory entry")
        path = item["path"]
        safe_relative(path)
        if path in result or not isinstance(item["bytes"], int) or item["bytes"] < 0:
            raise TrackError("duplicate path or invalid size")
        if not isinstance(item["sha256"], str) or len(item["sha256"]) != 64:
            raise TrackError("invalid inventory hash")
        result[path] = item
    if list(result) != sorted(result):
        raise TrackError("inventory is not sorted")
    missing = REQUIRED_FILES - result.keys()
    if missing:
        raise TrackError(f"missing inference/frontend files: {sorted(missing)}")
    if not any(path.startswith("espeak-ng-data/voices/") for path in result):
        raise TrackError("eSpeak voices data is missing")
    return result


def conversion_mapping(source_path: Path) -> dict[int, str]:
    if sha256(source_path) != EXACT_SOURCE_SHA256:
        raise TrackError("pinned v1.0 voice-ordering source hash drifted")
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "id2speaker" for t in node.targets):
            value = ast.literal_eval(node.value)
            if isinstance(value, dict) and all(isinstance(k, int) and isinstance(v, str) for k, v in value.items()):
                return value
    raise TrackError("conversion source has no literal id2speaker map")


def validate(track: dict[str, Any], descriptor: dict[str, Any], config: dict[str, Any],
             proof: dict[str, Any], inventory: dict[str, Any], source_path: Path) -> None:
    archive = track.get("archive", {})
    if track.get("deployment_variant") != EXACT_VARIANT or archive.get("filename") != EXACT_VARIANT + ".tar.bz2":
        raise TrackError("only exact kokoro-multi-lang-v1_0 is accepted")
    if archive.get("sha256") != EXACT_ARCHIVE_SHA256 or archive.get("expected_root") != EXACT_VARIANT:
        raise TrackError("archive revision/hash drifted")
    entries = inventory_map(inventory)
    model = entries["model.onnx"]
    if model != {"bytes": 325630829, "path": "model.onnx", "sha256": EXACT_MODEL_SHA256}:
        raise TrackError("exact v1.0 model pin drifted")
    if conversion_mapping(source_path).get(3) != "af_heart":
        raise TrackError("pinned conversion metadata no longer maps SID 3 to af_heart")
    expected_proof = (3, "af_heart", "3->af_heart", EXACT_MODEL_SHA256, EXACT_ARCHIVE_SHA256)
    observed_proof = (proof.get("speaker_id"), proof.get("speaker"), proof.get("metadata_entry"),
                      proof.get("model_sha256"), proof.get("archive_sha256"))
    if observed_proof != expected_proof:
        raise TrackError("voice proof drifted")
    if config != {
        "model_type": "kokoro", "model": "models/kokoro/model.onnx",
        "voices": "models/kokoro/voices.bin", "tokens": "models/kokoro/tokens.txt",
        "lexicon": "models/kokoro/lexicon-us-en.txt",
        "data_dir": "models/kokoro/espeak-ng-data", "lang": "en-us",
    }:
        raise TrackError("Kokoro English sherpa configuration drifted")
    for key in ("model", "voices", "tokens", "lexicon", "data_dir"):
        safe_relative(config[key])
    if descriptor.get("deployment_variant") != EXACT_VARIANT:
        raise TrackError("descriptor variant is not exact v1.0")
    expected = {"provider": "cpu", "num_threads": 1, "speaker_id": 3,
                "speaker": "af_heart", "language": "en-US",
                "model_storage": "app_specific_external_files", "warm_runs": 3}
    if any(descriptor.get(key) != value for key, value in expected.items()):
        raise TrackError("descriptor provider/thread/speaker/language/storage drifted")
    files = descriptor.get("files")
    if not isinstance(files, dict):
        raise TrackError("descriptor file pins are missing")
    expected_model_files = {f"models/kokoro/{path}": item["sha256"] for path, item in entries.items()}
    for path, digest in expected_model_files.items():
        safe_relative(path)
        if files.get(path) != digest:
            raise TrackError(f"descriptor does not pin deployed file: {path}")
    if set(files) != set(expected_model_files) | {"models/kokoro/sherpa-config.json", "protocol/transcript.txt"}:
        raise TrackError("descriptor contains missing, extra, or unpinned deployed paths")
    if descriptor.get("transcript_sha256") != "350c8d3d57525e65085b1d7c5ec733985c5467797cf50508b5e2a4eee313471f":
        raise TrackError("frozen transcript hash drifted")


def validate_host_report(report: dict[str, Any]) -> None:
    output = report.get("output", {})
    if report.get("status") != "passed" or report.get("android_performance_evidence") is not False or report.get("timing_recorded") is not False:
        raise TrackError("host smoke must pass without becoming Android performance evidence")
    if report.get("deployment_variant") != EXACT_VARIANT or report.get("configuration") != {
        "filesystem_backed": True, "language": "en-US", "num_threads": 1,
        "provider": "cpu", "speaker": "af_heart", "speaker_id": 3,
    }:
        raise TrackError("host smoke configuration drifted")
    if output.get("decoder") != "python_stdlib_wave_full_decode" or output.get("sample_rate_hz") != 24000:
        raise TrackError("host output was not independently decoded at the model sample rate")
    if output.get("non_silent") is not True or not isinstance(output.get("frames"), int) or output["frames"] <= 0:
        raise TrackError("host smoke output is empty or silent")
    if any(key in report for key in ("elapsed_seconds", "rtf", "load_seconds", "synthesis_seconds")):
        raise TrackError("host timing must not be published as benchmark evidence")


def validate_committed(model_root: Path | None = None) -> None:
    track = read_json(HERE / "model-track.json")
    descriptor = read_json(HERE / "benchmark-descriptor.json")
    config = read_json(HERE / "sherpa-config.json")
    proof = read_json(HERE / "voice-proof.json")
    inventory = read_json(HERE / "deployed-inventory.json")
    validate(track, descriptor, config, proof, inventory, HERE / "conversion/generate_voices_bin.py")
    validate_host_report(read_json(HERE / "host-smoke-report.json"))
    if model_root is not None:
        entries = inventory_map(inventory)
        actual_paths = sorted(str(path.relative_to(model_root).as_posix()) for path in model_root.rglob("*") if path.is_file())
        if actual_paths != list(entries):
            raise TrackError("deployed tree differs from the committed inventory")
        for relative, item in entries.items():
            path = model_root / relative
            if path.stat().st_size != item["bytes"] or sha256(path) != item["sha256"]:
                raise TrackError(f"deployed file drifted: {relative}")
        model_bytes = (model_root / "model.onnx").read_bytes()
        marker = b"id2speaker"
        index = model_bytes.find(marker)
        if index < 0 or b"3->af_heart" not in model_bytes[index:index + 2048]:
            raise TrackError("exact ONNX id2speaker metadata does not prove SID 3 is af_heart")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-root", type=Path)
    args = parser.parse_args()
    validate_committed(args.model_root)
    print("Kokoro v1.0 track valid: SID 3 is af_heart; CPU/one-thread English deployment pinned")

if __name__ == "__main__":
    main()
