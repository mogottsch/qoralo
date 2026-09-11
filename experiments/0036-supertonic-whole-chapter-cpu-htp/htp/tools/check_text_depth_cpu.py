#!/usr/bin/env python3
"""Original versus depth-partitioned CPU text-stage calls, offline only.

Validation outputs stay private and MUST NOT be used as HTP synthesis inputs.
"""
import argparse
import gc
import json
import os
from pathlib import Path
import resource
import signal
import time
from materialize import sha
from split_text_depth import SOURCE_SHA


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--parts',type=Path,required=True);p.add_argument('--bundle',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--reuse-original-result',type=Path);a=p.parse_args()
    if '.local' not in a.output.parts:raise ValueError('private validation outputs required')
    if sha(a.source)!=SOURCE_SHA:raise ValueError('wrong original source')
    a.output.mkdir(parents=True,exist_ok=False)
    resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3));signal.alarm(180)
    for name in ('OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='4'
    os.environ['OPENBLAS_NUM_THREADS']='1'
    import numpy as np
    import onnxruntime as ort
    manifest=json.loads((a.bundle/'manifest.json').read_text())
    specs={'text_ids':('text_ids.i64','<i8',(1,3200)),'text_mask':('text_mask.f32','<f4',(1,1,3200)),'style_ttl':('style_ttl.f32','<f4',(1,50,256))}
    inputs={}
    for name,(filename,dtype,shape) in specs.items():
        if sha(a.bundle/filename)!=manifest['tensors'][filename]['sha256']:raise ValueError('input pin differs')
        inputs[name]=np.fromfile(a.bundle/filename,dtype=dtype).reshape(shape)
    calls=[]
    def run(path,feed):
        o=ort.SessionOptions();o.intra_op_num_threads=4;o.inter_op_num_threads=1;o.execution_mode=ort.ExecutionMode.ORT_SEQUENTIAL;o.graph_optimization_level=ort.GraphOptimizationLevel.ORT_ENABLE_ALL;o.enable_cpu_mem_arena=False;o.enable_mem_pattern=False
        start=time.monotonic();s=ort.InferenceSession(str(path),sess_options=o,providers=['CPUExecutionProvider']);ready=time.monotonic()
        actual={v.name:feed[v.name] for v in s.get_inputs()}
        outputs=s.run(None,actual);end=time.monotonic()
        result=dict(zip((v.name for v in s.get_outputs()),outputs))
        if s.get_providers()!=['CPUExecutionProvider']:raise ValueError('not a CPU-only validation session')
        calls.append({'graph_sha256':sha(path),'setup_seconds':ready-start,'Run_seconds':end-ready,'Run_calls':1,'outputs':{k:list(v.shape) for k,v in result.items()}})
        del s;gc.collect();return result
    if a.reuse_original_result:
        previous=json.loads(a.reuse_original_result.read_text())
        old_output=a.reuse_original_result.parent/'original-text-CPU-validation-only.f32'
        if previous['status']!='passed' or previous['original_graph_sha256']!=SOURCE_SHA or previous['reference_sha256']!=manifest['reference_sha256'] or previous['runtime']!=ort.__version__ or sha(old_output)!=previous['original_output_sha256']:raise ValueError('prior source-validation baseline mismatch')
        original=np.fromfile(old_output,dtype='<f4').reshape(1,256,3200)
    else:
        original=run(a.source,inputs)['text_emb']
    proof=json.loads((a.parts/'structural-proof.json').read_text())
    state=dict(inputs)
    for label,record in proof['parts'].items():
        path=a.parts/label/(label+'.onnx')
        if sha(path)!=record['derivative']['sha256']:raise ValueError('part source binding differs')
        values=run(path,state)
        if any(v.shape!=(1,256,3200) for v in values.values()):raise ValueError('full-sequence cut ABI differs')
        state.update(values)
    composed=state['text_emb']
    for v in (original,composed):
        if v.shape!=(1,256,3200) or not np.isfinite(v).all():raise ValueError('invalid output')
    original.tofile(a.output/'original-text-CPU-validation-only.f32');composed.tofile(a.output/'composed-text-CPU-validation-only.f32')
    delta=original.astype(np.float64)-composed.astype(np.float64)
    max_abs=float(np.max(np.abs(delta)));rmse=float(np.sqrt(np.mean(delta*delta)))
    passed=bool(np.allclose(original,composed,atol=1e-5,rtol=1e-5))
    result={'status':'passed' if passed else 'failed','test_type':'CPU source-equivalence only, never HTP inputs','reference_sha256':manifest['reference_sha256'],'runtime':ort.__version__,'providers':['CPUExecutionProvider'],'threads':4,'original_graph_sha256':sha(a.source),'calls':calls,'total_Run_calls':len(calls),'original_baseline_reused':bool(a.reuse_original_result),'max_absolute_error':max_abs,'rmse':rmse,'bitwise_equal':bool(np.array_equal(original,composed)),'tolerance':{'atol':1e-5,'rtol':1e-5},'original_output_sha256':sha(a.output/'original-text-CPU-validation-only.f32'),'composed_output_sha256':sha(a.output/'composed-text-CPU-validation-only.f32'),'all_outputs_private_not_used_for_HTP':True,'maxrss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
    (a.output/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
    if not passed:raise RuntimeError('CPU depth split differs')


if __name__=='__main__':main()
