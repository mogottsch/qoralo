#!/usr/bin/env python3
"""Assemble the private Gemma4 Genie/QnnHtp phone bundle and manifest."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
SDK = Path("/home/moritz/opt/qairt/2.49.40.260810")
BUNDLE = EXP / ".local/runtime-bundle"
CONTEXT_SHA256 = "7739ce5278dbe77117c879602f15e1e62460c88a9adf2dbcf10abb47dd61d394"
EXPECTED_LUTS = {
    "embedding": ("embedding_int8_lut.bin", 402653184),
    "perlayer_embedding": ("embed_tokens_per_layer_int8_lut.bin", 2348810240),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as src:
        for chunk in iter(lambda: src.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def link_or_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.unlink(missing_ok=True)
    try:
        os.link(source, destination)
    except OSError:
        shutil.copy2(source, destination)


def main() -> None:
    provenance_path = BUNDLE / "lut-provenance.json"
    provenance = json.loads(provenance_path.read_text())
    luts = {item["name"]: item for item in provenance["luts"]}
    for name, (filename, size) in EXPECTED_LUTS.items():
        item = luts[name]
        path = BUNDLE / filename
        if item["filename"] != filename or item["bytes"] != size:
            raise RuntimeError(f"unexpected {name} metadata")
        if path.stat().st_size != size or sha256(path) != item["sha256"]:
            raise RuntimeError(f"unexpected {name} artifact")

    context_matches = list((EXP / ".local/qairt-2.49.40-context-cache-aligned-v6").rglob("ar1_cl4096_1_of_1.bin"))
    if len(context_matches) != 1 or sha256(context_matches[0]) != CONTEXT_SHA256:
        raise RuntimeError("compiled context identity mismatch")
    context_out = BUNDLE / "models/weight_sharing_model_ar128_ar1_cl4096_scl512_1_of_1.serialized.bin"
    link_or_copy(context_matches[0], context_out)

    tokenizer_source = EXP / ".local/checkpoint/extracted/gemma_4_e2b_it_w4a16/tokenizer.json"
    link_or_copy(tokenizer_source, BUNDLE / "tokenizer.json")
    link_or_copy(
        SDK / "examples/Genie/configs/htp_backend_ext_config.json",
        BUNDLE / "htp_backend_ext_config.json",
    )

    runtime_sources = {
        "genie-app": SDK / "bin/aarch64-android/genie-app",
        "libGenie.so": SDK / "lib/aarch64-android/libGenie.so",
        "libQnnHtp.so": SDK / "lib/aarch64-android/libQnnHtp.so",
        "libQnnSystem.so": SDK / "lib/aarch64-android/libQnnSystem.so",
        "libQnnHtpV73Stub.so": SDK / "lib/aarch64-android/libQnnHtpV73Stub.so",
        "libQnnHtpNetRunExtensions.so": SDK / "lib/aarch64-android/libQnnHtpNetRunExtensions.so",
        "libQnnHtpV73Skel.so": SDK / "lib/hexagon-v73/unsigned/libQnnHtpV73Skel.so",
    }
    for name, source in runtime_sources.items():
        destination = BUNDLE / ("bin" if name == "genie-app" else "lib") / name
        link_or_copy(source, destination)
        destination.chmod(0o700 if name == "genie-app" else 0o600)

    embedding = luts["embedding"]
    perlayer = luts["perlayer_embedding"]
    config = {
        "dialog": {
            "version": 1,
            "type": "basic",
            "max-num-tokens": 2048,
            "context": {
                "version": 1,
                "size": 4096,
                "n-vocab": 262144,
                "bos-token": 2,
                "eos-token": [1, 106],
                "pad-token": 0,
            },
            "sampler": {
                "version": 1,
                "seed": 42,
                "temp": 0.0,
                "top-k": 1,
                "top-p": 1.0,
                "greedy": True,
            },
            "tokenizer": {"version": 1, "path": "./tokenizer.json"},
            "engine": {
                "version": 1,
                "n-threads": 3,
                "backend": {
                    "version": 1,
                    "type": "QnnHtp",
                    "QnnHtp": {
                        "version": 1,
                        "use-mmap": True,
                        "spill-fill-bufsize": 0,
                        "mmap-budget": 40,
                        "poll": True,
                        "cpu-mask": "0xe0",
                        "kv-dim": 256,
                        "allow-async-init": True,
                        "enable-graph-switching": True,
                    },
                    "extensions": "./htp_backend_ext_config.json",
                },
                "cache-groups": [
                    {
                        "version": 1,
                        "prefix": "past_",
                        "kv-dim": 512,
                        "attention-mask-tensor-name": "attention_mask",
                    },
                    {
                        "version": 1,
                        "prefix": "swa_",
                        "kv-dim": 256,
                        "attention-mask-tensor-name": "swa_attention_mask",
                        "longcontext": {
                            "version": 1,
                            "type": "sliding-window",
                            "sliding-window": {"version": 1, "window-size": 512},
                        },
                    },
                ],
                "model": {
                    "version": 1,
                    "type": "binary",
                    "binary": {
                        "version": 1,
                        "ctx-bins": [
                            "./models/weight_sharing_model_ar128_ar1_cl4096_scl512_1_of_1.serialized.bin"
                        ],
                    },
                    "positional-encoding": [
                        {
                            "type": "rope",
                            "rope-dim": 256,
                            "rope-theta": 1000000.0,
                            "rope-scaling": {"rope-type": "proportional", "partial-rotary-factor": 0.25},
                        },
                        {"prefix": "swa_", "type": "rope", "rope-dim": 128, "rope-theta": 10000.0},
                    ],
                },
            },
            "embedding": {
                "version": 1,
                "type": "lut",
                "lut-path": f"./{embedding['filename']}",
                "size": 1536,
                "datatype": "ufixed8",
                "quant-param": {
                    "scale": embedding["encoding"]["scale"],
                    "offset": embedding["encoding"]["offset"],
                },
            },
            "perlayer-embedding": {
                "version": 1,
                "type": "lut",
                "lut-path": f"./{perlayer['filename']}",
                "size": 8960,
                "datatype": "ufixed8",
                "quant-param": {
                    "scale": perlayer["encoding"]["scale"],
                    "offset": perlayer["encoding"]["offset"],
                },
            },
        }
    }
    config_path = BUNDLE / "gemma4-e2b-htp-cl4096-greedy.json"
    config_path.write_text(json.dumps(config, indent=2) + "\n")

    manifest_files = {}
    for path in sorted(item for item in BUNDLE.rglob("*") if item.is_file()):
        if path.name in {"runtime-manifest.json", "build.stdout.log", "build.stderr.log"}:
            continue
        manifest_files[str(path.relative_to(BUNDLE))] = {
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
    manifest = {
        "schema_version": 1,
        "route": "gemma4-e2b-it-w4a16-qairt-2.49.40-sm8550-v73",
        "bundle_root": str(BUNDLE),
        "restricted_or_large_files_stored_outside_git": True,
        "backend": "QnnHtp",
        "target": "SM8550",
        "dsp_arch": "v73",
        "context_length": 4096,
        "auto_regression_numbers": [1, 128],
        "sampling": "greedy",
        "max_new_tokens": 2048,
        "files": manifest_files,
    }
    manifest_path = BUNDLE / "runtime-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(manifest_path)


if __name__ == "__main__":
    main()
