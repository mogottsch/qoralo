#!/usr/bin/env python3
"""Shared INT8 quantization, coverage, and acceptance helpers for Qwen2."""

from __future__ import annotations

import math
from typing import Any

import torch


def quantization_spec() -> dict[str, Any]:
    """Return the locked deployment configuration in JSON-serializable form."""
    return {
        "method": "PT2E post-training dynamic activation/static weight quantization",
        "backend": "XNNPACK",
        "activation": {
            "dtype": "int8",
            "granularity": "per-tensor asymmetric dynamic",
            "qmin": -128,
            "qmax": 127,
        },
        "weight": {
            "dtype": "int8",
            "granularity": "per-output-channel symmetric",
            "qmin": -127,
            "qmax": 127,
        },
        "bias_and_non_linear_ops": "FP32",
        "calibration": (
            "The pinned prefill/decode fixtures are executed once after prepare_pt2e. "
            "Weights are calibrated/frozen per output channel; activation qparams are "
            "computed dynamically for each invocation, so no static activation ranges are reused."
        ),
    }


def int4_quantization_spec() -> dict[str, Any]:
    """Return the attempted INT4 configuration and its deployment gates.

    ExecuTorch 1.2's XNNPACK PT2E API represents the four-bit range as int8
    during conversion, then packs qint4 constants while serializing the
    delegated graph. Package-size evidence is therefore required in addition
    to inspecting the intermediate graph.
    """
    return {
        "method": "PT2E dynamic activation/static weight reduced-range experiment",
        "backend": "XNNPACK",
        "activation": {
            "dtype": "int8",
            "granularity": "per-tensor asymmetric dynamic",
            "qmin": -128,
            "qmax": 127,
        },
        "weight": {
            "logical_dtype": "signed int4",
            "pt2e_intermediate_storage_dtype": "int8",
            "qmin": -8,
            "qmax": 7,
            "granularity": "per-output-channel symmetric (one group per output row)",
            "group_size": "input_features of each Linear (full-row group)",
            "packing": "XNNPACK serialized qint4; require package <=65% of matched INT8 as packing evidence",
        },
        "calibration": (
            "The pinned prefill/decode fixtures would be executed after prepare_pt2e; "
            "dynamic activation qparams need no reusable calibration range. Full-model "
            "calibration is gated on a genuinely packed INT4 representation."
        ),
        "acceptance_gate": (
            "Require packed nibbles, an explicit fixed group size, XNNPACK delegation, "
            "and at least 35% package reduction versus accepted INT8 before prefill."
        ),
    }


def quantize_dynamic_int4_candidate(
    module: torch.nn.Module, inputs: tuple[torch.Tensor, ...]
) -> tuple[torch.fx.GraphModule, dict[str, Any]]:
    """Exercise XNNPACK's four-bit qrange and expose data for package auditing."""
    from executorch.backends.xnnpack.quantizer.xnnpack_quantizer import (
        XNNPACKQuantizer,
        get_symmetric_quantization_config,
    )
    from torchao.quantization.pt2e.quantize_pt2e import convert_pt2e, prepare_pt2e

    captured = torch.export.export(module.eval(), inputs, strict=True).module()
    eligible = sum(
        node.op == "call_function" and node.target == torch.ops.aten.linear.default
        for node in captured.graph.nodes
    )
    if eligible == 0:
        return captured, {
            "eligible_linear_ops": 0,
            "four_bit_range_linear_ops": 0,
            "four_bit_range_sites": 0,
            "storage_dtypes": [],
            "storage_bits_per_weight": [],
            "serialized_packing": "not applicable: stage has no Linear weights",
            "group_size": "not applicable",
            "granularity": "not applicable",
            "delegation_target": "XNNPACK",
            "candidate_ready_for_package_audit": True,
            "fallback_if_rejected": "accepted dynamic-activation/per-channel-weight INT8 XNNPACK package",
        }
    config = get_symmetric_quantization_config(
        is_per_channel=True,
        is_dynamic=True,
        weight_qmin=-8,
        weight_qmax=7,
    )
    prepared = prepare_pt2e(captured, XNNPACKQuantizer().set_global(config))
    with torch.no_grad():
        prepared(*inputs)
    converted = convert_pt2e(prepared)
    graph_text = str(converted.graph)
    frozen = [
        value for name, value in converted.state_dict().items()
        if "_frozen_param" in name and isinstance(value, torch.Tensor)
    ]
    # Frozen parameters are sometimes attributes rather than state_dict entries.
    if not frozen:
        frozen = [
            value for name, value in vars(converted).items()
            if "_frozen_param" in name and isinstance(value, torch.Tensor)
        ]
    storage_dtypes = sorted({str(value.dtype).removeprefix("torch.") for value in frozen})
    storage_bits = sorted({value.element_size() * 8 for value in frozen})
    ranged = graph_text.count("-8, 7")
    quantized = min(eligible, graph_text.count("dequantize_per_channel"))
    return converted, {
        "eligible_linear_ops": eligible,
        "four_bit_range_linear_ops": quantized,
        "four_bit_range_sites": ranged,
        "storage_dtypes": storage_dtypes or ["int8"],
        "storage_bits_per_weight": storage_bits or [8],
        "serialized_packing": "must be audited after XNNPACK lowering from matched package size",
        "group_size": "input_features of each Linear (full-row group)",
        "granularity": "per-output-channel whole-row scale",
        "delegation_target": "XNNPACK",
        "candidate_ready_for_package_audit": True,
        "fallback_if_rejected": "accepted dynamic-activation/per-channel-weight INT8 XNNPACK package",
    }


def quantize_dynamic_int8(
    module: torch.nn.Module, inputs: tuple[torch.Tensor, ...]
) -> tuple[torch.fx.GraphModule, dict[str, Any]]:
    """PT2E-quantize a captured component and return an auditable coverage report."""
    from executorch.backends.xnnpack.quantizer.xnnpack_quantizer import (
        XNNPACKQuantizer,
        get_symmetric_quantization_config,
    )
    from torchao.quantization.pt2e.quantize_pt2e import convert_pt2e, prepare_pt2e

    captured = torch.export.export(module.eval(), inputs, strict=True).module()
    eligible = sum(
        node.op == "call_function" and node.target == torch.ops.aten.linear.default
        for node in captured.graph.nodes
    )
    if eligible == 0:
        return captured, {
            "eligible_linear_ops": 0,
            "quantized_linear_ops": 0,
            "dynamic_activation_sites": 0,
            "linear_op_coverage": 1.0,
            "fallback_linear_ops": 0,
            "fallback_policy": "reject any component with eligible Linear coverage below 95%",
            "accepted": True,
        }
    config = get_symmetric_quantization_config(is_per_channel=True, is_dynamic=True)
    prepared = prepare_pt2e(captured, XNNPACKQuantizer().set_global(config))
    with torch.no_grad():
        prepared(*inputs)  # deterministic pinned calibration/smoke invocation
    converted = convert_pt2e(prepared)
    graph_text = str(converted.graph)
    quantized_weights = graph_text.count("dequantize_per_channel")
    dynamic_activations = graph_text.count("choose_qparams")
    covered = min(eligible, quantized_weights)
    ratio = 1.0 if eligible == 0 else covered / eligible
    return converted, {
        "eligible_linear_ops": eligible,
        "quantized_linear_ops": covered,
        "dynamic_activation_sites": dynamic_activations,
        "linear_op_coverage": ratio,
        "fallback_linear_ops": eligible - covered,
        "fallback_policy": "reject any component with eligible Linear coverage below 95%",
        "accepted": eligible == 0 or ratio >= 0.95,
    }


def _cosine(actual: torch.Tensor, expected: torch.Tensor) -> float:
    a = actual.detach().float().reshape(-1).double()
    b = expected.detach().float().reshape(-1).double()
    denominator = float(torch.linalg.vector_norm(a) * torch.linalg.vector_norm(b))
    if denominator == 0:
        return 1.0 if torch.equal(a, b) else 0.0
    return float(torch.dot(a, b) / denominator)


def quantized_comparison(
    actual: tuple[torch.Tensor, ...], expected: tuple[torch.Tensor, ...], names: list[str]
) -> dict[str, Any]:
    """Report absolute and scale-normalized INT8 error without hiding FP32 drift."""
    if len(actual) != len(expected) or len(actual) != len(names):
        raise ValueError("actual, expected, and names must have equal lengths")
    details: list[dict[str, Any]] = []
    squared_error = squared_reference = 0.0
    all_finite = True
    for name, got, want in zip(names, actual, expected):
        difference = (got.float() - want.float()).abs()
        finite = bool(torch.isfinite(got).all() and torch.isfinite(difference).all())
        all_finite &= finite
        mse_sum = float(torch.square(got.float() - want.float()).double().sum())
        ref_sum = float(torch.square(want.float()).double().sum())
        squared_error += mse_sum
        squared_reference += ref_sum
        details.append({
            "name": name,
            "numel": got.numel(),
            "finite": finite,
            "max_abs_error": float(difference.max()) if finite else math.inf,
            "mean_abs_error": float(difference.mean()) if finite else math.inf,
            "cosine_similarity": _cosine(got, want) if finite else 0.0,
            "nrmse": math.sqrt(mse_sum / max(ref_sum, 1e-30)) if finite else math.inf,
        })
    logits = details[1]
    hidden = details[0]
    caches = details[2:]
    token_actual = int(actual[1].float().argmax(-1).reshape(-1)[0])
    token_expected = int(expected[1].float().argmax(-1).reshape(-1)[0])
    aggregate_nrmse = math.sqrt(squared_error / max(squared_reference, 1e-30))
    cache_nrmse = max((item["nrmse"] for item in caches), default=0.0)
    cache_cosine = min((item["cosine_similarity"] for item in caches), default=1.0)
    accepted = (
        all_finite
        and token_actual == token_expected
        and hidden["cosine_similarity"] >= 0.99
        and logits["cosine_similarity"] >= 0.99
        and aggregate_nrmse <= 0.05
        and cache_nrmse <= 0.12
        and cache_cosine >= 0.99
    )
    return {
        "all_finite": all_finite,
        "token": {
            "actual_argmax": token_actual,
            "fp32_argmax": token_expected,
            "exact_match": token_actual == token_expected,
        },
        "aggregate_nrmse": aggregate_nrmse,
        "maximum_cache_nrmse": cache_nrmse,
        "minimum_cache_cosine_similarity": cache_cosine,
        "criteria": {
            "hidden_cosine_min": 0.99,
            "logits_cosine_min": 0.99,
            "aggregate_nrmse_max": 0.05,
            "each_cache_nrmse_max": 0.12,
            "each_cache_cosine_min": 0.99,
            "argmax_token_exact": True,
            "all_outputs_finite": True,
            "rationale": (
                "INT8 is evaluated against pinned eager FP32, not the FP32 delegate tolerance. "
                "Cosine >=0.99 protects direction for hidden/logit/cache vectors, aggregate NRMSE "
                "<=5% bounds energy-weighted drift, per-cache NRMSE <=12% covers low-energy value "
                "caches without hiding it, and the externally consumed greedy token must match exactly."
            ),
        },
        "accepted": accepted,
        "output_details": details,
    }


def deployment_benefit(
    *, int8_bytes: int, fp32_bytes: int, coverages: list[dict[str, Any]]
) -> dict[str, Any]:
    ratio = int8_bytes / fp32_bytes
    coverage_ok = all(item["accepted"] for item in coverages)
    accepted = coverage_ok and ratio <= 0.75
    return {
        "int8_bytes": int8_bytes,
        "fp32_baseline_bytes": fp32_bytes,
        "size_ratio": ratio,
        "size_reduction_fraction": 1.0 - ratio,
        "coverage_accepted": coverage_ok,
        "criterion": "all eligible components >=95% Linear coverage and >=25% package-size reduction",
        "accepted": accepted,
        "rejection_reason": None if accepted else "fallback/size outcome defeats the required deployment benefit",
    }
