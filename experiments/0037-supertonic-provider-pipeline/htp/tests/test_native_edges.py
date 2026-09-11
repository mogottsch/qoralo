"""Synthetic only: no source models, neural sessions, device or compilation."""
import importlib.util
from pathlib import Path
import sys
import unittest

TOOLS = Path(__file__).resolve().parents[1] / 'tools'
sys.path.insert(0, str(TOOLS))
import numpy as np
import onnx
from onnx import helper, numpy_helper
from materialize import RADII, edge_indices, lower_native_edges
from check_padding import extent, pad


class NativeEdges(unittest.TestCase):
    def test_exact_native_edge_for_every_supported_length_and_radius(self):
        # Adversarial garbage beyond nativeL must never enter a native convolution.
        backing = np.arange(2*3*512, dtype=np.float32).reshape(2, 3, 512)
        for length in range(1, 513):
            for radius, indices in zip(RADII, edge_indices(length, 512).values()):
                gathered = np.take(backing, indices, axis=2)[..., :length+2*radius]
                native = np.pad(backing[..., :length], [(0, 0), (0, 0), (radius, radius)], mode='edge')
                np.testing.assert_array_equal(native, gathered)
                self.assertEqual(indices.dtype, np.int32)
                self.assertEqual(indices.shape, (512+2*radius,))
                self.assertLess(int(indices.max()), length)

    def test_invalid_length_rejected_without_clamping_duration(self):
        for native, bucket in [(0, 512), (513, 512), (1, 1001)]:
            with self.assertRaises(ValueError):
                edge_indices(native, bucket)

    def test_native_noise_layout_not_bucket_stride(self):
        a = np.arange(144*7, dtype=np.float32).reshape(1, 144, 7)
        b = pad(a, 512)
        np.testing.assert_array_equal(b[..., :7], a)
        self.assertTrue(np.all(b[..., 7:] == 0))
        self.assertEqual(b[0, 1, 0], 7)
        with self.assertRaises(ValueError):
            pad(a, 6)

    def test_provider_fp32_extent_and_no_floor_crop(self):
        d, length = extent(np.float32(19.881694793701172))
        self.assertEqual(length, 272)
        self.assertEqual(d, float(np.float32(18.934947967529297)))
        self.assertGreater(length*3072, int(np.float32(d)*np.float32(44100)))

    @staticmethod
    def model():
        nodes, tensors, outputs = [], [], []
        for i in range(28):
            radius = RADII[i % 4]
            name = f'/vector_estimator/vector_field/main_blocks.{i}/convnext.0/dwconv/Pad'
            tensor_name, output_name = f'pads_{i}', f'out_{i}'
            tensors.append(numpy_helper.from_array(np.array([0, 0, radius, 0, 0, radius], dtype=np.int64), tensor_name))
            nodes.append(helper.make_node('Pad', ['data', tensor_name], [output_name], name=name, mode='edge'))
            outputs.append(helper.make_tensor_value_info(output_name, onnx.TensorProto.FLOAT, [2, 3, 512+2*radius]))
        return helper.make_model(helper.make_graph(nodes, 'synthetic_edge_sites',
            [helper.make_tensor_value_info('data', onnx.TensorProto.FLOAT, [2, 3, 512])], outputs, tensors),
            opset_imports=[helper.make_opsetid('', 19)])

    def test_only_edge_sites_and_abi_changed(self):
        original = self.model()
        before = original.SerializeToString()
        result, rows = lower_native_edges(original, 512)
        self.assertEqual(original.SerializeToString(), before)
        self.assertEqual(len(rows), 28)
        self.assertEqual(len(result.graph.input), 5)
        self.assertEqual([v.SerializeToString() for v in original.graph.initializer],
                         [v.SerializeToString() for v in result.graph.initializer])
        self.assertTrue(all(n.op_type == 'Gather' for n in result.graph.node))
        onnx.checker.check_model(result, full_check=True)

    def test_changed_padding_contract_rejected(self):
        original = self.model()
        original.graph.initializer[0].CopyFrom(numpy_helper.from_array(np.array([0, 0, 2, 0, 0, 0], dtype=np.int64), 'pads_0'))
        with self.assertRaises(ValueError):
            lower_native_edges(original, 512)

    def test_missing_edge_site_rejected(self):
        original = self.model()
        del original.graph.node[-1]
        with self.assertRaises(ValueError):
            lower_native_edges(original, 512)


if __name__ == '__main__':
    unittest.main()
