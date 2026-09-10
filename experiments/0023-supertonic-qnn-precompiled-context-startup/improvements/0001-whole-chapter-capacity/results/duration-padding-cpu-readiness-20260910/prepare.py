#!/usr/bin/env python3
"""Prepare shared inputs/request from committed receipts; NumPy only, no model load."""
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
REPO=ROOT.parents[3]
EVIDENCE=Path(__file__).resolve().parent


def record(path):return {'path':str(path.absolute()),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def put(path,value):
    with path.open('x') as f:json.dump(value,f,indent=2);f.write('\n')


def main():
    saved=REPO/'podcast-app/evidence/tts-profile-off-result/tts-long-profile-off-20260910t205719z/device';pack=REPO/'podcast-app/.local/model-packs/supertonic-3-t2048-l2048-parity/current'
    sources={name:record(saved/name) for name in ['actual-request.txt','actual-normalized.txt','tokenization-reconstruction.json']}
    expected={'actual-request.txt':'f25655b54ad4e8d5e782dedf069867d6c201f1ea48327724527356d0f35aea37','actual-normalized.txt':'7add3140f7c8d871d0291e30ac1ca79546ad5fec9792ef78428e7eda9484c8b9','tokenization-reconstruction.json':'9b1585aec281f82eab74733588c79bb740e5a26fdc17f6da4aa8487be1c0b820'}
    assert all(sources[k]['sha256']==v for k,v in expected.items())
    voice_path=pack/'assets/voice.bin';index_path=pack/'assets/unicode-indexer.i32';voice=voice_path.read_bytes();index_bytes=index_path.read_bytes()
    assert hashlib.sha256(voice).hexdigest()=='b6d15b9e1fbb4a8efca004427bd05963a2b01ce11b780f3843956d82605d076a';assert hashlib.sha256(index_bytes).hexdigest()=='8402ca48e5189a8950138580b0fff64db6f072f24ac07cd54ba8b2fbb9883b30'
    assert struct.unpack('<6q',voice[:48])==(1,50,256,1,8,16) and len(voice)==51760
    normalized=(saved/'actual-normalized.txt').read_text();wrapped='<en>'+normalized.rstrip()+'</en>';assert len(normalized)==1324 and len(wrapped)==1333
    indexer=np.frombuffer(index_bytes,dtype='<i4');ids=np.zeros((1,2048),dtype=np.int64);ids[0,:1333]=[int(indexer[ord(c)]) for c in wrapped];mask=np.zeros((1,1,2048),dtype=np.float32);mask[0,0,:1333]=1
    style=np.frombuffer(voice[48+51200:],dtype='<f4').copy().reshape(1,8,16)
    reconstruction=json.loads((saved/'tokenization-reconstruction.json').read_text())
    assert wrapped==reconstruction['wrapped'];assert np.array_equal(ids,np.array(reconstruction['ids'],dtype=np.int64).reshape(1,2048));assert np.array_equal(mask,np.array(reconstruction['mask'],dtype=np.float32).reshape(1,1,2048));assert np.isfinite(style).all()
    inputs=ROOT/'.local/duration-padding-cpu-20260910/prepared-inputs';inputs.mkdir(parents=True,exist_ok=False);np.savez(inputs/'common-inputs.npz',text_ids=ids,text_mask=mask,style_dp=style)
    (inputs/'PRESERVE.md').write_text('Preserve exact shared input NPZ bytes. LOCAL-ONLY due to M1 style data. Derived from exact committed text/indexer/voice bindings, NOT captured native buffers. No model forward occurred in preparation.\n')
    input_binding={'sources':sources,'voice':record(voice_path),'indexer':record(index_path),'input_pack':record(inputs/'common-inputs.npz'),'arrays':{k:{'dtype':str(v.dtype),'shape':list(v.shape),'logical_bytes':v.nbytes,'raw_sha256':hashlib.sha256(v.tobytes()).hexdigest()} for k,v in [('text_ids',ids),('text_mask',mask),('style_dp',style)]},'active_length':1333,'padding':715,'style_extraction':{'offset_bytes':51248,'bytes':512,'shape':[1,8,16]},'reconstruction_matches':True,'native_buffer_capture':False,'scope':'shared active1333prefix andexactstyle; case2048adds only715zeroIDs+zeroMask; no model calls'}
    put(EVIDENCE/'input-binding.json',input_binding)
    python=REPO/'experiments/0022-supertonic-canonical-v2-precompiled-qnn-context/.local/proof-venv/bin/python';site=python.parent.parent/'lib/python3.10/site-packages';ort=site/'onnxruntime'
    runtime_paths=[python,ort/'__init__.py',*(ort/'capi').glob('*.py'),*(ort/'capi').glob('*.so*'),site/'onnxruntime-1.23.2.dist-info/METADATA',site/'numpy/__init__.py',site/'numpy-1.26.4.dist-info/METADATA',* (site/'numpy/core').glob('_multiarray_umath*.so'),*(site/'numpy.libs').glob('*.so*')]
    runtime=[record(path) for path in sorted(set(runtime_paths))]
    model=record(REPO/'experiments/0007-mobile-podcast-preview-bakeoff/artifacts/supertonic-3/snapshot/onnx/duration_predictor.onnx');assert model['sha256']=='c3eb91414d5ff8a7a239b7fe9e34e7e2bf8a8140d8375ffb14718b1c639325db'
    phase=ROOT/'.local/duration-padding-cpu-20260910/attempt-01';approval=ROOT/'.local/approvals/duration-padding-cpu-pair.json';assert not phase.exists() and not approval.exists()
    request={'status':'NOT_APPROVED_NO_MODEL_SESSION','model':model,'input_pack':input_binding['input_pack'],'input_binding_sha256':record(EVIDENCE/'input-binding.json')['sha256'],'runtime_pins':runtime,'runtime_pin_scope':'Selected existing CPU ORT/NumPy/Python files inclbundledBLAS; not a complete transitive OS dependency inventory. CPUORT1.23.2 differs from phoneORT1.27.1/QNN.','python':str(python),'ort_package_file':str((ort/'__init__.py').resolve()),'providers':['CPUExecutionProvider'],'constructor_calls_allowed':1,'Run_calls_allowed':2,'case_order':[1333,2048],'cpu_affinity':sorted(os.sched_getaffinity(0))[:4],'bounds':{'worker_seconds':100,'grace_seconds':20,'total_seconds':120,'address_space_bytes':4294967296,'cpus':4,'intra_threads':4,'inter_threads':1,'retries':0},'phase_dir':str(phase),'output_dir':str(phase/'data'),'approval_path':str(approval),'worker_sha256':record(ROOT/'tools/compare_duration_padding_cpu.py')['sha256'],'launcher_sha256':record(ROOT/'tools/run_duration_padding_cpu.py')['sha256'],'guard_sha256':record(REPO/'experiments/0032-qwen-3.5-2b-android-qnn-htp/tools/qwen_host_guard.py')['sha256'],'phone_WAV':{'frames':1314042,'sample_rate':44100,'sha256':'bb61a552d5a631d05aee7aaa79695946f8a53aa01ebd4d82a9060bab95714d98','native_scalar':None,'limit':'Frame quotient exact audio duration; predictor scalar not captured and FP32 multiply+floor rounds.'},'model_graph_changes':False,'QNN_phone_other_models_allowed':False}
    put(ROOT/'protocol/duration-padding-cpu.request.NOT_APPROVED.json',request)
    request_hash=record(ROOT/'protocol/duration-padding-cpu.request.NOT_APPROVED.json')['sha256']
    put(ROOT/'protocol/duration-padding-cpu.release.NOT_APPROVED.json',{'approved':False,'permission':'one_CPU_duration_session_two_padding_forwards','request_sha256':request_hash,'worker_sha256':request['worker_sha256'],'output_dir':request['output_dir']})
    print(json.dumps({'request_sha256':request_hash,'worker_sha256':request['worker_sha256'],'launcher_sha256':request['launcher_sha256'],'input_binding_sha256':request['input_binding_sha256'],'input_pack':request['input_pack'],'runtime_files':len(runtime),'ORT':'1.23.2','NumPy':np.__version__,'CPU_affinity':request['cpu_affinity'],'model_calls':0},indent=2))


if __name__=='__main__':main()
