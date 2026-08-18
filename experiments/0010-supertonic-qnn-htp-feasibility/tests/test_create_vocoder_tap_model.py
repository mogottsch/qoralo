#!/usr/bin/env python3
from __future__ import annotations
import importlib.util,unittest
from pathlib import Path
import onnx
from onnx import TensorProto,helper
TOOL=Path(__file__).resolve().parents[1]/'tools/create_vocoder_tap_model.py';spec=importlib.util.spec_from_file_location('taptool',TOOL);assert spec and spec.loader;taptool=importlib.util.module_from_spec(spec);spec.loader.exec_module(taptool)
def model()->onnx.ModelProto:
 inp=helper.make_tensor_value_info('latent',TensorProto.FLOAT,[1,24,1428]);mid=helper.make_tensor_value_info('mid',TensorProto.FLOAT,[1,24,1428]);tap=helper.make_tensor_value_info('/Add_output_0',TensorProto.FLOAT,[1,24,1428]);out=helper.make_tensor_value_info('downstream',TensorProto.FLOAT,[1,24,1428]);zero=helper.make_tensor('zero',TensorProto.FLOAT,[],[0.0]);nodes=[helper.make_node('Identity',['latent'],['mid'],name='before'),helper.make_node('Add',['mid','zero'],['/Add_output_0'],name='tap'),helper.make_node('Identity',['/Add_output_0'],['downstream'],name='after')];m=helper.make_model(helper.make_graph(nodes,'g',[inp],[out],[zero],value_info=[mid,tap]),opset_imports=[helper.make_opsetid('',19)]);onnx.checker.check_model(m);return m
class TapTest(unittest.TestCase):
 def test_extracts_only_dependency_prefix_and_preserves_exact_name(self):
  source=model();result=taptool.extract_tap(source,'predecoder_affine');self.assertEqual([n.name for n in result.graph.node],['before','tap']);self.assertEqual(result.graph.output[0].name,'/Add_output_0');self.assertEqual([d.dim_value for d in result.graph.output[0].type.tensor_type.shape.dim],[1,24,1428]);self.assertEqual([n.name for n in source.graph.node],['before','tap','after']);onnx.checker.check_model(result)
 def test_rejects_absent_exact_tensor(self):
  with self.assertRaisesRegex(ValueError,'tap tensor absent'):taptool.extract_tap(model(),'convnext3_add')
 def test_registry_has_unique_exact_tensors_and_positive_shapes(self):
  tensors=[t.tensor for t in taptool.TAPS.values()];self.assertEqual(len(tensors),len(set(tensors)));self.assertTrue(all(all(d>0 for d in t.shape) for t in taptool.TAPS.values()))
if __name__=='__main__':unittest.main()
