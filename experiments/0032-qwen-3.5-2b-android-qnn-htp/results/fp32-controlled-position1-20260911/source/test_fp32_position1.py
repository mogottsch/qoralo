import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
import torch

TOOLS=Path(__file__).resolve().parents[1]/'tools'
sys.path.insert(0,str(TOOLS))
import compare_fp32_position1 as worker


class FP32ReferenceTests(unittest.TestCase):
    def test_hidden_tap_never_replaces_or_changes_layer_output(self):
        class Layer(torch.nn.Module):
            def forward(self,x):return x+1,x*2,x*3
        class Model(torch.nn.Module):
            def __init__(self):super().__init__();self.layers=torch.nn.ModuleList([Layer(),Layer()])
            def forward(self,x):
                for l in self.layers:x=l(x)[0]
                return x
        m=Model();data=torch.tensor([2.]);plain=m(data)
        captured,handles=worker.capture_hidden(m)
        actual=m(data)
        self.assertTrue(torch.equal(plain,actual));self.assertEqual([float(x) for x in captured],[3.,4.])
        actual.add_(50);self.assertEqual(float(captured[-1]),4.)
        for h in handles:h.remove()
        m(data);self.assertEqual(len(captured),2)

    def test_load_copies_weights_without_staling_plain_recurrence_alias(self):
        class Attention(torch.nn.Module):
            def __init__(self):
                super().__init__();self.A_log=torch.nn.Parameter(torch.zeros(2));self.dt_bias=torch.nn.Parameter(torch.zeros(2))
                self.recurrence=torch.nn.Module();object.__setattr__(self.recurrence,'_a_log',self.A_log);object.__setattr__(self.recurrence,'_dt_bias',self.dt_bias)
        class Layer(torch.nn.Module):
            def __init__(self):super().__init__();self.is_linear=True;self.attention=Attention()
        m=torch.nn.Module();m.layers=torch.nn.ModuleList([Layer()]);old=m.layers[0].attention.A_log
        state={k:torch.full_like(v,3).bfloat16() for k,v in m.state_dict().items()}
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'small.pt';torch.save(state,path)
            result=worker.load_weights(m,SimpleNamespace(adapt_converted_state_dict=lambda x:x),path)
            self.assertIs(m.layers[0].attention.A_log,old)
            self.assertIs(m.layers[0].attention.recurrence._a_log,old)
            self.assertTrue(torch.equal(old,torch.full_like(old,3)))
            self.assertEqual(result['checkpoint_tensor_dtype_counts'],{'torch.bfloat16':2})

    def test_zero_norm_is_null_not_a_failed_forward(self):
        m=worker.tensor_metrics(torch.zeros(4),torch.zeros(4));self.assertIsNone(m['cosine']);self.assertTrue(m['finite']);self.assertEqual(m['l2'],0)

    def test_nonfinite_is_retained_as_a_numerical_limitation(self):
        m=worker.tensor_metrics(torch.ones(2),torch.tensor([float('nan'),1.]));self.assertFalse(m['finite']);self.assertIsNone(m['max_abs'])

    def test_shape_mismatch_rejected(self):
        with self.assertRaises(ValueError):worker.tensor_metrics(torch.ones(2),torch.ones(3))

    def test_l2_orientation_and_all73(self):
        reference=[torch.tensor([1.,2.]) for _ in range(73)];actual=[x+1 for x in reference]
        result=worker.compare_saved(reference,{'qdq':actual});self.assertEqual(len(result['qdq']['outputs']),73)
        self.assertAlmostEqual(result['qdq']['outputs'][0]['l2'],2**.5)
        with self.assertRaises(ValueError):worker.compare_saved(reference[:49],{'qdq':actual})

    def test_pin_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'x';p.write_bytes(b'first');r=worker.pin(p);p.write_bytes(b'other')
            with self.assertRaises(ValueError):worker.check(r)


if __name__=='__main__':unittest.main()
