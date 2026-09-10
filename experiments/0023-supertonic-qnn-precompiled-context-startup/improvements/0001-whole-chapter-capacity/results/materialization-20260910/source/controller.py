#!/usr/bin/env python3
"""One explicitly released serial four-component derivative attempt; no retry.

The parent executes stdlib coordination only. Existing external supervisor bounds
worker calls; shared580s execution deadline leaves20s TERM grace within600s total.
No SDK/ORT/QNN/native model execution. Source ONNX bytes/embedded weights remain local.
"""
import hashlib
import json
import os
from pathlib import Path
import time
import types

TRACK=Path(__file__).resolve().parents[3]
REPO=TRACK.parents[3]
BASE=TRACK/'.local/materialization-20260910/attempt-01'
HELPER=TRACK/'tools/onnx_capacity.py'
TARGET=TRACK/'protocol/target.json'
SOURCE=REPO/'experiments/0007-mobile-podcast-preview-bakeoff/artifacts/supertonic-3/snapshot/onnx'
PYTHON=REPO/'experiments/0022-supertonic-canonical-v2-precompiled-qnn-context/.local/proof-venv/bin/python'
GUARD=REPO/'experiments/0032-qwen-3.5-2b-android-qnn-htp/tools/qwen_host_guard.py'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def save(path,value):
    with path.open('x') as f:json.dump(value,f,indent=2);f.write('\n')


def main():
    started=time.monotonic();BASE.mkdir(parents=True,exist_ok=False)
    target=json.loads(TARGET.read_text());helper_sha=sha(HELPER);target_sha=sha(TARGET)
    guard=types.ModuleType('retained_external_supervisor');guard.__file__=str(GUARD)
    exec(compile(GUARD.read_bytes(),str(GUARD),'exec'),guard.__dict__)
    outcomes=[]
    save(BASE/'scope.json',{'helper_sha256':helper_sha,'target_sha256':target_sha,'controller_sha256':sha(Path(__file__)),'guard_sha256':sha(GUARD),'max_components':4,'max_seconds_per_component':180,'execution_deadline_seconds':580,'total_including_grace_seconds':600,'retry':False,'model_forwards':0,'runtime_calls':0,'SDK_conversions':0,'context_compiles':0,'phone_calls':0})
    try:
        for component in ('duration','text','vector','vocoder'):
            remaining=580-(time.monotonic()-started)
            if remaining<=1:raise TimeoutError('overall execution budget consumed')
            if sha(HELPER)!=helper_sha or sha(TARGET)!=target_sha:raise ValueError('source/target changed during release')
            phase=BASE/component;phase.mkdir();(phase/'scratch').mkdir();(phase/'guard').mkdir()
            output=phase/'data';release=phase/'release.json'
            save(release,{'approved':True,'permission':'one_source_derivative_only_no_execution','component':component,'source_sha256':target['sources'][component]['sha256'],'target_sha256':target_sha,'helper_sha256':helper_sha,'output_dir':str(output)})
            command=['nice','-n','15','ionice','-c','2','-n','7','prlimit','--as=8589934592','--',str(PYTHON),str(HELPER),'derive','--component',component,'--source',str(SOURCE/target['sources'][component]['filename']),'--output-dir',str(output),'--release',str(release)]
            env=dict(os.environ,TMPDIR=str(phase/'scratch'),OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4',NUMEXPR_NUM_THREADS='4')
            save(phase/'command.json',{'argv':command,'TMPDIR':env['TMPDIR'],'math_threads':4,'address_space_limit_bytes':8589934592})
            result=guard.supervise(command,phase/'guard',min(180,remaining),env=env,grace=20)
            outcomes.append({'component':component,**result});print(json.dumps(outcomes[-1]),flush=True)
            if result['exit_code']!=0:raise RuntimeError('component failed; preserve partial files and STOP, no retry')
    finally:
        save(BASE/'controller-result.json',{'outcomes':outcomes,'elapsed_seconds':time.monotonic()-started,'complete':len(outcomes)==4 and all(r['exit_code']==0 for r in outcomes),'retry':False})


if __name__=='__main__':main()
