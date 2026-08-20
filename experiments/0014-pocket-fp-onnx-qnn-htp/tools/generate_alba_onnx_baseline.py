#!/usr/bin/env python3
"""Generate host CPU candidates from the controlled FP ONNX bundle and Alba state."""
from __future__ import annotations
import argparse,hashlib,json,subprocess,sys,time,wave
from pathlib import Path
import numpy as np
TEXT="Pocket TTS runs entirely on this Android phone using the original floating point model."
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write_wav(path,x,sr=24000):
 x=np.asarray(x,np.float32).reshape(-1);assert x.size and np.isfinite(x).all();pcm=np.clip(np.rint(x*32767),-32768,32767).astype('<i2')
 with wave.open(str(path),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(sr);w.writeframes(pcm.tobytes())
 return {'path':str(path),'sha256':sha(path),'samples':x.size,'seconds':x.size/sr,'peak_float':float(np.max(np.abs(x))),'rms_float':float(np.sqrt(np.mean(x*x))),'clipped_before_conversion':int(np.count_nonzero(np.abs(x)>1))}
def main():
 p=argparse.ArgumentParser();p.add_argument('--temperatures',type=float,nargs='+',default=[.3,.7]);p.add_argument('--seed',type=int,default=0);p.add_argument('--out-dir',type=Path);a=p.parse_args()
 root=Path(subprocess.check_output(['git','rev-parse','--show-toplevel'],text=True).strip());e12=root/'experiments/0012-pocket-onnx-vs-executorch-android';e14=root/'experiments/0014-pocket-fp-onnx-qnn-htp';bundle=e12/'.local/onnx-controlled';runtime=e12/'.local/pocket_tts_onnx.py';alba=e12/'.local/source-assets/languages/english/embeddings/alba.safetensors';out=a.out_dir or e14/'work/quality-recovery/onnx-alba';out.mkdir(parents=True,exist_ok=True)
 assert sha(alba)=='e4a323e8e771f14fd669428d83e7af6d83b4d6d0f0e282c30122f04824f17b1c';sys.path.insert(0,str(runtime.parent));from pocket_tts_onnx import PocketTTSOnnx
 rows=[]
 for temp in a.temperatures:
  np.random.seed(a.seed);t0=time.perf_counter();m=PocketTTSOnnx(models_dir=str(bundle),language='x',precision='fp32',device='cpu',temperature=temp,lsd_steps=1);load=time.perf_counter()-t0;np.random.seed(a.seed);g=time.perf_counter();audio=m.generate(TEXT,alba);gen=time.perf_counter()-g;tag=str(temp).replace('.','p');row=write_wav(out/f'controlled-fp-onnx-alba-temp{tag}-seed{a.seed}.wav',audio);row.update({'temperature':temp,'seed':a.seed,'load_seconds':load,'generation_seconds':gen,'provider':m.providers});rows.append(row)
 report={'schema_version':1,'status':'awaiting_human_listening_verdict','route':'controlled unquantized FP ONNX on host CPU with pinned fixed Alba state','source_graphs':{p.name:sha(p) for p in sorted(bundle.glob('*.onnx'))},'contract':{'text':TEXT,'text_sha256':hashlib.sha256(TEXT.encode()).hexdigest(),'voice':'official pinned Alba state','voice_state_sha256':sha(alba),'seed':a.seed,'temperatures':a.temperatures,'lsd_decode_steps':1,'eos_threshold':-4.0,'frames_after_eos':'model-derived'},'outputs':rows,'claim_boundary':'Numerical fidelity is documented separately; this route is not quality-valid until Moritz listens.'};(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
