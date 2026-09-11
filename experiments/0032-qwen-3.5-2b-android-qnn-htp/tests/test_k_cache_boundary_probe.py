"""Small CPU-array/scalar tests; no Torch/SDK/model calls."""
import importlib.util
from pathlib import Path
import struct
import sys
import unittest
import numpy as np

TOOLS=Path(__file__).resolve().parents[1]/'tools'
sys.path.insert(0,str(TOOLS))
import k_cache_boundary_probe as p
from audit_conv_history_metadata import scalar_qdq


class BoundaryTests(unittest.TestCase):
    def test_scope_and_domains(self):
        ds=p.domains();self.assertEqual([d['state_index'] for d in ds],[3,15])
        self.assertEqual(ds[0]['input']['zero_point'],42000)
        self.assertEqual(ds[1]['input']['zero_point'],32369)
        self.assertTrue(all(d['input']['scale']!=d['output']['scale'] for d in ds))
        self.assertEqual(p.SHAPES,(p.CACHE,p.KEY,p.CACHE,p.KEY))

    def test_sparse_input_binding(self):
        a=p.arrays();self.assertEqual(sum(v.nbytes for v in a),16777216)
        self.assertEqual([np.count_nonzero(v) for v in a],[2,0,1,0])
        self.assertEqual(float(a[0][p.ANCHOR]),p.ANCHOR_VALUE)
        self.assertEqual(float(a[2][p.ANCHOR]),1.0)

    def test_numpy_matches_independent_scalar(self):
        values=np.array([-12.0,-1.0,0,1,4.0,p.ANCHOR_VALUE],dtype='f4')
        for d in p.domains():
            for e in [d['input'],d['output']]:
                actual=p.qdq(values,e)
                expected=np.array([scalar_qdq(float(x),e)['output_fp32'] for x in values],dtype='f4')
                self.assertEqual(actual.tobytes(),expected.tobytes())

    def test_small_cat_geometry_and_discrimination(self):
        # Small arrays check scalar/index oracle construction only, not exported ABI.
        a=np.array([[[[p.ANCHOR_VALUE,1.0]]]],dtype='f4');key=np.zeros((1,1,1,1),dtype='f4')
        ref=p.oracle([a,key,a*0,key],p.domains());alt=p.oracle([a,key,a*0,key],p.domains(),True)
        self.assertEqual(ref[0].shape,(1,1,1,3));self.assertEqual(float(ref[0][0,0,0,2]),0.0)
        self.assertGreater(abs(float(ref[0][0,0,0,0])-float(alt[0][0,0,0,0])),3)
        self.assertEqual(ref[1].tobytes(),alt[1].tobytes())

    def test_import_does_not_activate_models_or_sdk(self):
        self.assertNotIn('torch',sys.modules);self.assertNotIn('executorch',sys.modules)
        self.assertNotIn('onnxruntime',sys.modules)


if __name__=='__main__':unittest.main()
