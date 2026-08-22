#!/usr/bin/env python3
"""Build and hash the bounded Android stage without accessing the phone."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import struct
import subprocess
from pathlib import Path
from typing import Any

GRAPH_HASHES = {
    "duration_predictor.onnx": "8a1875ef0f6960ca16fc06814509b1c3258e8f50b04a5d590d3ab6db8c775016",
    "text_encoder.onnx": "769fd1d257674e8624bdea941f7a903d9460051f9845b604cd2c2980f281a8c3",
    "vector_estimator-stable-softplus.onnx": "f2318c54726a034dcc89aa9818a91f1c3db0e3067b9932c7c2dae65957897c7b",
    "vocoder.onnx": "35b90eeae4a01d06f82dccc903a63d23c95eb2d9095ffa0d62f2cf151817c7c7",
}
QNN_HASHES = {
    "libQnnHtp.so": "a09b3af28342331b3ec9e57ecbe42bfe54a5fff37c4323ce5685c395ae3ee604",
    "libQnnHtpPrepare.so": "db0a4c4811fe0947f6f237978190cbaf4cea8fa8bd607ea14fda67d375403c9e",
    "libQnnHtpV73Skel.so": "bd54463547f0234d06045699b1f747b7d9d3e3b581874840af50c295b3124f25",
    "libQnnHtpV73Stub.so": "2912cc4f29cc5163c36c6c58f931bd08b798ccf8545a670a9498549f95b9036f",
    "libQnnSystem.so": "536201ed918f4066f9ef35671198c072faf9ef04af24545f5fae0fc79aa05baa",
}
ORT_HASH = "643c6f6fd3d2b375ca8f2407a1695acaf55320b8e947adc4284665640fdc3ae9"
TRANSCRIPT_HASH = "350c8d3d57525e65085b1d7c5ec733985c5467797cf50508b5e2a4eee313471f"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def copy_checked(source: Path, destination: Path, expected: str | None = None) -> dict[str, Any]:
    if not source.is_file():
        raise SystemExit(f"missing source: {source}")
    actual = sha(source)
    if expected and actual != expected:
        raise SystemExit(f"hash mismatch for {source}: expected {expected}, got {actual}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    if sha(destination) != actual:
        raise SystemExit(f"copy hash mismatch: {destination}")
    return {"source": str(source), "bytes": destination.stat().st_size, "sha256": actual}


def flatten(value: Any):
    if isinstance(value, list):
        for child in value:
            yield from flatten(child)
    else:
        yield value


def write_assets(snapshot: Path, output: Path) -> dict[str, Any]:
    index_source = snapshot / "onnx/unicode_indexer.json"
    voice_source = snapshot / "voice_styles/M1.json"
    indexer = json.loads(index_source.read_text())
    if len(indexer) != 65536 or not all(isinstance(item, int) for item in indexer):
        raise SystemExit("unexpected unicode indexer")
    output.mkdir(parents=True, exist_ok=True)
    index_output = output / "unicode_indexer.bin"
    index_output.write_bytes(struct.pack("<65536i", *indexer))
    voice = json.loads(voice_source.read_text())
    tensors = []
    for name, dims in (("style_ttl", [1, 50, 256]), ("style_dp", [1, 8, 16])):
        item = voice[name]
        values = list(flatten(item["data"]))
        count = 1
        for dimension in dims:
            count *= dimension
        if item["dims"] != dims or item["type"] != "float32" or len(values) != count:
            raise SystemExit(f"unexpected {name}")
        tensors.append(struct.pack(f"<{count}f", *values))
    voice_output = output / "voice.bin"
    voice_output.write_bytes(
        struct.pack("<6q", 1, 50, 256, 1, 8, 16) + b"".join(tensors)
    )
    return {
        "unicode_indexer": {
            "source_sha256": sha(index_source),
            "output_bytes": index_output.stat().st_size,
            "output_sha256": sha(index_output),
        },
        "voice": {
            "source_sha256": sha(voice_source),
            "output_bytes": voice_output.stat().st_size,
            "output_sha256": sha(voice_output),
        },
    }


def run(args: argparse.Namespace) -> None:
    output = args.output.resolve()
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    provenance: dict[str, Any] = {
        "schema_version": 1,
        "experiment": "0023-supertonic-qnn-precompiled-context-startup",
        "status": "phone_stage_prepared_not_executed",
        "runner": copy_checked(args.runner, output / "runner"),
        "runtime": {},
        "source_graphs": {},
        "contexts": {},
    }
    provenance["runner"].update(
        source_sha256=sha(args.runner_source),
        file_output=subprocess.check_output(["file", str(args.runner)], text=True).strip(),
    )
    provenance["runtime"]["libonnxruntime.so"] = copy_checked(
        args.ort, output / "lib/libonnxruntime.so", ORT_HASH
    )
    provenance["runtime"]["libc++_shared.so"] = copy_checked(
        args.libcxx, output / "lib/libc++_shared.so"
    )
    android_lib = args.qairt / "lib/aarch64-android"
    hexagon_lib = args.qairt / "lib/hexagon-v73/unsigned"
    for name, expected in QNN_HASHES.items():
        source = hexagon_lib / name if name == "libQnnHtpV73Skel.so" else android_lib / name
        provenance["runtime"][name] = copy_checked(source, output / "lib" / name, expected)
    for name, expected in GRAPH_HASHES.items():
        provenance["source_graphs"][name] = copy_checked(
            args.graphs / name, output / "source-models" / name, expected
        )
    functional = json.loads(args.functional.read_text())
    for component in ("duration", "text", "vector", "vocoder"):
        descriptor_record = functional["components"][component]["external_context"]["descriptor"]
        binary_record = functional["components"][component]["external_context"]["binary"]
        source_dir = args.contexts / component
        descriptor = source_dir / f"{component}-context.onnx"
        binary = source_dir / f"{component}-context_qnn.bin"
        provenance["contexts"][component] = {
            "descriptor": copy_checked(
                descriptor,
                output / "contexts" / descriptor.name,
                descriptor_record["sha256"],
            ),
            "binary": copy_checked(
                binary, output / "contexts" / binary.name, binary_record["sha256"]
            ),
        }
    provenance["assets"] = write_assets(args.snapshot, output / "assets")
    provenance["transcript"] = copy_checked(
        args.transcript, output / "transcript.txt", TRANSCRIPT_HASH
    )
    for protocol in (args.contract, args.transport):
        copy_checked(protocol, output / "protocol" / protocol.name)

    manifest_lines = []
    manifest_records = []
    for path in sorted(item for item in output.rglob("*") if item.is_file()):
        relative = path.relative_to(output).as_posix()
        digest = sha(path)
        manifest_lines.append(f"{digest}  {relative}")
        manifest_records.append(
            {"path": relative, "bytes": path.stat().st_size, "sha256": digest}
        )
    manifest = output / "stage-manifest.sha256"
    provenance["stage"] = {
        "payload_files_before_provenance": manifest_records,
        "payload_bytes_before_provenance": sum(item["bytes"] for item in manifest_records),
    }
    provenance["transport"] = {
        "contract": args.transport.name,
        "selected_adb": "/usr/bin/adb",
        "phone_access_during_preparation": False,
    }
    (output / "stage-provenance.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n"
    )
    # The final manifest includes the finalized provenance and every other stage file.
    manifest_lines = []
    for path in sorted(
        item
        for item in output.rglob("*")
        if item.is_file() and item.name != "stage-manifest.sha256"
    ):
        manifest_lines.append(f"{sha(path)}  {path.relative_to(output).as_posix()}")
    manifest.write_text("\n".join(manifest_lines) + "\n")
    print(json.dumps({
        **provenance["stage"],
        "final_manifest_sha256": sha(manifest),
        "final_manifest_entries": len(manifest_lines),
    }, indent=2, sort_keys=True))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runner", type=Path, required=True)
    parser.add_argument("--runner-source", type=Path, required=True)
    parser.add_argument("--ort", type=Path, required=True)
    parser.add_argument("--libcxx", type=Path, required=True)
    parser.add_argument("--qairt", type=Path, required=True)
    parser.add_argument("--graphs", type=Path, required=True)
    parser.add_argument("--contexts", type=Path, required=True)
    parser.add_argument("--functional", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--transcript", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--transport", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
