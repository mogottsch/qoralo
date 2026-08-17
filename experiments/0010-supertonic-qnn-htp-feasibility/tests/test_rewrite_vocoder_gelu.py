#!/usr/bin/env python3
"""Safety tests for the model-specific explicit-GELU rewrite."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

import numpy as np
import onnx
from onnx import TensorProto, helper

TOOL = Path(__file__).resolve().parents[1] / "tools" / "rewrite_vocoder_gelu.py"
SPEC = importlib.util.spec_from_file_location("rewrite_vocoder_gelu", TOOL)
assert SPEC and SPEC.loader
rewrite = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(rewrite)


def make_model(*, sqrt_2: np.float32 = np.float32(np.sqrt(np.float32(2.0))), unsafe: bool = False) -> onnx.ModelProto:
    nodes = [
        helper.make_node("Constant", [], ["sqrt2"], name="sqrt2_constant", value=helper.make_tensor("sqrt2_value", TensorProto.FLOAT, [], [sqrt_2])),
        helper.make_node("Constant", [], ["one"], name="one_constant", value=helper.make_tensor("one_value", TensorProto.FLOAT, [], [1.0])),
        helper.make_node("Constant", [], ["half"], name="half_constant", value=helper.make_tensor("half_value", TensorProto.FLOAT, [], [0.5])),
    ]
    inputs = []
    outputs = []
    value_info = []
    for index in range(10):
        prefix = f"/decoder/convnext.{index}/act"
        x, div, erf, add, mul, out = (f"x{index}", f"div{index}", f"erf{index}", f"add{index}", f"mul{index}", f"out{index}")
        inputs.append(helper.make_tensor_value_info(x, TensorProto.FLOAT, [1, 4, 3]))
        outputs.append(helper.make_tensor_value_info(out, TensorProto.FLOAT, [1, 4, 3]))
        value_info.extend(helper.make_tensor_value_info(name, TensorProto.FLOAT, [1, 4, 3]) for name in (div, erf, add, mul))
        nodes.extend([
            helper.make_node("Div", [x, "sqrt2"], [div], name=f"{prefix}/Div"),
            helper.make_node("Erf", [div], [erf], name=f"{prefix}/Erf"),
            helper.make_node("Add", [erf, "one"], [add], name=f"{prefix}/Add"),
            helper.make_node("Mul", [x, add], [mul], name=f"{prefix}/Mul"),
            helper.make_node("Mul", [mul, "half"], [out], name=f"{prefix}/Mul_1"),
        ])
    if unsafe:
        nodes.append(helper.make_node("Identity", ["erf0"], ["unsafe"], name="unsafe_external_consumer"))
        outputs.append(helper.make_tensor_value_info("unsafe", TensorProto.FLOAT, [1, 4, 3]))
    graph = helper.make_graph(nodes, "gelu_test", inputs, outputs, value_info=value_info)
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 19), helper.make_opsetid("com.microsoft", 1)])
    onnx.checker.check_model(model)
    return model


class RewriteVocoderGeluTest(unittest.TestCase):
    def test_accepts_exact_eight_selected_chains_and_records_safety(self) -> None:
        records = rewrite.analyze(make_model())
        self.assertEqual(len(records), 8)
        self.assertEqual([record["prefix"] for record in records], list(rewrite.EXPECTED_PREFIXES))
        self.assertTrue(all(record["safety"]["reuses_identical_x"] for record in records))
        self.assertTrue(all(record["safety"]["each_removed_intermediate_has_exactly_one_consumer"] for record in records))

    def test_rejects_external_consumer_of_removed_intermediate(self) -> None:
        with self.assertRaisesRegex(ValueError, "has 2 consumers"):
            rewrite.analyze(make_model(unsafe=True))

    def test_rejects_nonexact_sqrt_two_constant(self) -> None:
        wrong = np.nextafter(rewrite.EXPECTED_CONSTANTS["sqrt_2"], np.float32(2.0), dtype=np.float32)
        with self.assertRaisesRegex(ValueError, "sqrt\\(2\\) constant mismatch"):
            rewrite.analyze(make_model(sqrt_2=wrong))


if __name__ == "__main__":
    unittest.main()
