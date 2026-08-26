#!/usr/bin/env python3
"""Inventory the authorized public Gemma 4 E2B QNN/HTP route without downloading it."""
from __future__ import annotations

import hashlib
import json
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QAIRT = Path("/home/moritz/opt/qairt/2.49.0.260730")
ASSET_URL = (
    "https://qaihub-public-assets.s3.us-west-2.amazonaws.com/"
    "qai-hub-models/models/gemma_4_e2b_it/v1/gemma_4_e2b_it_w4a16.zip"
)
FILES = {
    "sdk_manifest": QAIRT / "sdk.yaml",
    "release_notes": QAIRT / "QAIRT_ReleaseNotes.txt",
    "gemma4_htp_config": QAIRT / "examples/Genie/configs/gemma4/gemma4-e2b-htp.json",
    "gguf_htp_builder": QAIRT / "lib/python/qairt/gen_ai_api/builders/gguf_builder_htp.py",
    "gguf_support_table": QAIRT / "lib/python/qti/aisw/converters/gguf_builder/utils.py",
    "android_genie_t2t_run": QAIRT / "bin/aarch64-android/genie-t2t-run",
    "android_lib_genie": QAIRT / "lib/aarch64-android/libGenie.so",
    "android_lib_qnn_htp": QAIRT / "lib/aarch64-android/libQnnHtp.so",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as src:
        for chunk in iter(lambda: src.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    req = urllib.request.Request(ASSET_URL, method="HEAD")
    with urllib.request.urlopen(req, timeout=60) as response:
        public_asset = {
            "url": ASSET_URL,
            "http_status": response.status,
            "content_length_bytes": int(response.headers["Content-Length"]),
            "content_type": response.headers.get("Content-Type"),
            "last_modified": response.headers.get("Last-Modified"),
            "etag": response.headers.get("ETag"),
            "authentication_used": False,
            "downloaded": False,
            "sha256": None,
            "sha256_null_reason": "HEAD-only inventory; hash is recorded only after a heavy-ram.lock-protected download.",
        }

    release_notes = FILES["release_notes"].read_text(errors="replace")
    config = json.loads(FILES["gemma4_htp_config"].read_text())
    support_text = FILES["gguf_support_table"].read_text()
    model_types_match = re.search(r"MODEL_TYPE_TO_ARCH\s*=\s*\{(.*?)\}\n\n", support_text, re.S)
    model_types = sorted(set(re.findall(r'"([a-zA-Z0-9_]+)"\s*:', model_types_match.group(1)))) if model_types_match else []
    result = {
        "schema_version": 1,
        "experiment": "0031-gemma-4-e2b-it-android-qnn-htp",
        "assessment": "phone_independent_support_and_public_artifact_inventory",
        "sdk": {
            "root": str(QAIRT),
            "version": "2.49.0.260730",
            "already_installed": True,
            "license_acceptance_or_sdk_download_performed": False,
            "files": {
                name: {"path": str(path), "bytes": path.stat().st_size, "sha256": sha256(path)}
                for name, path in FILES.items()
            },
        },
        "support": {
            "release_notes_explicit_gemma4": "Added support for the Gemma 4 model family." in release_notes,
            "example_backend_type": config["dialog"]["engine"]["backend"]["type"],
            "example_context_size": config["dialog"]["context"]["size"],
            "example_context_binaries": config["dialog"]["engine"]["model"]["binary"]["ctx-bins"],
            "example_embedding_type": config["dialog"]["embedding"]["type"],
            "example_per_layer_embedding_type": config["dialog"]["perlayer-embedding"]["type"],
            "sm8550_compile_target_supported_by_installed_api": True,
            "sm8550_compile_target_source": "qairt/api/compiler/config.py documents CompileConfig(backend='HTP', soc_details='chipset:SM8550').",
        },
        "public_w4a16_checkpoint": public_asset,
        "direct_gguf_path": {
            "google_public_gguf_architecture": "gemma4",
            "installed_gguf_builder_supported_model_types": model_types,
            "gemma4_supported": "gemma4" in model_types,
            "decision": "rejected" if "gemma4" not in model_types else "candidate",
            "reason": "The installed direct GGUF-to-HTP builder has no gemma4 architecture entry; it cannot credibly consume the public Gemma 4 GGUF.",
        },
        "selected_candidate": {
            "input": "public Qualcomm AI Hub Models v1 w4a16 calibrated checkpoint archive",
            "conversion": "local installed QAIRT 2.49 HTP compilation targeting SM8550",
            "runtime": "Genie QnnHtp with serialized context binary",
            "status": "awaiting heavy-ram.lock-protected download and archive inspection",
        },
    }
    output = ROOT / "results/support-assessment/result.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(output)


if __name__ == "__main__":
    main()
