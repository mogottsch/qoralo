#!/usr/bin/env python3
"""Calibrate QDQ INT16 FlowLM derivatives on the exact Pocket fixtures.

This is an accuracy experiment motivated by HTP's mandatory FP16 execution for
unquantized FP32 graphs. It preserves ONNX float graph I/O while quantizing
eligible neural operators to asymmetric UINT16 activations and symmetric INT16
weights using real recurrent states from the matched prompt.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import numpy as np,onnxruntime as ort
from onnxruntime.quantization import CalibrationDataReader,QuantFormat,QuantType,quantize_static
class Reader(CalibrationDataReader):
 def __init__(self,items):self.items=iter(items)
 def get_next(self):return next(self.items,None)
def S(p):
 o=ort.SessionOptions();o.intra_op_num_threads=1;o.inter_op_num_threads=1;o.graph_optimization_level=ort.GraphOptimizationLevel.ORT_ENABLE_ALL;return ort.InferenceSession(str(p),o,providers=['CPUExecutionProvider'])
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,required=True);p.add_argument('--static',type=Path,required=True);p.add_argument('--flow',type=Path,required=True);p.add_argument('--voice',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
 import wave,sentencepiece as spm
 with wave.open(str(a.voice),'rb') as w:audio=np.frombuffer(w.readframes(w.getnframes()),dtype='<i2').astype(np.float32).reshape(1,1,-1)/32768
 enc=S(a.bundle/'mimi_encoder.onnx');voice0=enc.run(None,{'audio':audio})[0];bos=np.load(a.bundle/'bos_before_voice.npy').astype(np.float32);voice=np.concatenate((bos,voice0),1)
 tok=spm.SentencePieceProcessor();tok.Load(str(a.bundle/'tokenizer.model'));ids=np.asarray(tok.Encode('Pocket TTS runs entirely on this Android phone using the original floating point model.'),np.int64).reshape(1,-1);tc=S(a.bundle/'text_conditioner.onnx');text=tc.run(None,{'token_ids':ids})[0]
 paths={'voice126':a.flow/'flow_lm_prefill_voice126.onnx','text26':a.flow/'flow_lm_prefill_text26.onnx','ar_bos1':a.flow/'flow_lm_ar_bos1.onnx','ar_latent1':a.flow/'flow_lm_ar_latent1.onnx','flow1':a.static/'flow_lm_flow-flow1.onnx'};sessions={k:S(v) for k,v in paths.items()};cn=[z for i in range(6) for z in (f'k_cache_{i}',f'v_cache_{i}')];cache=[np.zeros((1,16,256,64),np.float32) for _ in range(12)];mask=np.full((1,1,1,256),-10000,np.float32);feeds={k:[] for k in paths};pos=0
 def call(k,lead):
  nonlocal cache,mask,pos
  n=lead.shape[1] if lead is not None else 1;f={'positions':np.arange(pos,pos+n,dtype=np.int64),'valid_mask':mask.copy(),**{x:y.copy() for x,y in zip(cn,cache)}}
  if k.startswith('voice') or k.startswith('text'):f['embeddings']=lead.copy()
  elif k=='ar_latent1':f['sequence']=lead.copy()
  feeds[k].append(f);r=sessions[k].run(None,f);off=0 if k in ('voice126','text26') else 2;cache=[x.copy() for x in r[off:off+12]];mask=r[off+12].copy();pos+=n;return r
 call('voice126',voice);call('text26',text);rng=np.random.RandomState(0);cur=None
 for step in range(100):
  k='ar_bos1' if step==0 else 'ar_latent1';r=call(k,cur);noise=rng.normal(0,np.sqrt(.3),(1,32)).astype(np.float32);f={'c':r[0].copy(),'s':np.zeros((1,1),np.float32),'t':np.ones((1,1),np.float32),'x':noise.copy()};feeds['flow1'].append(f);cur=(noise+sessions['flow1'].run(None,f)[0]).reshape(1,1,32)
 # Keep representative recurrent samples while avoiding excessive calibration time.
 selected={'voice126':feeds['voice126'],'text26':feeds['text26'],'ar_bos1':feeds['ar_bos1'],'ar_latent1':[feeds['ar_latent1'][i] for i in [0,1,2,4,9,19,39,59,79,98]],'flow1':[feeds['flow1'][i] for i in [0,1,2,5,10,20,40,60,80,99]]}
 report={'schema_version':1,'derivative':'QDQ QUInt16 activation + QInt16 weight','reason':'HTP maps unquantized FP32 graphs to FP16; calibrated INT16 is evaluated as a higher-resolution fixed-point alternative','calibration':{'voice_sha256':sha(a.voice),'text_sha256':hashlib.sha256('Pocket TTS runs entirely on this Android phone using the original floating point model.'.encode()).hexdigest(),'seed':0,'temperature':.3},'graphs':[]}
 for k,src in paths.items():
  dst=a.output/(src.stem+'-int16.onnx');quantize_static(str(src),str(dst),Reader(selected[k]),quant_format=QuantFormat.QDQ,op_types_to_quantize=['MatMul','Gemm','LayerNormalization'],per_channel=False,activation_type=QuantType.QUInt16,weight_type=QuantType.QInt16,calibrate_method=__import__('onnxruntime.quantization',fromlist=['CalibrationMethod']).CalibrationMethod.MinMax,calibration_providers=['CPUExecutionProvider'],extra_options={'ActivationSymmetric':False,'WeightSymmetric':True,'DedicatedQDQPair':True,'ForceQuantizeNoInputCheck':True})
  report['graphs'].append({'variant':k,'source':str(src),'source_sha256':sha(src),'output':str(dst),'output_sha256':sha(dst),'bytes':dst.stat().st_size,'calibration_samples':len(selected[k])})
 (a.output/'quantization-report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
