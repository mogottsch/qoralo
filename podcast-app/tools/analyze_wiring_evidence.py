#!/usr/bin/env python3
"""Classify retained wiring artifacts without inventing throughput or provider proof."""
from __future__ import annotations
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import tarfile
from prepare_wiring_gate import CONTRACT_SHA


def profile_observations(ort_events, qnn_rows):
    providers = sorted({e.get("args", {}).get("provider") for e in ort_events if e.get("args", {}).get("provider")})
    positive = set()
    for row in qnn_rows:
        try:
            if float(row.get("Time", "0")) > 0:
                positive.add(row.get("Event Identifier", ""))
        except ValueError:
            pass
    return {"ortProviders": providers, "rpcExecuteObserved": "RPC (execute) time" in positive,
            "acceleratorCyclesObserved": "Accelerator (execute) time (cycles)" in positive,
            "htpProofEstablished": providers == ["QNNExecutionProvider"] and "RPC (execute) time" in positive and "Accelerator (execute) time (cycles)" in positive}


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
