#!/usr/bin/env python3
"""Record non-secret provenance for an authorized QAIRT update kept outside Git."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
OLD = Path("/home/moritz/opt/qairt/2.49.0.260730")
NEW = Path("/home/moritz/opt/qairt/2.49.40.260810")
QIK = Path(
    "/home/moritz/.local/share/vibevoice-android-spike/qualcomm-packages/"
    "Qualcomm_AI_Runtime_SDK.2.49.40.260810.Linux-AnyCPU.qik"
)
OUT = EXP / "results/qairt-2.49.40-capability/result.json"

SELECTED = [
    "sdk.yaml",
    "QAIRT_ReleaseNotes.txt",
    "lib/python/qairt/gen_ai_api/gen_ai_builder_factory.py",
    "lib/python/qairt/optimizer/onnx/utils/utils.py",
    "lib/python/qairt/optimizer/onnx/passes/shape_infer/shape_infer.py",
    "examples/Genie/configs/gemma4/gemma4-e2b-htp.json",
    "bin/aarch64-android/genie-app",
    "bin/aarch64-android/genie-t2t-run",
    "lib/aarch64-android/libGenie.so",
    "lib/aarch64-android/libQnnHtp.so",
    "lib/aarch64-android/libQnnHtpV73Stub.so",
    "lib/hexagon-v73/unsigned/libQnnHtpV73Skel.so",
    "lib/hexagon-v73/unsigned/libQnnSystem.so",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as src:
        for chunk in iter(lambda: src.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def manifest_fields(path: Path) -> dict[str, str]:
    text = path.read_text(errors="replace")
    keys = ("product", "version", "build_id", "qnn_backend_api_version", "sdk_flavor")
    fields: dict[str, str] = {}
    for key in keys:
        match = re.search(rf"^{re.escape(key)}:\s*(.+)$", text, re.MULTILINE)
        if not match:
            raise ValueError(f"missing {key} in {path}")
        fields[key] = match.group(1).strip()
    return fields


def entry(root: Path, relative: str) -> dict[str, object]:
    path = root / relative
    return {
        "relative_path": relative,
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def main() -> None:
    old_files = {rel: entry(OLD, rel) for rel in SELECTED}
    new_files = {rel: entry(NEW, rel) for rel in SELECTED}
    comparison = []
    for rel in SELECTED:
        old = old_files[rel]
        new = new_files[rel]
        comparison.append(
            {
                "relative_path": rel,
                "old_bytes": old["bytes"],
                "old_sha256": old["sha256"],
                "new_bytes": new["bytes"],
                "new_sha256": new["sha256"],
                "byte_identical": old["sha256"] == new["sha256"],
            }
        )

    converter_paths = {
        "lib/python/qairt/gen_ai_api/gen_ai_builder_factory.py",
        "lib/python/qairt/optimizer/onnx/utils/utils.py",
        "lib/python/qairt/optimizer/onnx/passes/shape_infer/shape_infer.py",
    }
    converter_identical = all(
        item["byte_identical"] for item in comparison if item["relative_path"] in converter_paths
    )

    result = {
        "schema_version": 1,
        "experiment": "0031-gemma-4-e2b-it-android-qnn-htp",
        "classification": "authorized_toolchain_acquisition_and_host_capability_comparison",
        "claim_boundary": (
            "Package provenance and selected host/runtime capability comparison only. "
            "No Gemma transform, QNN conversion, HTP compilation, Android execution, or paid Workbench job is claimed."
        ),
        "authorization": {
            "product": "Qualcomm_AI_Runtime_SDK",
            "license_status": "ACTIVE",
            "license_end_date": "2030-08-22",
            "identifiers_recorded": False,
            "account_identity_recorded": False,
            "secret_material_recorded": False,
        },
        "package": {
            "source": "https://qpm.qualcomm.com/#/main/tools/details/Qualcomm_AI_Runtime_SDK",
            "qpm_product": "Qualcomm_AI_Runtime_SDK",
            "qpm_version": "2.49.40.260810",
            "qik_filename": QIK.name,
            "bytes": QIK.stat().st_size,
            "sha256": sha256(QIK),
            "stored_outside_git": True,
        },
        "sdk": {
            "old": manifest_fields(OLD / "sdk.yaml"),
            "new": manifest_fields(NEW / "sdk.yaml"),
            "new_root": str(NEW),
            "new_root_outside_git": True,
            "selected_file_comparison": comparison,
        },
        "assessment": {
            "selected_converter_sources_byte_identical": converter_identical,
            "gemma4_factory_dispatch_added": False,
            "old_constant_attribute_bug_fixed": False,
            "android_runtime_binaries_changed": any(
                not item["byte_identical"]
                for item in comparison
                if item["relative_path"].startswith(("bin/aarch64-android/", "lib/aarch64-android/", "lib/hexagon-v73/"))
            ),
            "gemma4_qnn_htp_example_present": (NEW / "examples/Genie/configs/gemma4/gemma4-e2b-htp.json").is_file(),
            "sm8550_v73_runtime_present": all(
                (NEW / rel).is_file()
                for rel in (
                    "lib/aarch64-android/libQnnHtp.so",
                    "lib/aarch64-android/libQnnHtpV73Stub.so",
                    "lib/hexagon-v73/unsigned/libQnnHtpV73Skel.so",
                )
            ),
            "transform_probe_ran": False,
            "decision": (
                "Do not expect the previously observed transform defect to disappear in 2.49.40: "
                "the factory and implicated optimizer sources are byte-identical to 2.49.0. "
                "Retain 2.49.40 as the runtime candidate and test an isolated, schema-faithful converter compatibility fix."
            ),
        },
        "security": {
            "restricted_package_or_sdk_committed": False,
            "credential_contents_inspected": False,
            "qpm_private_state_directories_mode": "0700",
            "qpm_private_state_files_mode": "0600",
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(OUT)


if __name__ == "__main__":
    main()
