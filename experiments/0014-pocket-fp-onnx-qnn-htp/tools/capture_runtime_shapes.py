#!/usr/bin/env python3
"""Capture the exact ONNX call-shape variants used by the frozen Pocket transcript."""
import argparse,json,sys
from collections import Counter
from pathlib import Path
import numpy as np

p=argparse.ArgumentParser();p.add_argument('--runtime',type=Path,required=True);p.add_argument('--bundle',type=Path,required=True);p.add_argument('--voice',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
sys.path.insert(0,str(a.runtime.parent));from pocket_tts_onnx import PocketTTSOnnx
text='Pocket TTS runs entirely on this Android phone using the original floating point model.'
np.random.seed(0);tts=PocketTTSOnnx(models_dir=str(a.bundle),language='x',precision='fp32',device='cpu',temperature=.3,lsd_steps=1)
records={}
class Proxy:
 def __init__(self,name,inner):self.name=name;self.inner=inner
 def run(self,outputs,feeds):
  result=self.inner.run(outputs,feeds)
  sig=json.dumps({'inputs':{k:{'shape':list(v.shape),'dtype':str(v.dtype)} for k,v in feeds.items()},'outputs':[{'shape':list(v.shape),'dtype':str(v.dtype)} for v in result]},sort_keys=True)
  records.setdefault(self.name,Counter())[sig]+=1
  return result
for name in ('text_conditioner','flow_lm_main','flow_lm_flow','mimi_encoder','mimi_decoder'):
 setattr(tts,name,Proxy(name,getattr(tts,name)))
np.random.seed(0);audio=tts.generate(text,a.voice)
out={'schema_version':1,'text':text,'audio_samples':int(np.asarray(audio).size),'components':{}}
for name,counter in records.items():out['components'][name]=[dict(json.loads(sig),calls=count) for sig,count in counter.items()]
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
