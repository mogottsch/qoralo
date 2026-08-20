#!/usr/bin/env python3
"""Pack the pinned Alba flow state and deterministic noise fixtures for Android."""
from __future__ import annotations
import hashlib,json,subprocess
from pathlib import Path
import numpy as np
from safetensors import safe_open

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
 root=Path(subprocess.check_output(['git','rev-parse','--show-toplevel'],text=True).strip());e12=root/'experiments/0012-pocket-onnx-vs-executorch-android';e14=root/'experiments/0014-pocket-fp-onnx-qnn-htp';src=e12/'.local/source-assets/languages/english/embeddings/alba.safetensors';out=e14/'work/quality-recovery/alba-assets';out.mkdir(parents=True,exist_ok=True)
 assert sha(src)=='e4a323e8e771f14fd669428d83e7af6d83b4d6d0f0e282c30122f04824f17b1c';parts=[];records=[]
 with safe_open(str(src),framework='np') as f:
  for layer in range(6):
   key=f'transformer.layers.{layer}.self_attn/cache';off=f'transformer.layers.{layer}.self_attn/offset';x=np.ascontiguousarray(f.get_tensor(key),dtype='<f4');o=np.asarray(f.get_tensor(off),dtype=np.int64);assert x.shape==(2,1,126,16,64) and o.tolist()==[126];parts.append(x);records.append({'layer':layer,'source_key':key,'shape':list(x.shape),'dtype':'float32','float32_sha256':hashlib.sha256(x.tobytes()).hexdigest(),'offset':126})
 packed=np.concatenate([x.reshape(-1) for x in parts]).astype('<f4');cache=out/'alba-flow-cache-v1.f32';cache.write_bytes(packed.tobytes());assert cache.stat().st_size==6*2*126*16*64*4
 noise=[]
 for temp in (.3,.7):
  rng=np.random.RandomState(0);x=rng.normal(0,np.sqrt(temp),(134,32)).astype('<f4');p=out/f'numpy-randomstate-seed0-temp{str(temp).replace(".","p")}-134x32.f32';p.write_bytes(x.tobytes());noise.append({'temperature':temp,'seed':0,'algorithm':'NumPy RandomState (MT19937) normal','shape':[134,32],'path':str(p),'sha256':sha(p)})
 report={'schema_version':1,'source':{'path':str(src),'sha256':sha(src),'meaning':'official pinned fixed Alba FlowLM state'},'cache_pack':{'format':'six layer caches concatenated in layer order; each little-endian float32 [2,1,126,16,64]','path':str(cache),'bytes':cache.stat().st_size,'sha256':sha(cache),'layers':records},'noise_fixtures':noise,'contract':{'tokenizer_ids':[1456,603,597,602,854,640,791,261,260,1332,323,288,285,287,489,594,1355,1049,265,311,2081,3697,273,519,1836,263],'max_frames':134,'eos_threshold':-4.0,'frames_after_eos':3,'lsd_steps':1}};(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
