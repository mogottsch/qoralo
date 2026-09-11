from pathlib import Path
import sys
import types
import unittest
import torch
import torch.ao.quantization.fx._decomposed
from torchao.quantization.pt2e import PerChannelMinMaxObserver
from torchao.quantization.quant_primitives import quantize_affine

EXP=Path(__file__).resolve().parents[1];sys.path.insert(0,str(EXP/'tools'))
from weight_only_ablation import EPS,reconstruct_weight,quantize_model


class WeightAblationTests(unittest.TestCase):
    def test_per_channel_matches_framework_qdq(self):
        x=torch.linspace(-3,5,4*64).reshape(4,64);x[0].zero_()
        observer=PerChannelMinMaxObserver(dtype=torch.int8,qscheme=torch.per_channel_symmetric,ch_axis=0,quant_min=-7,quant_max=7,eps=EPS)
        observer(x);scales,zp=observer.calculate_qparams()
        q=torch.ops.quantized_decomposed.quantize_per_channel.default(x,scales,zp,0,-7,7,torch.int8)
        expected=torch.ops.quantized_decomposed.dequantize_per_channel.default(q,scales,zp,0,-7,7,torch.int8)
        self.assertTrue(torch.equal(expected,reconstruct_weight(x,'per_channel')))

    def test_lpbq_matches_framework_codes_and_source_scale_expansion(self):
        path=EXP.parents[1]/'artifacts/venv-executorch-1.2/lib/python3.11/site-packages/executorch/backends/qualcomm/quantizer/observers/per_block_param_observer.py'
        module=types.ModuleType('isolated_per_block_observer');exec(compile(path.read_bytes(),str(path),'exec'),module.__dict__)
        x=torch.linspace(-2,3,4*64).reshape(4,64);x[0,:32]*=.07
        observer=module.PerBlockParamObserver(dtype=torch.int8,block_size=(1,32),quant_min=-7,quant_max=7,eps=EPS)
        observer(x);scales,zp=observer.calculate_qparams()
        codes=quantize_affine(x,(1,32),scales,zp,torch.int8,-7,7)
        # Literal source algorithm, channel by channel, independently of worker vectorization.
        rows=[]
        for ch in range(x.shape[0]):
            candidates=scales[ch];base=candidates.reshape(1,-1).amax(dim=-1)/16
            q_scales=torch.round(candidates/base).clamp(1,16).to(torch.uint8)
            rows.append((codes[ch].reshape(-1,32).float()*(base*q_scales.float())[:,None]).flatten())
        self.assertTrue(torch.equal(torch.stack(rows),reconstruct_weight(x,'lpbq32')))

    def test_depthwise_keeps_per_channel(self):
        x=torch.arange(16,dtype=torch.float32).reshape(4,1,1,4)
        self.assertTrue(torch.equal(reconstruct_weight(x,'lpbq32'),reconstruct_weight(x,'per_channel')))

    def test_no_silent_padding(self):
        with self.assertRaises(ValueError):reconstruct_weight(torch.ones(3,31),'lpbq32')

    def test_scale_compression_not_requantization_and_not_universal_improvement(self):
        x=torch.full((1,64),.01);x[0,0]=7
        result=reconstruct_weight(x,'lpbq32')
        self.assertEqual(float(result[0,32]),7/16)
        self.assertGreater(float((result-x).square().sum()),float((reconstruct_weight(x,'per_channel')-x).square().sum()))

    def test_quantizes_only_linear_conv_not_embedding_or_norm(self):
        m=torch.nn.Module();m.embedding=torch.nn.Embedding(4,32);m.linear=torch.nn.Linear(32,4,bias=False);m.norm=torch.nn.LayerNorm(32)
        before={n:p.clone() for n,p in m.named_parameters()};records=quantize_model(m,'lpbq32')
        self.assertEqual([r['module'] for r in records],['linear'])
        for n,p in m.named_parameters():
            if n!='linear.weight':self.assertTrue(torch.equal(p,before[n]))


if __name__=='__main__':unittest.main()
