#!/usr/bin/env python3
import importlib.util,unittest
from pathlib import Path
import onnx
from onnx import TensorProto,helper
P=Path(__file__).resolve().parents[1]/'tools/create_vocoder_qdq_microprobe.py';s=importlib.util.spec_from_file_location('micro',P);assert s and s.loader;m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def model(rename=False):
 i=helper.make_tensor_value_info('latent',TensorProto.FLOAT,m.SHAPE);pad=helper.make_tensor_value_info(m.INPUT,TensorProto.FLOAT,m.SHAPE);out=helper.make_tensor_value_info(m.OUTPUT,TensorProto.FLOAT,m.SHAPE);scale=helper.make_tensor('scale',TensorProto.FLOAT,[],[.01]);zero=helper.make_tensor('zero',TensorProto.UINT8,[],[128]);nodes=[helper.make_node('Identity',['latent'],[m.INPUT],name='upstream'),helper.make_node('QuantizeLinear',[m.INPUT,'scale','zero'],['q'],name='wrong' if rename else m.NODES[0]),helper.make_node('DequantizeLinear',['q','scale','zero'],[m.OUTPUT],name=m.NODES[1])];x=helper.make_model(helper.make_graph(nodes,'g',[i],[out],[scale,zero],value_info=[pad]),opset_imports=[helper.make_opsetid('',19)]);onnx.checker.check_model(x);return x
class Test(unittest.TestCase):
 def test_exact_two_node_extraction(self):
  x=m.extract(model());self.assertEqual([n.name for n in x.graph.node],m.NODES);self.assertEqual(x.graph.input[0].name,m.INPUT);self.assertEqual(x.graph.output[0].name,m.OUTPUT);self.assertEqual({i.name for i in x.graph.initializer},{'scale','zero'});onnx.checker.check_model(x)
 def test_rejects_changed_exact_node(self):
  with self.assertRaisesRegex(ValueError,'unexpected extracted nodes'):m.extract(model(True))
if __name__=='__main__':unittest.main()
