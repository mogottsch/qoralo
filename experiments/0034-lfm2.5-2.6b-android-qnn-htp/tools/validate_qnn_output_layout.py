#!/usr/bin/env python3
"""Verify qnn-net-run raw output files against execution metadata tensors."""
import argparse,hashlib,json,math
from pathlib import Path
import numpy as np,yaml
SIZE={'QNN_DATATYPE_FLOAT_32':4,'QNN_DATATYPE_FLOAT_16':2,'QNN_DATATYPE_INT_32':4,'QNN_DATATYPE_INT_64':8}
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8<<20),b''):h.update(b)
 return h.hexdigest()
def file_name(n):return n.replace('.','_').replace('/','_')+'.raw'
ap=argparse.ArgumentParser();ap.add_argument('--output-dir',type=Path,required=True);ap.add_argument('--result',type=Path,required=True);a=ap.parse_args();meta=yaml.safe_load((a.output_dir/'execution_metadata.yaml').read_text());tensors=meta['graphs'][0]['output_tensors'];items=[]
for t in tensors:
 p=a.output_dir/'Result_0'/file_name(t['tensor_name']);expected=math.prod(t['dimensions'])*SIZE[t['datatype']];actual=p.stat().st_size if p.exists() else None;z={'name':t['tensor_name'],'data_type':t['datatype'],'dimensions':t['dimensions'],'expected_bytes':expected,'actual_bytes':actual,'exists':p.exists(),'size_equal':actual==expected}
 if p.exists():
  z['sha256']=sha(p)
  if t['datatype']=='QNN_DATATYPE_FLOAT_32':
   x=np.fromfile(p,np.float32);z.update({'finite':bool(np.isfinite(x).all()),'min':float(x.min()),'max':float(x.max())})
 items.append(z)
r={'schema_version':1,'classification':'post_cleanup_qnn_raw_output_layout_validation','inferences_completed':meta['inferences_completed'],'graph_name':meta['graphs'][0]['graph_name'],'tensor_count':len(items),'all_exist':all(x['exists'] for x in items),'all_sizes_equal_metadata':all(x['size_equal'] for x in items),'all_float_outputs_finite':all(x.get('finite',True) for x in items),'tensors':items,'claim_boundary':'Raw file type/shape/size/finiteness validation only; not numerical equivalence.'};a.result.write_text(json.dumps(r,indent=2,sort_keys=True)+'\n');print(json.dumps({k:r[k] for k in ('inferences_completed','tensor_count','all_exist','all_sizes_equal_metadata','all_float_outputs_finite')},indent=2))
