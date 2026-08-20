#!/usr/bin/env python3
import argparse,hashlib,json,wave
from pathlib import Path
import numpy as np
p=argparse.ArgumentParser();p.add_argument('--cpu',type=Path,required=True);p.add_argument('--htp',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
def read(p):
 w=wave.open(str(p),'rb');meta={'channels':w.getnchannels(),'sample_rate_hz':w.getframerate(),'sample_width_bytes':w.getsampwidth(),'frames':w.getnframes(),'duration_seconds':w.getnframes()/w.getframerate()};assert meta['channels']==1 and meta['sample_width_bytes']==2;v=np.frombuffer(w.readframes(w.getnframes()),dtype='<i2').astype(np.float64)/32768.;w.close();return meta,v
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
cm,c=read(a.cpu);hm,h=read(a.htp);assert cm['sample_rate_hz']==hm['sample_rate_hz'];n=min(c.size,h.size);x=c[:n];y=h[:n];d=x-y;cos=float(np.dot(x,y)/(np.linalg.norm(x)*np.linalg.norm(y))) if np.any(x) and np.any(y) else None
out={'schema_version':1,'claim_boundary':'Descriptive sample-level raw time-domain comparison with no numerical acceptance threshold. Numerical divergence is not a listening rejection; Moritz listening is the quality gate.','cpu':{**cm,'sha256':sha(a.cpu),'path':str(a.cpu.resolve())},'htp':{**hm,'sha256':sha(a.htp),'path':str(a.htp.resolve())},'overlap':{'samples':n,'mae':float(np.mean(np.abs(d))),'rmse':float(np.sqrt(np.mean(d*d))),'cosine':cos,'cpu_rms':float(np.sqrt(np.mean(x*x))),'htp_rms':float(np.sqrt(np.mean(y*y))),'cpu_peak':float(np.max(np.abs(x))),'htp_peak':float(np.max(np.abs(y)))},'duration_difference_seconds':hm['duration_seconds']-cm['duration_seconds']}
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
