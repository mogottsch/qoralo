#!/usr/bin/env python3
"""Inspect experiment 0032's explicit-state ExecuTorch PTE without executing it."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def tensor_record(info) -> dict:
    scalar_names = {3: "Int", 6: "Float"}
    scalar = info.dtype()
    return {
        "shape": list(info.sizes()),
        "dtype": scalar_names.get(scalar, f"ScalarType({scalar})"),
        "nbytes": info.nbytes(),
        "memory_planned": info.is_memory_planned(),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pte", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    from executorch.extension.pybindings.portable_lib import _load_for_executorch

    module = _load_for_executorch(str(args.pte))
    meta = module.method_meta("forward")
    inputs = [tensor_record(meta.input_tensor_meta(i)) for i in range(meta.num_inputs())]
    outputs = [tensor_record(meta.output_tensor_meta(i)) for i in range(meta.num_outputs())]
    if len(inputs) != 51 or len(outputs) != 49:
        raise RuntimeError(f"wrong explicit-state ABI: {len(inputs)} inputs, {len(outputs)} outputs")
    expected = {
        "token": ([1, 1], "Int"),
        "mask": ([1, 1, 1, 4096], "Float"),
        "position": ([1, 1], "Int"),
        "logits": ([1, 1, 248320], "Float"),
    }
    observed = {
        "token": (inputs[0]["shape"], inputs[0]["dtype"]),
        "mask": (inputs[1]["shape"], inputs[1]["dtype"]),
        "position": (inputs[2]["shape"], inputs[2]["dtype"]),
        "logits": (outputs[0]["shape"], outputs[0]["dtype"]),
    }
    for name, value in expected.items():
        if observed[name] != value:
            raise RuntimeError(f"wrong {name} ABI: {observed[name]} != {value}")
    digest = hashlib.sha256(args.pte.read_bytes()).hexdigest()
    result = {
        "schema_version": 1,
        "evidence_class": "exact_pte_host_abi_inspection",
        "pte": {"bytes": args.pte.stat().st_size, "sha256": digest},
        "method": "forward",
        "inputs": len(inputs),
        "outputs": len(outputs),
        "input_bytes": sum(item["nbytes"] for item in inputs),
        "output_bytes": sum(item["nbytes"] for item in outputs),
        "fixed_inputs": {name: {"shape": shape, "dtype": dtype} for name, (shape, dtype) in observed.items() if name != "logits"},
        "fixed_output_logits": {"shape": observed["logits"][0], "dtype": observed["logits"][1]},
        "state": {
            "layers": 24,
            "state_inputs": 48,
            "state_outputs": 48,
            "linear_recurrent_example": {"input": inputs[3], "output": outputs[1]},
            "full_attention_key_example": {"input": inputs[6], "output": outputs[4]},
            "linear_conv_example": {"input": inputs[27], "output": outputs[25]},
            "full_attention_value_example": {"input": inputs[30], "output": outputs[28]},
        },
        "claim_limits": [
            "PTE FlatBuffer metadata inspection only; no graph was executed.",
            "This is not Android or physical QNN/HTP evidence."
        ],
    }
    if digest != "bfdae1c3327c954566ec0d4a5a0ee8873eb145d0921bc3f9d988a6a2557be6df":
        raise RuntimeError(f"unexpected PTE hash: {digest}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(args.output)


if __name__ == "__main__":
    main()
