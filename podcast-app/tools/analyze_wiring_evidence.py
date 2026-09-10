#!/usr/bin/env python3
"""Classify retained wiring artifacts without inventing throughput or provider proof."""
from __future__ import annotations
import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import tarfile
from prepare_wiring_gate import CONTRACT_SHA


def positive_finite(value):
    try:
        return math.isfinite(float(value)) and float(value) > 0
    except (ValueError, TypeError):
        return False


def profile_observations(ort_events, qnn_rows):
    # Session metadata, provider declarations and Node fence events are not executed kernels.
    nodes = [e for e in ort_events if e.get("cat") == "Node" and e.get("ph") == "X"
             and str(e.get("name", "")).endswith("_kernel_time") and positive_finite(e.get("dur"))]
    providers = sorted({e.get("args", {}).get("provider") for e in nodes if e.get("args", {}).get("provider")})
    all_nodes_qnn = bool(nodes) and all(e.get("args", {}).get("provider") == "QNNExecutionProvider" for e in nodes)
    def has_backend_event(identifier, unit):
        return any(row.get("Event Identifier") == identifier and row.get("Unit of Measurement") == unit
                   and row.get("Timing Source") == "BACKEND" and row.get("Event Level") == "ROOT"
                   and positive_finite(row.get("Time")) for row in qnn_rows)
    rpc = has_backend_event("RPC (execute) time", "US")
    cycles = has_backend_event("Accelerator (execute) time (cycles)", "CYCLES")
    return {"ortProviders": providers, "ortExecutionNodeCount": len(nodes), "rpcExecuteObserved": rpc,
            "acceleratorCyclesObserved": cycles, "htpProofEstablished": all_nodes_qnn and rpc and cycles,
            "scope": "per-component recorded Node/RPC/cycle evidence predicate; not blanket route or product acceptance"}


def analyze(archive_path: Path, candidate: dict, run_id: str):
    prefix = f"files/wiring/{run_id}/"
    with tarfile.open(archive_path) as archive:
        members = {m.name.removeprefix(prefix): m for m in archive if m.isfile() and m.name.startswith(prefix)}
        def raw(name):
            member = members[name]
            if member.size > 268435456:
                raise ValueError("unbounded evidence member")
            return archive.extractfile(member).read()
        def document(name):
            return json.loads(raw(name))
        identity = document("driver-identity.json")
        if identity["appApkSha256"] != candidate["app"]["sha256"] or identity["testApkSha256"] != candidate["test"]["sha256"] or identity["contractSha256"] != CONTRACT_SHA:
            raise ValueError("driver identity not bound to this candidate")
        for name, expected in candidate["contract"]["inputs"].items():
            payload = raw(name)
            if len(payload) != expected["bytes"] or hashlib.sha256(payload).hexdigest() != expected["sha256"]:
                raise ValueError(f"input changed: {name}")
        profiles = {}
        for component in ("duration", "text", "vector", "vocoder"):
            ort_events = []
            for name in members:
                if name.startswith(f"qnn-profiles/{component}") and name.endswith(".json"):
                    ort_events += document(name)
            csv_name = f"qnn-profiles/{component}.qnn.csv"
            rows = list(csv.DictReader(io.StringIO(raw(csv_name).decode()))) if csv_name in members else []
            profiles[component] = profile_observations(ort_events, rows)
        maps = raw("gemma-after-generation-proc-maps.txt").decode(errors="replace") if "gemma-after-generation-proc-maps.txt" in members else ""
        fds = raw("gemma-after-generation-fds.txt").decode(errors="replace") if "gemma-after-generation-fds.txt" in members else ""
        return {"claim": "bounded wiring only; not product E2E", "driver": document("driver-result.json"),
                "service": document("service-result.json"), "qnn": profiles,
                "gpuObservations": {"litertJniMapped": "liblitertlm_jni.so" in maps,
                                    "openClDriverMapped": "libOpenCL.so" in maps,
                                    "kgslDescriptorObserved": "/dev/kgsl" in fds,
                                    "proofStatus": "manual provider review required; maps alone do not prove delegation"},
                "capacity": document("capacity-observation.json") if "capacity-observation.json" in members else None,
                "inventory": {name: {"bytes": member.size, "sha256": hashlib.sha256(raw(name)).hexdigest()} for name, member in members.items()},
                "listeningVerdict": "not_reviewed"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = analyze(args.archive, json.loads(args.candidate.read_text()), args.run_id)
    except Exception as error:
        result = {"status": "incomplete_or_invalid_evidence", "error": repr(error), "rawArchivePreserved": str(args.archive)}
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"report": str(args.output), "physicalApproval": False}))


if __name__ == "__main__":
    main()
