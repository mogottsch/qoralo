import importlib.util
from pathlib import Path
import unittest
import numpy as np
import onnx
from onnx import helper, numpy_helper

TOOL=Path(__file__).resolve().parents[1]/'tools/materialize.py'
spec=importlib.util.spec_from_file_location('materialize0036',TOOL)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def source():
    table=helper.make_tensor(m.capacity.INCREMENTS,onnx.TensorProto.INT64,[1,1000,1],range(1000))
    theta=numpy_helper.from_array(np.arange(32,dtype=np.float32).reshape(1,1,32),m.capacity.THETA)
    w=numpy_helper.from_array(np.array([0.25,-2],dtype=np.float32),'learned_weight')
    return helper.make_model(helper.make_graph([], 'test', [], [], [table,theta,w]))


class PositionTests(unittest.TestCase):
    def test_extent_and_prefix(self):
        a=source();b=m.extend_positions(a,3200)
        np.testing.assert_array_equal(numpy_helper.to_array(b.graph.initializer[0]),np.arange(3200).reshape(1,3200,1))
        np.testing.assert_array_equal(numpy_helper.to_array(b.graph.initializer[0])[:,:1000],numpy_helper.to_array(a.graph.initializer[0]))
        self.assertEqual(list(a.graph.initializer[0].dims),[1,1000,1])

    def test_other_bytes_unchanged(self):
        a=source();b=m.extend_positions(a,4096)
        for before,after in zip(a.graph.initializer[1:],b.graph.initializer[1:]):
            self.assertEqual(before.SerializeToString(),after.SerializeToString())
        self.assertEqual([n.SerializeToString() for n in a.graph.node],[n.SerializeToString() for n in b.graph.node])

    def test_invalid_extent(self):
        for extent in (0,999,16385,True,3200.0):
            with self.subTest(extent=extent),self.assertRaises(ValueError):
                m.extend_positions(source(),extent)

    def test_corrupt_table_rejected(self):
        a=source();a.graph.initializer[0].int64_data[10]=999
        with self.assertRaises(ValueError):m.extend_positions(a,3200)

    def test_duplicate_table_rejected(self):
        a=source();a.graph.initializer.append(a.graph.initializer[0])
        with self.assertRaises(ValueError):m.extend_positions(a,3200)

    def test_no_neural_import(self):
        # Runtime imports belong only to the constructor worker, never materialization.
        import ast
        tree=ast.parse(TOOL.read_text())
        names=[]
        for node in ast.walk(tree):
            if isinstance(node,ast.Import):names.extend(n.name.split('.')[0] for n in node.names)
            if isinstance(node,ast.ImportFrom):names.append((node.module or '').split('.')[0])
        self.assertFalse(set(names)&{'torch','onnxruntime','executorch'})

    def test_real_prepared_duration_text_deltas(self):
        import json
        root=TOOL.parents[1]/'.local/graphs'
        if not (root/'duration/structural-delta.json').exists():self.skipTest('local artifacts absent')
        for name in ('duration','text'):
            delta=json.loads((root/name/'structural-delta.json').read_text())
            self.assertTrue(all(row['unchanged'] for row in delta['initializers']))
            self.assertEqual(delta['inputs']['text_ids'],[1,3200])
            self.assertEqual(delta['source_nodes'],delta['derived_nodes'])


if __name__=='__main__':unittest.main()
