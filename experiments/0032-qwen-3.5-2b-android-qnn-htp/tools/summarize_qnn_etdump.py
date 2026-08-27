#!/usr/bin/env python3
"""Summarize high-level QNN delegate profile records from an ExecuTorch ETDump."""
from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path


EVENTS = (
    "Number of HVX threads used (count)",
    "RPC (execute) time (us)",
    "QNN accelerator (execute) time (us)",
    "Accelerator (execute) time (cycles)",
    "Time for initial VTCM acquire (us)",
    "Time for HVX + HMX power on and acquire (us)",
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--etdump", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prompt-tokens", type=int, required=True)
    parser.add_argument("--qnn-graphs", type=int, required=True)
    args = parser.parse_args()

    from executorch.devtools import Inspector

    # QNN's delegate event names state their native units. Preserve the numeric
    # payload rather than applying Inspector's generic nanosecond conversion.
    inspector = Inspector(
        etdump_path=str(args.etdump),
        delegate_time_scale_converter=lambda _name, value: value,
    )
    blocks = [block for block in inspector.event_blocks if block.name == "Execute"]
    if len(blocks) != 1:
        raise RuntimeError(f"expected one Execute block, found {len(blocks)}")
    block = blocks[0]
    summaries = {}
    expected_observations = args.prompt_tokens * args.qnn_graphs
    for name in EVENTS:
        matched = [event for event in block.events if event.name == name]
        values = [value for event in matched for value in event.perf_data.raw]
        if len(values) != expected_observations:
            raise RuntimeError(
                f"{name}: expected {expected_observations} observations, got {len(values)}"
            )
        summaries[name] = {
            "event_series": len(matched),
            "observations": len(values),
            "sum": sum(values),
            "mean": statistics.fmean(values),
            "min": min(values),
            "max": max(values),
        }

    accelerator_us = summaries["QNN accelerator (execute) time (us)"]["sum"]
    rpc_us = summaries["RPC (execute) time (us)"]["sum"]
    result = {
        "schema_version": 1,
        "source": "ExecuTorch Inspector over physical-attempt ETDump",
        "delegate_unit_handling": "identity conversion; units are taken from each QNN event name",
        "prompt_tokens": args.prompt_tokens,
        "qnn_graphs_per_token": args.qnn_graphs,
        "expected_graph_executions": expected_observations,
        "events": summaries,
        "derived_viability_observations": {
            "qnn_accelerator_seconds_total": accelerator_us / 1_000_000,
            "qnn_accelerator_seconds_per_prompt_token": accelerator_us
            / 1_000_000
            / args.prompt_tokens,
            "rpc_execute_seconds_total": rpc_us / 1_000_000,
            "rpc_execute_seconds_per_prompt_token": rpc_us
            / 1_000_000
            / args.prompt_tokens,
        },
        "claim_limits": [
            "Single-request max_new_tokens=1 viability profile only.",
            "These observations are not a loaded-route campaign distribution or registry benchmark.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(args.output)


if __name__ == "__main__":
    main()
