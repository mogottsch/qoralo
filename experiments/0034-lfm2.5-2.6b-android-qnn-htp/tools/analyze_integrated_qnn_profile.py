#!/usr/bin/env python3
"""Summarize retained integrated-runner detailed QNN profile events."""
from __future__ import annotations
import argparse, collections, json, re
from pathlib import Path

def category(identifier: str) -> str:
    if identifier.startswith("Input "): return "input_boundary"
    if identifier.startswith("Output "): return "output_boundary"
    if "/lm_head/" in identifier: return "lm_head"
    if "/mlp/" in identifier: return "mlp"
    if "/attn/" in identifier: return "attention"
    if "/conv/" in identifier: return "recurrent_conv"
    if "layernorm" in identifier.lower(): return "normalization"
    return "other"

def subcategory(identifier: str) -> str:
    if "scaled_scores" in identifier: return "attention_scaled_scores"
    if "key_tiled" in identifier or "value_tiled" in identifier: return "attention_kv_tile"
    if "/attn/" in identifier: return "attention_other"
    if ("/mlp/" in identifier and "MatMul_Q4" in identifier and
            ("/matmul0" in identifier or "/matmul1" in identifier) and
            not any(value in identifier for value in ("cast", "reshape"))):
        return "mlp_q4_matmul"
    if "/mlp/" in identifier: return "mlp_other"
    return category(identifier)

def summarize(events: list[tuple[int, str]], top_cycles: int) -> dict[str, object]:
    total = sum(value for value, _ in events)
    if total != top_cycles:
        raise ValueError(f"per-node cycle sum {total} != accelerator total {top_cycles}")
    def grouped(classifier):
        values = collections.Counter()
        for cycles, identifier in events:
            values[classifier(identifier)] += cycles
        return {
            name: {"cycles": cycles, "percent": cycles * 100.0 / total}
            for name, cycles in values.most_common()
        }
    return {
        "node_events": len(events),
        "nonzero_node_events": sum(value > 0 for value, _ in events),
        "per_node_cycle_sum": total,
        "per_node_sum_equals_accelerator_cycles": True,
        "categories": grouped(category),
        "subcategories": grouped(subcategory),
        "top_nodes": [
            {"cycles": cycles, "percent": cycles * 100.0 / total, "identifier": identifier}
            for cycles, identifier in sorted(events, reverse=True)[:30]
        ],
    }

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runner-stderr", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()
    line_pattern = re.compile(
        r"qnn_profile phase=(\S+) depth=(\d+) type=(\d+) value=(\d+) unit=(\d+) identifier=(.*)"
    )
    per_node: dict[str, list[tuple[int, str]]] = collections.defaultdict(list)
    top: dict[str, dict[str, list[int]]] = collections.defaultdict(lambda: collections.defaultdict(list))
    for line in args.runner_stderr.read_text(errors="replace").splitlines():
        match = line_pattern.fullmatch(line)
        if not match: continue
        phase, depth, event_type, value, unit, identifier = match.groups()
        depth, event_type, value, unit = int(depth), int(event_type), int(value), int(unit)
        if depth == 1 and event_type == 404 and unit == 3:
            per_node[phase].append((value, identifier))
        if depth == 0:
            top[phase][identifier].append(value)
    expected = {"prefill", "ar1_decode"}
    if set(per_node) != expected:
        raise ValueError(f"unexpected profile phases: {set(per_node)}")
    required_top = ["Accelerator (execute) time (cycles)", "Accelerator (execute) time", "QNN (execute) time", "RPC (execute) time"]
    for phase in expected:
        if any(len(top[phase].get(name, [])) != 1 for name in required_top):
            raise ValueError(f"{phase} does not contain one required top-level snapshot")
    phases = {}
    for phase in ("prefill", "ar1_decode"):
        accelerator_cycles = top[phase]["Accelerator (execute) time (cycles)"][0]
        phases[phase] = {
            "top_level": {
                "accelerator_cycles": accelerator_cycles,
                "accelerator_execute_us": top[phase]["Accelerator (execute) time"][0],
                "qnn_execute_us": top[phase]["QNN (execute) time"][0],
                "rpc_execute_us": top[phase]["RPC (execute) time"][0],
                "input_op_cycles": next(value for value, name in per_node[phase] if name.startswith("Input ")),
                "output_op_cycles": next(value for value, name in per_node[phase] if name.startswith("Output ")),
            },
            **summarize(per_node[phase], accelerator_cycles),
        }
    prefill = phases["prefill"]
    ar1 = phases["ar1_decode"]
    result = {
        "schema_version": 1,
        "classification": "offline_breakdown_of_retained_corrected_integrated_qnn_profile",
        "source": str(args.runner_stderr),
        "profile_phases": phases,
        "raw_io_context": {
            "ar171_direct_qnn_input_bytes": 133358936,
            "ar171_output_bytes": 6656000,
            "ar1_direct_qnn_input_bytes": 134750216,
            "ar1_output_bytes": 1085440,
            "interpretation": "Static raw tensor bytes copied through app/QNN buffers. QNN Input/Output node cycles are boundary-node facts, not measured host-bus byte counters."
        },
        "facts": [
            f"Prefill MLP accounts for {prefill['categories']['mlp']['percent']:.2f}% of accelerator cycles; Q4 MLP matmuls alone account for {prefill['subcategories']['mlp_q4_matmul']['percent']:.2f}%.",
            f"Prefill attention accounts for {prefill['categories']['attention']['percent']:.2f}%; the eight scaled_scores nodes alone account for {prefill['subcategories']['attention_scaled_scores']['percent']:.2f}%.",
            f"AR1 snapshot MLP accounts for {ar1['categories']['mlp']['percent']:.2f}%; input boundary and KV tiling account for {ar1['categories']['input_boundary']['percent']:.2f}% and {ar1['subcategories']['attention_kv_tile']['percent']:.2f}%.",
        ],
        "single_supported_hypothesis": {
            "proposal": "For AR171 only, multiply the much smaller query tensor by 0.125 before score MatMul and remove the post-MatMul scaled_scores multiply, preserving the algebraic scale while avoiding an elementwise pass over the [1,32,171,4096] score tensor.",
            "profile_support": {
                "scaled_scores_nodes": 8,
                "scaled_scores_cycles": prefill["subcategories"]["attention_scaled_scores"]["cycles"],
                "scaled_scores_percent": prefill["subcategories"]["attention_scaled_scores"]["percent"],
                "score_tensor_elements_per_layer": 1 * 32 * 171 * 4096,
                "query_tensor_elements_per_layer": 1 * 32 * 171 * 64,
                "element_ratio": 64,
            },
            "required_validation": "Before any new AOT, host CPU comparison must check all state/logit deltas plus finite values, FP16 underflow, and overflow after reassociation. Full fallback-disabled AOT must then precede any physical diagnostic. No speed or fidelity improvement is claimed yet.",
            "caveats": [
                "64 times fewer scaled elements is not a 64 times speedup claim.",
                "19.56 percent is the share of AR171 accelerator cycles only, not whole-request, context-load, CPU, RPC, or emitted-token latency.",
            ],
        },
        "limitations": [
            "The prefill phase has one execution and one detailed snapshot.",
            "AR1 executed 15 calls, but extraction retained one top-level/per-node event set; it is a phase snapshot (likely latest backend event), not per-call history or a distribution.",
            "QNN node cycles do not isolate host memcpy, RPC transfer bytes, DDR counters, CPU embedding, global argmax, profile dump, or context lifecycle time.",
            "This analysis performs no model load, graph execution, compilation, or phone access.",
        ],
        "claim_boundary": "Offline analysis of retained corrected-route profile events only. No new runtime, optimization result, statistical performance, campaign, or registry evidence.",
    }
    args.result.parent.mkdir(parents=True, exist_ok=True)
    args.result.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "prefill_cycles": prefill["per_node_cycle_sum"],
        "prefill_mlp_percent": prefill["categories"]["mlp"]["percent"],
        "prefill_scaled_scores_percent": prefill["subcategories"]["attention_scaled_scores"]["percent"],
        "ar1_cycles": ar1["per_node_cycle_sum"],
        "ar1_snapshot_mlp_percent": ar1["categories"]["mlp"]["percent"],
    }, indent=2))

if __name__ == "__main__":
    main()
