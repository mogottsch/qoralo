import importlib.util
import unittest
from pathlib import Path

import numpy as np
import onnx
from onnx import TensorProto, helper, numpy_helper

TOOL = Path(__file__).parents[1] / "tools/rewrite_vector_softplus.py"
SPEC = importlib.util.spec_from_file_location("rewrite", TOOL)
rewrite = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(rewrite)


def model(*, graph_output=False, extra_consumer=False, dtype=TensorProto.FLOAT):
    x = helper.make_tensor_value_info("x", TensorProto.FLOAT, [2, 256])
    y = helper.make_tensor_value_info("y", TensorProto.FLOAT, [2, 256])
    target_info = helper.make_tensor_value_info(rewrite.TARGET_INPUT, dtype, [2, 256])
    softplus_info = helper.make_tensor_value_info(rewrite.TARGET_OUTPUT, TensorProto.FLOAT, [2, 256])
    before = helper.make_node("Identity", ["x"], [rewrite.TARGET_INPUT], name="before")
    target = helper.make_node("Softplus", [rewrite.TARGET_INPUT], [rewrite.TARGET_OUTPUT], name=rewrite.TARGET_NAME)
    consumer = helper.make_node("Tanh", [rewrite.TARGET_OUTPUT], ["y"], name=rewrite.EXPECTED_CONSUMER)
    nodes = [before, target, consumer]
    outputs = [y]
    if extra_consumer:
        nodes.append(helper.make_node("Identity", [rewrite.TARGET_OUTPUT], ["extra"], name="extra-consumer"))
        outputs.append(helper.make_tensor_value_info("extra", TensorProto.FLOAT, [2, 256]))
    if graph_output:
        outputs.append(softplus_info)
    graph = helper.make_graph(nodes, "test", [x], outputs, [numpy_helper.from_array(np.asarray(2.0, dtype=np.float32), name="existing")], value_info=[target_info, softplus_info])
    return helper.make_model(graph, opset_imports=[helper.make_opsetid("", 19)])


class RewriteTests(unittest.TestCase):
    def test_exact_replacement_and_original_content_preserved(self):
        source = model()
        original_before = source.graph.node[0].SerializeToString()
        original_after = source.graph.node[2].SerializeToString()
        original_initializer = source.graph.initializer[0].SerializeToString()
        candidate, report = rewrite.rewrite(source)
        self.assertEqual([n.op_type for n in candidate.graph.node], ["Identity", "Relu", "Abs", "Neg", "Exp", "Add", "Log", "Add", "Tanh"])
        self.assertEqual(candidate.graph.node[0].SerializeToString(), original_before)
        self.assertEqual(candidate.graph.node[-1].SerializeToString(), original_after)
        self.assertEqual(candidate.graph.initializer[0].SerializeToString(), original_initializer)
        self.assertEqual(candidate.graph.initializer[-1].name, rewrite.ONE_NAME)
        self.assertEqual(candidate.graph.node[-2].output[0], rewrite.TARGET_OUTPUT)
        self.assertEqual(report["input_contract"], {"name": rewrite.TARGET_INPUT, "dtype": "float32", "shape": [2, 256]})
        onnx.checker.check_model(candidate, full_check=True)

    def test_stable_formula_matches_reference_for_extreme_values(self):
        x = np.asarray([-1e6, -100, -20, -1, 0, 1, 20, 100, 1e6], dtype=np.float64)
        actual = np.maximum(x, 0) + np.log1p(np.exp(-np.abs(x)))
        expected = np.logaddexp(0, x)
        np.testing.assert_allclose(actual, expected, rtol=0, atol=1e-14)
        self.assertTrue(np.isfinite(actual).all())

    def test_rejects_target_as_graph_output(self):
        with self.assertRaisesRegex(ValueError, "graph output"):
            rewrite.rewrite(model(graph_output=True))

    def test_rejects_extra_consumer(self):
        with self.assertRaisesRegex(ValueError, "unsafe consumer"):
            rewrite.rewrite(model(extra_consumer=True))

    def test_rejects_wrong_dtype(self):
        with self.assertRaisesRegex(ValueError, "expected float32"):
            rewrite.rewrite(model(dtype=TensorProto.FLOAT16))


if __name__ == "__main__":
    unittest.main()
