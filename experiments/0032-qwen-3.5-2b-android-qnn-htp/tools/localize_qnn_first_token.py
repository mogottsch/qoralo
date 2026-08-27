#!/usr/bin/env python3
"""Compare first-token host QDQ outputs with the exact PTE on QNN's x86 backend."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def summarize_tensor(tensor: torch.Tensor) -> dict:
    values = tensor.float().reshape(-1)
    finite = torch.isfinite(values)
    finite_values = values[finite]
    result = {
        "shape": list(tensor.shape),
        "finite": bool(finite.all()),
        "nan_count": int(torch.isnan(values).sum()),
        "inf_count": int(torch.isinf(values).sum()),
        "zero_count": int((values == 0).sum()),
        "numel": values.numel(),
    }
    if finite_values.numel():
        result.update(
            {
                "min": float(finite_values.min()),
                "max": float(finite_values.max()),
                "mean": float(finite_values.mean()),
                "std": float(finite_values.std()),
                "min_count": int((finite_values == finite_values.min()).sum()),
                "max_count": int((finite_values == finite_values.max()).sum()),
            }
        )
    return result


def comparison(reference: torch.Tensor, actual: torch.Tensor) -> dict:
    ref = reference.float().reshape(-1)
    got = actual.float().reshape(-1)
    difference = (ref - got).abs()
    return {
        "max_abs": float(difference.max()),
        "mean_abs": float(difference.mean()),
        "cosine": float(F.cosine_similarity(ref, got, dim=0)),
        "reference_l2": float(torch.linalg.vector_norm(ref)),
        "actual_l2": float(torch.linalg.vector_norm(got)),
    }


def make_inputs_from_pte_meta(meta) -> list[torch.Tensor]:
    inputs = []
    for index in range(meta.num_inputs()):
        info = meta.input_tensor_meta(index)
        dtype = {3: torch.int32, 6: torch.float32}.get(info.dtype())
        if dtype is None:
            raise RuntimeError(f"unsupported PTE input dtype {info.dtype()} at {index}")
        inputs.append(torch.zeros(info.sizes(), dtype=dtype))
    return inputs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("qdq", "qnn", "compare"), required=True)
    parser.add_argument("--params", type=Path, required=True)
    parser.add_argument("--token-ids", type=Path, required=True)
    parser.add_argument("--qdq-file", type=Path)
    parser.add_argument("--pte", type=Path)
    parser.add_argument("--qdq-outputs", type=Path, required=True)
    parser.add_argument("--qnn-outputs", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--context", type=int, default=4096)
    args = parser.parse_args()

    experiment = Path(__file__).resolve().parents[1]
    diagnostic = load_module(
        "diagnose_quantized_output", experiment / "tools/diagnose_quantized_output.py"
    )
    adapter = load_module("qwen35_qnn_model", experiment / "tools/qwen35_qnn_model.py")
    from executorch.examples.models.llama.model_args import ModelArgs

    params = json.loads(args.params.read_text())
    config = ModelArgs(
        max_seq_len=args.context,
        max_context_len=args.context,
        max_batch_size=1,
        use_kv_cache=True,
        **params,
    )
    token = int(np.fromfile(args.token_ids, dtype="<i4", count=1)[0])

    if args.phase == "qdq":
        if args.qdq_file is None:
            raise ValueError("--qdq-file is required for qdq phase")
        import torchao.quantization.pt2e.quantize_pt2e  # noqa: F401

        module = torch.export.load(args.qdq_file).module()
        states = diagnostic.make_state_templates(config, args.context)
        mask = torch.full((1, 1, 1, args.context), -65504.0)
        mask[..., -1] = 0.0
        with torch.no_grad():
            outputs = module(
                torch.tensor([[token]], dtype=torch.int32),
                mask,
                torch.tensor([[0]], dtype=torch.int32),
                *states,
            )
        args.qdq_outputs.parent.mkdir(parents=True, exist_ok=True)
        torch.save([output.detach().cpu() for output in outputs], args.qdq_outputs)
        print(args.qdq_outputs)
        return

    if args.phase == "qnn":
        if args.pte is None:
            raise ValueError("--pte is required for qnn phase")
        from executorch.extension.pybindings.portable_lib import _load_for_executorch
        from executorch.extension.llm.custom_ops import custom_ops  # noqa: F401

        module = _load_for_executorch(str(args.pte))
        meta = module.method_meta("forward")
        inputs = make_inputs_from_pte_meta(meta)
        if len(inputs) != 51:
            raise RuntimeError(f"expected 51 PTE inputs, got {len(inputs)}")
        inputs[0][0, 0] = token
        inputs[1].fill_(-65504.0)
        inputs[1][..., -1] = 0.0
        inputs[2][0, 0] = 0
        outputs = module.forward(inputs)
        if len(outputs) != 49:
            raise RuntimeError(f"expected 49 PTE outputs, got {len(outputs)}")
        args.qnn_outputs.parent.mkdir(parents=True, exist_ok=True)
        torch.save([output.detach().cpu().clone() for output in outputs], args.qnn_outputs)
        print(args.qnn_outputs)
        return

    qdq_outputs = torch.load(args.qdq_outputs, map_location="cpu", weights_only=True)
    qnn_outputs = torch.load(args.qnn_outputs, map_location="cpu", weights_only=True)
    if len(qdq_outputs) != len(qnn_outputs) or len(qdq_outputs) != 49:
        raise RuntimeError("output count mismatch")
    records = []
    for index, (reference, actual) in enumerate(zip(qdq_outputs, qnn_outputs)):
        if index == 0:
            kind = "logits"
            layer = None
        elif index <= config.n_layers:
            kind = "state_a"
            layer = index - 1
        else:
            kind = "state_b"
            layer = index - 1 - config.n_layers
        records.append(
            {
                "output_index": index,
                "kind": kind,
                "layer": layer,
                "layer_type": None if layer is None else config.layer_types[layer],
                "qdq": summarize_tensor(reference),
                "qnn_x86": summarize_tensor(actual),
                "comparison": comparison(reference, actual),
            }
        )
    qdq_logits = qdq_outputs[0].float().reshape(-1)
    qnn_logits = qnn_outputs[0].float().reshape(-1)
    qdq_values, qdq_ids = torch.topk(qdq_logits, 10)
    qnn_values, qnn_ids = torch.topk(qnn_logits, 10)
    result = {
        "schema_version": 1,
        "experiment": "0032-qwen-3.5-2b-android-qnn-htp",
        "evidence_class": "host_qnn_x86_first_token_divergence_localization",
        "token_position": 0,
        "token_id": token,
        "qdq_logits": {
            "argmax": int(qdq_logits.argmax()),
            "top_ids": [int(value) for value in qdq_ids],
            "top_values": [float(value) for value in qdq_values],
        },
        "qnn_x86_logits": {
            "argmax": int(qnn_logits.argmax()),
            "top_ids": [int(value) for value in qnn_ids],
            "top_values": [float(value) for value in qnn_values],
        },
        "outputs": records,
        "claim_limits": [
            "QNN x86 backend simulation is host localization evidence, not physical HTP evidence.",
            "Position zero uses zero state, so this comparison does not test cross-token state transport.",
        ],
    }
    args.result.parent.mkdir(parents=True, exist_ok=True)
    args.result.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(args.result)


if __name__ == "__main__":
    main()
