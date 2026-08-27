#!/usr/bin/env python3
"""Validate the SM8550/v73 weight-shared Gemma context and metadata."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
RUN = EXP / ".local/qairt-2.49.40-compile-run"
OUT = EXP / "results/qairt-2.49.40-sm8550-context/result.json"
HTP_HEADER = Path("/home/moritz/opt/qairt/2.49.40.260810/include/QNN/HTP/QnnHtpCommon.h")
EXPECTED_CONTEXT_SHA256 = "b8c169cedf9a00dde67e2e555805b1a773cb6fd128f5c3912a684c371f4af95a"
EXPECTED_DLCS = {
    1: "02a790601b561a9ebb122c3101b916dfe8e3496435eee08a514237112a57ff68",
    128: "5f17ece8a99cd649abdadb61e2e104e5cd569a1d1735e9e6ecb5c297286156ee",
}


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


def contains_markers(path: Path, markers: list[bytes]) -> dict[str, bool]:
    found = {marker.decode(): False for marker in markers}
    overlap = max(map(len, markers)) - 1
    tail = b""
    with path.open("rb") as src:
        for chunk in iter(lambda: src.read(8 * 1024 * 1024), b""):
            data = tail + chunk
            for marker in markers:
                if marker in data:
                    found[marker.decode()] = True
            tail = data[-overlap:] if overlap else b""
    return found


def tensor_summary(tensors: list[dict[str, object]]) -> dict[str, object]:
    infos = [tensor["info"] for tensor in tensors]
    return {
        "count": len(infos),
        "names": [info["name"] for info in infos],
        "datatype_counts": dict(sorted(Counter(info["dataType"] for info in infos).items())),
        "memtype_counts": dict(sorted(Counter(info["memType"] for info in infos).items())),
    }


def main() -> None:
    events = parse_events()
    if [event.get("event") for event in events] != ["htp_compile_start", "htp_compile_complete"]:
        raise RuntimeError(f"unexpected compile events: {[event.get('event') for event in events]}")
    start, complete = events
    if start["mode"] != "weight_sharing" or start["target"] != "chipset:SM8550":
        raise RuntimeError("compile did not request weight-shared SM8550")
    if {item["ar"]: item["dlc_sha256"] for item in start["models"]} != EXPECTED_DLCS:
        raise RuntimeError("compile input DLC identity mismatch")

    context_path = Path(complete["context"]["path"])
    context_hash = sha256(context_path)
    if context_hash != EXPECTED_CONTEXT_SHA256:
        raise RuntimeError(f"context identity mismatch: {context_hash}")
    metadata_path = RUN / "context-info.json"
    metadata = json.loads(metadata_path.read_text())
    info = metadata["info"]
    header_text = HTP_HEADER.read_text(errors="replace")
    if "#define QNN_BACKEND_ID_HTP 6" not in header_text or info["backendId"] != 6:
        raise RuntimeError("context backend ID is not bound to QNN HTP")
    if info["numGraphs"] != 2:
        raise RuntimeError("expected two graphs in weight-shared context")

    graphs = []
    for graph in info["graphs"]:
        graph_info = graph["info"]
        graphs.append(
            {
                "name": graph_info["graphName"],
                "inputs": tensor_summary(graph_info["graphInputs"]),
                "outputs": tensor_summary(graph_info["graphOutputs"]),
            }
        )
    graphs.sort(key=lambda graph: graph["name"])
    if [graph["name"] for graph in graphs] != ["ar128_cl4096_1_of_1", "ar1_cl4096_1_of_1"]:
        raise RuntimeError("unexpected graph names")
    if any(graph["inputs"]["count"] != 38 or graph["outputs"]["count"] != 31 for graph in graphs):
        raise RuntimeError("unexpected graph IO counts")
    if any(graph["inputs"]["memtype_counts"] != {"QNN_TENSORMEMTYPE_MEMHANDLE": 38} for graph in graphs):
        raise RuntimeError("context inputs are not all memhandle tensors")
    if any(graph["outputs"]["memtype_counts"] != {"QNN_TENSORMEMTYPE_MEMHANDLE": 31} for graph in graphs):
        raise RuntimeError("context outputs are not all memhandle tensors")

    markers = contains_markers(
        context_path,
        [
            b"soc_type=SM8550",
            b"arch=73",
            b"native_hmx_a16w4=true",
            b"ar1_cl4096_1_of_1",
            b"ar128_cl4096_1_of_1",
        ],
    )
    if not all(markers.values()):
        raise RuntimeError(f"missing context markers: {markers}")

    result = {
        "schema_version": 1,
        "experiment": "0031-gemma-4-e2b-it-android-qnn-htp",
        "classification": "positive_host_sm8550_htp_context_compile_and_inspection",
        "claim_boundary": (
            "The two bound QNN DLCs compiled into one weight-sharing context whose official metadata "
            "identifies QNN HTP backend ID 6 and two AR graphs, and whose embedded compiler markers bind "
            "SM8550/architecture 73. This is host AOT evidence only, not physical Android loading, HTP "
            "execution, no-fallback proof, generated text, or performance evidence."
        ),
        "qairt_version": complete["qairt_version"],
        "compile": {
            "mode": complete["mode"],
            "target": complete["target"],
            "soc_model": complete["soc_model"],
            "dsp_arch": complete["dsp_arch"],
            "pd_session": start["pd_session"],
            "input_dlcs": sorted(start["models"], key=lambda item: item["ar"]),
            "context_path": str(context_path.resolve().relative_to(EXP.resolve())),
            "context_bytes": context_path.stat().st_size,
            "context_sha256": context_hash,
        },
        "inspection": {
            "utility": "qnn-context-binary-utility",
            "metadata_path": str(metadata_path.resolve().relative_to(EXP.resolve())),
            "metadata_bytes": metadata_path.stat().st_size,
            "metadata_sha256": sha256(metadata_path),
            "artifact_type": metadata["header"]["artifact_type"],
            "metadata_version": metadata["version"],
            "backend_id": info["backendId"],
            "backend_id_source": "QAIRT 2.49.40 include/QNN/HTP/QnnHtpCommon.h: QNN_BACKEND_ID_HTP 6",
            "backend_id_source_sha256": sha256(HTP_HEADER),
            "build_id": info["buildId"],
            "core_api_version": info["coreApiVersion"],
            "backend_api_version": info["backendApiVersion"],
            "context_blob_version": info["contextBlobVersion"],
            "context_blob_bytes": info["contextBlobSize"],
            "num_graphs": info["numGraphs"],
            "graphs": graphs,
            "embedded_markers": markers,
        },
        "mixed_precision_boundary": {
            "ar1_output_datatypes": next(
                graph["outputs"]["datatype_counts"] for graph in graphs if graph["name"].startswith("ar1_")
            ),
            "ar128_output_datatypes": next(
                graph["outputs"]["datatype_counts"] for graph in graphs if graph["name"].startswith("ar128_")
            ),
            "not_uniform_integer_execution_claim": True,
        },
        "raw_logs": {
            name: {"bytes": (RUN / name).stat().st_size, "sha256": sha256(RUN / name)}
            for name in ("stdout.log", "stderr.log", "context-info.stdout.log", "context-info.stderr.log")
        },
        "requested": {
            "htp_compilation": True,
            "phone_access": False,
            "physical_htp_execution": False,
            "inference": False,
            "paid_workbench_job": False,
        },
        "next_gate": (
            "Generate and bind matching token + per-layer embedding LUTs and a Genie QnnHtp config, then wait "
            "for explicit phone priority and acquire phone.lock before a bounded physical context-load/inference probe."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(OUT)


if __name__ == "__main__":
    main()
