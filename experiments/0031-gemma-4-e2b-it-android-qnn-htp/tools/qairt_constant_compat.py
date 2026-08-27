#!/usr/bin/env python3
"""Narrow QAIRT compatibility patch for ONNX Constant(value_ints=...).

QAIRT 2.49's ``get_constant_np`` assumes every Constant uses the tensor-valued
``value`` attribute. ONNX opset 18 also permits ``value_ints``. The public
Gemma4 checkpoint uses that standard form for four small shape/index tensors.
This module patches only that missing case and does not rewrite checkpoint
bytes or alter tensor-valued constants.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
import re
import sys
from typing import Any


def value_ints_values(
    attributes: Mapping[str, Any], convert_attr_to_py: Callable[[Any], Any]
) -> tuple[int, ...] | None:
    """Return normalized values only for Constant(value_ints=...)."""
    if "value" in attributes or "value_ints" not in attributes:
        return None
    return tuple(int(value) for value in convert_attr_to_py(attributes["value_ints"]))


def gemma4_swa_lengths(auto_regression_number: int, context_length: int) -> tuple[int, int]:
    """Return (KV window, attention-mask width) for Gemma4 sliding attention."""
    past_length = context_length - auto_regression_number
    if past_length < 1:
        raise ValueError("context length must exceed the auto-regression number")
    window = min(512, past_length)
    return window, window + auto_regression_number


def value_ints_array(
    attributes: Mapping[str, Any], convert_attr_to_py: Callable[[Any], Any]
) -> Any:
    """Return the ONNX-specified INT64 tensor for Constant(value_ints=...)."""
    values = value_ints_values(attributes, convert_attr_to_py)
    if values is None:
        return None
    import numpy as np

    return np.asarray(values, dtype=np.int64)


def install() -> dict[str, Any]:
    """Install the narrow patch in QAIRT modules that imported the helper."""
    from qairt.gen_ai_api.builders import htp_mixin
    from qairt.optimizer.onnx.passes.axis_denotation_infer import (
        AxisDenotationConfig,
        AxisDenotationSeedRule,
    )
    import onnx_ir as ir

    from qairt.optimizer.onnx.passes.axis_denotation_infer.propagation_passes import (
        InferIdentityAxisDenotation,
    )
    from qairt.optimizer.onnx.passes.shape_infer import ShapeInference
    from qairt.optimizer.onnx.utils import utils
    from qairt.optimizer.onnx.utils.ir_extra_info import AxisDenotation

    original = utils.get_constant_np
    original_change_seq_and_context_length = htp_mixin.change_seq_and_context_length

    def compatible_get_constant_np(
        value: Any,
        load_external_data: bool = True,
        use_infered_value: bool = False,
    ) -> Any:
        if value is not None and value.const_value is None:
            producer = value.producer()
            if producer is not None and producer.op_type == "Constant":
                converted = value_ints_array(producer.attributes, utils.convert_attr_to_py)
                if converted is not None:
                    return converted
        return original(
            value,
            load_external_data=load_external_data,
            use_infered_value=use_infered_value,
        )

    axis_config = AxisDenotationConfig(
        custom_seed_rules=[
            AxisDenotationSeedRule(
                name_pattern=r"per_layer_inputs",
                denotations=[
                    AxisDenotation.BATCH,
                    AxisDenotation.SEQ_LENGTH,
                    AxisDenotation.UNKNOWN,
                    AxisDenotation.UNKNOWN,
                ],
            ),
            AxisDenotationSeedRule(
                name_pattern=r"position_ids_global_(cos|sin)",
                denotations=[
                    AxisDenotation.BATCH,
                    AxisDenotation.UNKNOWN,
                    AxisDenotation.SEQ_LENGTH,
                    AxisDenotation.UNKNOWN,
                ],
            ),
            AxisDenotationSeedRule(
                name_pattern=r"swa_key_\d+_h\d+_in",
                denotations=[
                    AxisDenotation.BATCH,
                    AxisDenotation.UNKNOWN,
                    AxisDenotation.UNKNOWN,
                    AxisDenotation.SLIDING_CONTEXT_LENGTH,
                ],
            ),
            AxisDenotationSeedRule(
                name_pattern=r"swa_value_\d+_h\d+_in",
                denotations=[
                    AxisDenotation.BATCH,
                    AxisDenotation.UNKNOWN,
                    AxisDenotation.SLIDING_CONTEXT_LENGTH,
                    AxisDenotation.UNKNOWN,
                ],
            ),
            AxisDenotationSeedRule(
                name_pattern=r"past_key_\d+_h\d+_in",
                denotations=[
                    AxisDenotation.BATCH,
                    AxisDenotation.UNKNOWN,
                    AxisDenotation.UNKNOWN,
                    AxisDenotation.PAST_SEQ_LENGTH,
                ],
            ),
            AxisDenotationSeedRule(
                name_pattern=r"past_value_\d+_h\d+_in",
                denotations=[
                    AxisDenotation.BATCH,
                    AxisDenotation.UNKNOWN,
                    AxisDenotation.PAST_SEQ_LENGTH,
                    AxisDenotation.UNKNOWN,
                ],
            ),
        ]
    )

    def compatible_change_seq_and_context_length(
        ctx: Any, new_seq_length: int, new_context_length: int, axis_denotation_config: Any = None
    ) -> Any:
        if axis_denotation_config is not None:
            raise ValueError("unexpected caller-provided axis denotation config")
        result = original_change_seq_and_context_length(
            ctx,
            new_seq_length,
            new_context_length,
            axis_denotation_config=axis_config,
        )
        window, mask_width = gemma4_swa_lengths(new_seq_length, new_context_length)
        changed_inputs = 0
        for value in result.graph_ir.inputs:
            name = value.name or ""
            dims = list(value.shape) if value.shape is not None else []
            if name == "swa_attention_mask" and len(dims) == 4:
                dims[-2:] = [new_seq_length, mask_width]
            elif re.fullmatch(r"swa_key_\d+_h\d+_in", name) and len(dims) == 4:
                dims[-1] = window
            elif re.fullmatch(r"swa_value_\d+_h\d+_in", name) and len(dims) == 4:
                dims[-2] = window
            else:
                continue
            value.shape = ir.Shape(dims)
            changed_inputs += 1
        if changed_inputs != 25:
            raise ValueError(f"expected 25 Gemma4 SWA inputs, changed {changed_inputs}")
        ShapeInference(ShapeInference.Config(overwrite_shape=True)).apply(result)
        return result

    patched_get_constant_bindings = []
    for module_name, module in tuple(sys.modules.items()):
        namespace = getattr(module, "__dict__", {}) if module is not None else {}
        if namespace.get("get_constant_np") is original:
            namespace["get_constant_np"] = compatible_get_constant_np
            patched_get_constant_bindings.append(f"{module_name}.get_constant_np")
    htp_mixin.change_seq_and_context_length = compatible_change_seq_and_context_length
    InferIdentityAxisDenotation.op_types.add("Reciprocal")
    return {
        "patches": [
            {
                "name": "onnx_constant_value_ints_to_int64_numpy",
                "scope": "Constant nodes without value and with value_ints only",
            },
            {
                "name": "gemma4_per_layer_inputs_axis_seed",
                "scope": ["BATCH", "SEQ_LENGTH", "UNKNOWN", "UNKNOWN"],
            },
            {
                "name": "gemma4_global_rope_axis_seed",
                "scope": ["BATCH", "UNKNOWN", "SEQ_LENGTH", "UNKNOWN"],
            },
            {
                "name": "gemma4_h-indexed_kv_axis_seeds",
                "scope": {
                    "swa_key": ["BATCH", "UNKNOWN", "UNKNOWN", "SLIDING_CONTEXT_LENGTH"],
                    "swa_value": ["BATCH", "UNKNOWN", "SLIDING_CONTEXT_LENGTH", "UNKNOWN"],
                    "past_key": ["BATCH", "UNKNOWN", "UNKNOWN", "PAST_SEQ_LENGTH"],
                    "past_value": ["BATCH", "UNKNOWN", "PAST_SEQ_LENGTH", "UNKNOWN"],
                },
            },
            {
                "name": "gemma4_swa_static_shape_materialization",
                "scope": "12 key + 12 value external cache inputs and one SWA attention mask; later shared-KV layers have no graph-cache inputs",
            },
            {
                "name": "reciprocal_axis_propagation",
                "scope": "shape-preserving unary identity denotation",
            },
        ],
        "checkpoint_rewritten": False,
        "patched_bindings": sorted(patched_get_constant_bindings)
        + ["qairt.gen_ai_api.builders.htp_mixin.change_seq_and_context_length"],
    }
