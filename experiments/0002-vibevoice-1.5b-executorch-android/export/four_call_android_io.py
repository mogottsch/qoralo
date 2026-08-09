#!/usr/bin/env python3
"""Package frozen four-call ABI inputs and validate serialized Android results.

This module deliberately performs metadata and byte-level work only.  It does not
load a model, invoke ADB, or acquire the phone.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any, Iterable

ABI_ID = "vibevoice-1.5b-four-call-cache-abi-v1"
SCHEMA_VERSION = 1
CALL_COUNT = 4
CACHE_COUNT = 34


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _validate_tensor_list(items: Any, expected: list[tuple[str, list[int], str]], label: str) -> None:
    _require(isinstance(items, list) and len(items) == len(expected), f"{label}: tensor count mismatch")
    for order, (item, (name, shape, dtype)) in enumerate(zip(items, expected)):
        _require(item.get("order") == order, f"{label}[{order}]: order mismatch")
        _require(item.get("name") == name, f"{label}[{order}]: name mismatch")
        _require(item.get("shape") == shape, f"{label}.{name}: shape mismatch")
        _require(item.get("dtype") == dtype, f"{label}.{name}: dtype mismatch")


def load_abi(path: Path) -> dict[str, Any]:
    """Load and strictly validate the Android-visible subset of the frozen ABI."""
    abi = json.loads(path.read_text(encoding="utf-8"))
    _require(abi.get("schema_version") == 1, "unsupported ABI schema_version")
    _require(abi.get("abi_id") == ABI_ID, "unsupported abi_id")
    _require(abi.get("status") == "frozen_pre_export", "ABI is not frozen")
    methods = abi.get("methods")
    _require(isinstance(methods, dict) and list(methods) == ["acoustic_decode", "semantic_encode"],
             "method ordering mismatch")
    domains = (("acoustic_decode", "decoder", [1, 1, 64], "pcm", [1, 1, 3200]),
               ("semantic_encode", "semantic", [1, 1, 3200], "semantic_output", [1, 1, 128]))
    for method_order, (method_name, domain, primary_shape, output_name, output_shape) in enumerate(domains):
        method = methods[method_name]
        _require(method.get("method_order") == method_order, f"{method_name}: method_order mismatch")
        inputs = [("decoder_latent" if domain == "decoder" else "pcm", primary_shape, "float32"),
                  ("phase", [], "int32"), (f"{domain}_valid_lengths", [CACHE_COUNT], "int32")]
        outputs = [(output_name, output_shape, "float32"),
                   (f"{domain}_next_valid_lengths", [CACHE_COUNT], "int32")]
        caches = method.get("caches")
        _require(isinstance(caches, list) and len(caches) == CACHE_COUNT,
                 f"{method_name}: cache count mismatch")
        for index, cache in enumerate(caches):
            _require(cache.get("order") == index, f"{method_name}: cache order mismatch at {index}")
            _require(cache.get("tensor_name") == f"{domain}_cache_{index:02d}",
                     f"{method_name}: cache name mismatch at {index}")
            shape = cache.get("capacity_shape")
            _require(isinstance(shape, list) and shape and all(isinstance(v, int) and v > 0 for v in shape),
                     f"{method_name}: invalid cache shape at {index}")
            _require(cache.get("dtype") == "float32", f"{method_name}: cache dtype mismatch at {index}")
            inputs.append((f"{domain}_cache_{index:02d}", shape, "float32"))
            outputs.append((f"next_{domain}_cache_{index:02d}", shape, "float32"))
        _validate_tensor_list(method.get("inputs"), inputs, f"{method_name}.inputs")
        _validate_tensor_list(method.get("outputs"), outputs, f"{method_name}.outputs")

    transitions = abi.get("call_transitions")
    _require(isinstance(transitions, list) and len(transitions) == CALL_COUNT,
             "call transition count mismatch")
    previous: dict[str, list[int]] | None = None
    for call, transition in enumerate(transitions):
        _require(transition.get("call") == call, f"transition {call}: call ordering mismatch")
        _require(transition.get("required_phase") == call and transition.get("next_phase") == call + 1,
                 f"transition {call}: phase mismatch")
        for domain in ("decoder", "semantic"):
            pre = transition.get(f"{domain}_pre_valid_lengths")
            post = transition.get(f"{domain}_post_valid_lengths")
            _require(isinstance(pre, list) and len(pre) == CACHE_COUNT, f"transition {call}: {domain} pre lengths")
            _require(isinstance(post, list) and len(post) == CACHE_COUNT, f"transition {call}: {domain} post lengths")
            _require(all(isinstance(v, int) and v >= 0 for v in pre + post),
                     f"transition {call}: invalid {domain} length")
            if previous is not None:
                _require(pre == previous[domain], f"transition {call}: disconnected {domain} lengths")
        _require(transition.get("pcm_sample_range") == [call * 3200, (call + 1) * 3200],
                 f"transition {call}: PCM range mismatch")
        previous = {domain: transition[f"{domain}_post_valid_lengths"] for domain in ("decoder", "semantic")}
    return abi


def _file_record(path: Path, shape: list[int], dtype: str, relative_to: Path) -> dict[str, Any]:
    return {"file": path.relative_to(relative_to).as_posix(), "shape": shape, "dtype": dtype,
            "byte_count": path.stat().st_size, "sha256": sha256(path)}


def prepare(abi_path: Path, latent_paths: Iterable[Path], output_directory: Path,
            artifact_name: str = "audio.pte") -> dict[str, Any]:
    """Create a self-describing directory consumed by ``StreamingProbeActivity``."""
    abi = load_abi(abi_path)
    latents = list(latent_paths)
    _require(len(latents) == CALL_COUNT, "exactly four decoder latent files are required")
    output_directory.mkdir(parents=True, exist_ok=True)
    abi_output = output_directory / "four-call-cache-abi.json"
    shutil.copyfile(abi_path, abi_output)
    calls = []
    for call, source in enumerate(latents):
        _require(source.is_file(), f"missing latent for call {call}: {source}")
        _require(source.stat().st_size == 64 * 4, f"call {call}: latent must be 256-byte FP32")
        destination = output_directory / f"call-{call}-decoder-latent.f32le"
        shutil.copyfile(source, destination)
        calls.append({"call": call, "required_phase": call,
                      "decoder_latent": _file_record(destination, [1, 1, 64], "float32", output_directory)})
    manifest = {"schema_version": SCHEMA_VERSION, "abi_id": ABI_ID,
                "abi": {"file": abi_output.name, "sha256": sha256(abi_output)},
                "artifact": {"file": artifact_name, "methods": ["acoustic_decode", "semantic_encode"]},
                "calls": calls}
    (output_directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def parse_result(manifest_path: Path, device_result_path: Path, output_directory: Path) -> dict[str, Any]:
    """Validate ordering/metadata/hashes and prepare a host-side Android result."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    root = manifest_path.parent
    _require(manifest.get("schema_version") == SCHEMA_VERSION, "unsupported input manifest version")
    _require(manifest.get("abi_id") == ABI_ID, "input manifest ABI mismatch")
    abi_record = manifest.get("abi", {})
    abi_path = root / abi_record.get("file", "")
    _require(abi_path.is_file() and sha256(abi_path) == abi_record.get("sha256"), "ABI file hash mismatch")
    abi = load_abi(abi_path)
    result = json.loads(device_result_path.read_text(encoding="utf-8"))
    _require(result.get("schema_version") == SCHEMA_VERSION, "unsupported device result version")
    _require(result.get("abi_id") == ABI_ID, "device result ABI mismatch")
    _require(result.get("status") == "passed", f"device result status is {result.get('status')!r}")
    calls = result.get("calls")
    _require(isinstance(calls, list) and len(calls) == CALL_COUNT, "device result must contain four calls")
    verified = []
    for call, record in enumerate(calls):
        transition = abi["call_transitions"][call]
        _require(record.get("call") == call, f"device call {call}: ordering mismatch")
        _require(record.get("phase") == call and record.get("next_phase") == call + 1,
                 f"device call {call}: phase mismatch")
        for domain in ("decoder", "semantic"):
            _require(record.get(f"{domain}_pre_valid_lengths") == transition[f"{domain}_pre_valid_lengths"],
                     f"device call {call}: {domain} pre lengths mismatch")
            _require(record.get(f"{domain}_post_valid_lengths") == transition[f"{domain}_post_valid_lengths"],
                     f"device call {call}: {domain} post lengths mismatch")
        files = record.get("outputs")
        _require(isinstance(files, list) and len(files) == 70, f"device call {call}: output count mismatch")
        expected = [("pcm", [1, 1, 3200], "float32"),
                    ("semantic_output", [1, 1, 128], "float32")]
        for domain in ("decoder", "semantic"):
            expected.extend((f"{domain}_cache_{index:02d}",
                             abi["methods"]["acoustic_decode" if domain == "decoder" else "semantic_encode"]
                                ["caches"][index]["capacity_shape"], "float32") for index in range(CACHE_COUNT))
        for order, (file_record, (name, shape, dtype)) in enumerate(zip(files, expected)):
            _require(file_record.get("order") == order and file_record.get("name") == name,
                     f"device call {call}: output ordering mismatch at {order}")
            _require(file_record.get("shape") == shape and file_record.get("dtype") == dtype,
                     f"device call {call}: output metadata mismatch for {name}")
            path = output_directory / file_record.get("file", "")
            byte_count = 4
            for dimension in shape:
                byte_count *= dimension
            _require(path.is_file() and path.stat().st_size == byte_count,
                     f"device call {call}: output bytes mismatch for {name}")
            _require(file_record.get("byte_count") == byte_count and sha256(path) == file_record.get("sha256"),
                     f"device call {call}: output hash mismatch for {name}")
        verified.append({"call": call, "phase": call, "next_phase": call + 1,
                         "output_count": len(files), "outputs_verified": True})
    return {"schema_version": SCHEMA_VERSION, "abi_id": ABI_ID, "status": "prepared",
            "source_device_result": str(device_result_path), "calls": verified}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    package = commands.add_parser("prepare")
    package.add_argument("abi", type=Path); package.add_argument("output", type=Path)
    package.add_argument("latents", nargs=CALL_COUNT, type=Path); package.add_argument("--artifact", default="audio.pte")
    parse = commands.add_parser("parse-result")
    parse.add_argument("manifest", type=Path); parse.add_argument("device_result", type=Path)
    parse.add_argument("device_output", type=Path); parse.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.command == "prepare":
        value = prepare(args.abi, args.latents, args.output, args.artifact)
    else:
        value = parse_result(args.manifest, args.device_result, args.device_output)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(value, indent=2))


if __name__ == "__main__":
    main()
