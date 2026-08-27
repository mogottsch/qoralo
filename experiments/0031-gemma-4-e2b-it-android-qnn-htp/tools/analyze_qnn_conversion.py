#!/usr/bin/env python3
"""Validate and summarize the positive host QNN-conversion gate."""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
RUN = EXP / ".local/qairt-2.49.40-convert-run"
OUT = EXP / "results/qairt-2.49.40-qnn-conversion/result.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as src:
        for chunk in iter(lambda: src.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_events() -> list[dict[str, object]]:
    events = []
    for line in (RUN / "stdout.log").read_text(errors="replace").splitlines():
        if line.startswith("{"):
            events.append(json.loads(line))
    return events


def parse_dlc_info(path: Path) -> dict[str, object]:
    text = path.read_text(errors="replace")
    dlc_match = re.search(r"^DLC info of: (.+)$", text, re.MULTILINE)
    param_match = re.search(r"^Total parameters: (\d+)", text, re.MULTILINE)
    mac_match = re.search(r"^Total MACs per inference: (\S+)", text, re.MULTILINE)
    memory_match = re.search(r"^Est\. Steady-State Memory Needed to Run: ([0-9.]+) MiB", text, re.MULTILINE)
    ops_match = re.search(r"^Ops used by Graph: (.+)$", text, re.MULTILINE)
    if not all((dlc_match, param_match, mac_match, memory_match, ops_match)):
        raise RuntimeError(f"incomplete DLC info report: {path}")
    dlc_path = Path(dlc_match.group(1))
    ar_match = re.search(r"ar(1|128)_cl4096", dlc_path.name)
    if not ar_match:
        raise RuntimeError(f"cannot infer AR from {dlc_path}")

    output_section = text.split("Output Name", 1)[1].split("Total parameters:", 1)[0]
    outputs = []
    for line in output_section.splitlines():
        if not line.startswith("|"):
            continue
        fields = [field.strip() for field in line.strip("|").split("|")]
        if len(fields) >= 3 and fields[0] not in ("", "Output Name"):
            outputs.append({"name": fields[0], "dimensions": fields[1], "type": fields[2]})
    output_types = Counter(item["type"] for item in outputs)
    return {
        "ar": int(ar_match.group(1)),
        "dlc_path": str(dlc_path.resolve().relative_to(EXP.resolve())),
        "report_path": str(path.resolve().relative_to(EXP.resolve())),
        "report_bytes": path.stat().st_size,
        "report_sha256": sha256(path),
        "parameters": int(param_match.group(1)),
        "macs_reported": mac_match.group(1),
        "estimated_steady_state_memory_mib": float(memory_match.group(1)),
        "ops": [item.strip() for item in ops_match.group(1).split(",")],
        "output_count": len(outputs),
        "output_type_counts": dict(sorted(output_types.items())),
        "float16_outputs": [item["name"] for item in outputs if item["type"] == "Float_16"],
    }


def main() -> None:
    events = parse_events()
    if [event.get("event") for event in events] != ["qnn_conversion_start", "qnn_conversion_complete"]:
        raise RuntimeError(f"unexpected events: {[event.get('event') for event in events]}")
    start, complete = events
    models = complete["converted_models"]
    if len(models) != 2 or sorted(model["ar"] for model in models) != [1, 128]:
        raise RuntimeError("expected converted AR1 and AR128 models")
    converted = []
    for model in models:
        dlc_path = Path(model["dlc_path"])
        actual = sha256(dlc_path)
        if actual != model["dlc_sha256"] or dlc_path.stat().st_size != model["dlc_bytes"]:
            raise RuntimeError(f"DLC identity mismatch: {dlc_path}")
        converted.append(
            {
                "ar": model["ar"],
                "name": model["model_name"],
                "path": str(dlc_path.resolve().relative_to(EXP.resolve())),
                "bytes": model["dlc_bytes"],
                "sha256": model["dlc_sha256"],
            }
        )

    reports = sorted(
        (parse_dlc_info(path) for path in RUN.glob("dlc-*.stdout.log")), key=lambda item: item["ar"]
    )
    if [report["ar"] for report in reports] != [1, 128]:
        raise RuntimeError("expected one DLC info report per AR variant")
    main_stdout = (RUN / "stdout.log").read_text(errors="replace")
    fallback_groups = re.findall(r"Following OPs fallback to float:\n([^\n]+)", main_stdout)
    float_fallback_ops = [[name.strip() for name in group.split(",") if name.strip()] for group in fallback_groups]
    if len(float_fallback_ops) != 2 or any(len(group) != 15 for group in float_fallback_ops):
        raise RuntimeError("unexpected float fallback warning shape")

    result = {
        "schema_version": 1,
        "experiment": "0031-gemma-4-e2b-it-android-qnn-htp",
        "classification": "positive_host_qnn_conversion_result",
        "claim_boundary": (
            "Both bound static Gemma4 variants converted to QAIRT DLC with backend=HTP and quantization "
            "overrides. This proves host QNN conversion only; no HTP compilation, serialized context, "
            "partition acceptance, Android execution, or inference is claimed."
        ),
        "qairt_version": complete["qairt_version"],
        "target_configuration": complete["target_configuration"],
        "host_memory_coordination": "Conversion ran alone after checking actual host memory pressure; heavy-ram.lock is retired.",
        "converted_models": sorted(converted, key=lambda item: item["ar"]),
        "dlc_info": reports,
        "quantization": {
            "overrides_supplied": True,
            "weights_published_precision": "w4",
            "activations_published_precision": "a16",
            "converter_float_fallback_warning_groups": len(float_fallback_ops),
            "converter_float_fallback_ops_per_variant": [len(group) for group in float_fallback_ops],
            "converter_float_fallback_op_kind": "RmsNorm",
            "ar1_float16_outputs": next(report["float16_outputs"] for report in reports if report["ar"] == 1),
            "ar128_float16_outputs": next(report["float16_outputs"] for report in reports if report["ar"] == 128),
            "boundary": (
                "The converter reports 15 RmsNorm float fallbacks per variant. AR1 exposes its 15 value-cache "
                "outputs as Float_16 while AR128 exposes all outputs as uFxp_16. These facts are retained for "
                "compile/runtime validation and are not silently relabeled as uniform integer execution."
            ),
        },
        "raw_logs": {
            name: {"bytes": (RUN / name).stat().st_size, "sha256": sha256(RUN / name)}
            for name in ("stdout.log", "stderr.log")
        },
        "requested": {
            "qnn_conversion": True,
            "htp_compilation": False,
            "phone_access": False,
            "inference": False,
            "paid_workbench_job": False,
        },
        "next_gate": (
            "Compile the two DLCs together in weight-sharing mode for chipset:SM8550/HTP v73, then inspect "
            "the serialized context and graph/provider metadata before phone staging."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(OUT)


if __name__ == "__main__":
    main()
