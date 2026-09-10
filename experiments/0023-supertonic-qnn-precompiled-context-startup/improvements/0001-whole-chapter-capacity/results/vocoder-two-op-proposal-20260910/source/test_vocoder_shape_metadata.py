import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import onnx
from onnx import helper,TensorProto

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import vocoder_shape_metadata as metadata


class MetadataTests(unittest.TestCase):
    def test_leaf_metadata_only_skips_embedded_tensor_and_nodes(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'toy.onnx'
            weight=helper.make_tensor('unused',TensorProto.FLOAT,[4096],[0.5]*4096)
            graph=helper.make_graph([helper.make_node('Identity',['x'],['y'])],'toy',[helper.make_tensor_value_info('x',1,[1,3])],[helper.make_tensor_value_info('y',1,[1,3])],[weight])
            path.write_bytes(helper.make_model(graph).SerializeToString());digest=hashlib.sha256(path.read_bytes()).hexdigest()
            with patch.object(onnx,'load',side_effect=AssertionError('no model load')),patch.object(onnx,'load_model',side_effect=AssertionError('no model load')):
                result=metadata.inspect(path,digest)
            self.assertEqual(2,len(result['rows']));self.assertEqual([12,12],[v['logical_bytes'] for v in result['rows']]);self.assertEqual(1,result['graph_field_counts']['5'])
            self.assertEqual(0,result['initializer_or_Constant_payloads_decoded']);self.assertLess(result['metadata_payload_bytes_decoded'],256)

    def test_unresolved_dims_remain_null_and_identity_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'toy.onnx';graph=helper.make_graph([],'toy',[helper.make_tensor_value_info('x',1,['N',3])],[]);path.write_bytes(helper.make_model(graph).SerializeToString())
            with self.assertRaises(ValueError):metadata.inspect(path,'bad')
            result=metadata.inspect(path,hashlib.sha256(path.read_bytes()).hexdigest());self.assertIsNone(result['rows'][0]['logical_bytes'])


if __name__=='__main__':unittest.main()
