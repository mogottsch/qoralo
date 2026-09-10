#!/usr/bin/env python3
"""Released CPU-only duration pair; one unchanged dynamic model/session, two calls."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import sys
import time

MODEL_SHA='c3eb91414d5ff8a7a239b7fe9e34e7e2bf8a8140d8375ffb14718b1c639325db'
LIMIT=4294967296


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()


def write(path,value):
    with Path(path).open('x') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')


def verify(record):
    p=Path(record['path'])
    if not p.is_file() or p.stat().st_size!=record['bytes'] or sha(p)!=record['sha256']:raise ValueError('pinned file changed: '+str(p))


def authorize(request_path,release_path):
    request=json.loads(Path(request_path).read_text());release=json.loads(Path(release_path).read_text())
    expected={'approved':True,'permission':'one_CPU_duration_session_two_padding_forwards','request_sha256':sha(request_path),'worker_sha256':sha(__file__),'output_dir':request['output_dir']}
    if release!=expected or request['worker_sha256']!=sha(__file__):raise ValueError('exact separate release mismatch')
    if request['model']['sha256']!=MODEL_SHA or request['providers']!=['CPUExecutionProvider'] or request['case_order']!=[1333,2048] or request['constructor_calls_allowed']!=1 or request['Run_calls_allowed']!=2:raise ValueError('scope mismatch')
    if request['bounds']!={'worker_seconds':100,'grace_seconds':20,'total_seconds':120,'address_space_bytes':LIMIT,'cpus':4,'intra_threads':4,'inter_threads':1,'retries':0}:raise ValueError('bounds mismatch')
    return request


def validate_arrays(np,arrays):
    if set(arrays)!=set(['text_ids','text_mask','style_dp']):raise ValueError('input set differs')
    for name,dtype,shape in [('text_ids','int64',(1,2048)),('text_mask','float32',(1,1,2048)),('style_dp','float32',(1,8,16))]:
        if arrays[name].dtype!=np.dtype(dtype) or arrays[name].shape!=shape:raise ValueError('array metadata differs: '+name)
    if not np.all(arrays['text_ids']>=0) or not np.all(arrays['text_ids'][:,1333:]==0) or not np.all(arrays['text_mask'][:,:,:1333]==1) or not np.all(arrays['text_mask'][:,:,1333:]==0) or not np.isfinite(arrays['style_dp']).all():raise ValueError('prepared prefix/mask/style invalid')


def run_pair(ort,np,request,arrays,out,result):
    validate_arrays(np,arrays)
    options=ort.SessionOptions();options.intra_op_num_threads=4;options.inter_op_num_threads=1;options.execution_mode=ort.ExecutionMode.ORT_SEQUENTIAL;options.graph_optimization_level=ort.GraphOptimizationLevel.ORT_ENABLE_ALL;options.enable_profiling=False
    result['python_InferenceSession_calls']=1;start=time.monotonic()
    session=ort.InferenceSession(request['model']['path'],sess_options=options,providers=['CPUExecutionProvider'],enable_fallback=False)
    result['session_setup_seconds']=time.monotonic()-start;result['actual_providers']=session.get_providers()
    if result['actual_providers']!=['CPUExecutionProvider']:raise ValueError('CPU-only provider requirement')
    result['actual_inputs']=[{'name':v.name,'type':v.type,'shape':v.shape} for v in session.get_inputs()]
    result['actual_outputs']=[{'name':v.name,'type':v.type,'shape':v.shape} for v in session.get_outputs()]
    for length in request['case_order']:
        label='active1333' if length==1333 else 'padded2048'
        feed={'text_ids':arrays['text_ids'][:,:length].copy(),'text_mask':arrays['text_mask'][:,:,:length].copy(),'style_dp':arrays['style_dp'].copy()}
        record={'label':label,'length':length,'input_raw_sha256':{k:sha_bytes(v.tobytes()) for k,v in feed.items()},'Run_calls_attempted':1}
        result['Run_calls_attempted']+=1;start=time.monotonic();values=session.run(['duration'],feed);record['Run_seconds']=time.monotonic()-start
        # Preserve returned bytes before scalar/type/finiteness classification.
        record['outputs']=[]
        for i,value in enumerate(values):
            file=out/(label+'-output-'+str(i)+'.npy');np.save(str(file),value,allow_pickle=False)
            record['outputs'].append({'path':str(file),'shape':list(value.shape),'dtype':str(value.dtype),'bytes':file.stat().st_size,'sha256':sha(file)})
        result['cases'].append(record);write(out/(label+'-receipt.json'),record)
        if len(values)!=1 or values[0].dtype!=np.float32 or values[0].shape!=(1,):raise ValueError('duration output ABI differs')
        scalar=float(values[0][0]);record['finite_positive']=bool(np.isfinite(scalar) and scalar>0)
        record['duration_seconds']=scalar if np.isfinite(scalar) else None
        if record['finite_positive']:record['source_formula_FP32_wave_frames']=int(np.floor(np.float32(values[0][0])*np.float32(44100)))
    del session
    if not all(c['finite_positive'] for c in result['cases']):raise ValueError('nonfinite/nonpositive duration')
    a,b=[v['duration_seconds'] for v in result['cases']]
    result['comparison']={'padded_minus_active_seconds':b-a,'padded_over_active':b/a,'observed_WAV_seconds':1314042/44100,'CPU_minus_frame_quotient_seconds':{'active1333':a-1314042/44100,'padded2048':b-1314042/44100},'native_DP_scalar':None,'native_DP_scalar_reason':'Not captured. WAV quotient/ideal real-arithmetic interval is approximate; native FP32 multiply+floor rounds.','ideal_real_arithmetic_interval_only':[1314042/44100,1314043/44100]}


def sha_bytes(data):return hashlib.sha256(data).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--request',type=Path,required=True);parser.add_argument('--release',type=Path);parser.add_argument('--execute',action='store_true');a=parser.parse_args()
    if not a.execute:print(json.dumps({'status':'PLAN_ONLY_NO_RUNTIME_IMPORT','request_sha256':sha(a.request),'worker_sha256':sha(__file__)}));return
    if a.release is None:parser.error('exact reviewed release required')
    request=authorize(a.request,a.release);out=Path(request['output_dir']);out.mkdir(parents=True,exist_ok=False)
    result={'status':'started','python_InferenceSession_calls':0,'Run_calls_attempted':0,'cases':[],'QNN_calls':0,'phone_calls':0,'graph_mutations':0,'request_sha256':sha(a.request)};start=time.monotonic()
    try:
        if resource.getrlimit(resource.RLIMIT_AS)[0]!=LIMIT or set(os.sched_getaffinity(0))!=set(request['cpu_affinity']) or len(request['cpu_affinity'])>4:raise ValueError('worker bounds not applied')
        for record in [request['model'],request['input_pack'],*request['runtime_pins']]:verify(record)
        import numpy as np
        import onnxruntime as ort
        if ort.__version__!='1.23.2' or str(Path(ort.__file__).resolve())!=request['ort_package_file'] or np.__version__!='1.26.4':raise ValueError('selected stock CPU runtime differs')
        result['runtime']={'ORT':ort.__version__,'NumPy':np.__version__,'Python':sys.version,'ort_package':ort.__file__,'cpu_affinity':sorted(os.sched_getaffinity(0)),'RLIMIT_AS':list(resource.getrlimit(resource.RLIMIT_AS)),'threads':{'intra':4,'inter':1}}
        with np.load(request['input_pack']['path'],allow_pickle=False) as pack:arrays={name:pack[name].copy() for name in pack.files}
        run_pair(ort,np,request,arrays,out,result)
        for record in [request['model'],request['input_pack'],*request['runtime_pins']]:verify(record)
        maps=Path('/proc/self/maps').read_text();qnn=[line for line in maps.splitlines() if 'libQnn' in line or 'onnxruntime_providers_qnn' in line]
        result['QNN_library_mappings']=qnn
        if qnn:raise ValueError('unexpected QNN library mapping')
        result.update(status='two_CPU_duration_outputs_retained',postpins='unchanged')
    except BaseException as error:result.update(status='error',error={'type':type(error).__name__,'message':str(error)});raise
    finally:
        result['elapsed_seconds']=time.monotonic()-start;result['process_ru_maxrss_kib']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        write(out/'result.json',result)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
