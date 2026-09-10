#!/usr/bin/env python3
"""Exact-release CPU pair launcher: fresh owned scratch,4GiB/four CPUs/100s+20s<=120s."""
import argparse
import json
import os
from pathlib import Path
import types
import compare_duration_padding_cpu as worker

ROOT=Path(__file__).resolve().parents[1]
GUARD=ROOT.parents[3]/'experiments/0032-qwen-3.5-2b-android-qnn-htp/tools/qwen_host_guard.py'


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--request',type=Path,required=True);p.add_argument('--release',type=Path);p.add_argument('--execute',action='store_true');a=p.parse_args();request=json.loads(a.request.read_text())
    phase=Path(request['phase_dir']).resolve();scratch=phase/'scratch'
    command=['nice','-n','15','ionice','-c','2','-n','7','prlimit','--as=4294967296','--','taskset','--cpu-list',','.join(str(v) for v in request['cpu_affinity']),request['python'],str(ROOT/'tools/compare_duration_padding_cpu.py'),'--request',str(a.request.resolve()),'--release',str(a.release or Path(request['approval_path'])),'--execute']
    if not a.execute:print(json.dumps({'status':'PLAN_ONLY_NO_RUNTIME_OR_SUBPROCESS','request_sha256':worker.sha(a.request),'argv':command},indent=2));return
    if a.release is None:p.error('explicit separate release required')
    worker.authorize(a.request,a.release)
    if worker.sha(__file__)!=request['launcher_sha256'] or worker.sha(GUARD)!=request['guard_sha256']:raise ValueError('launcher/guard drift')
    if phase.exists() or not phase.is_relative_to(ROOT.resolve()) or Path(request['output_dir'])!=phase/'data':raise ValueError('fresh owned phase/data required')
    if not set(request['cpu_affinity']).issubset(os.sched_getaffinity(0)):raise ValueError('reviewed four CPUs unavailable')
    phase.mkdir(parents=True);scratch.mkdir();(phase/'guard').mkdir()
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4',NUMEXPR_NUM_THREADS='4')
    env.pop('PYTHONPATH',None);env.pop('LD_LIBRARY_PATH',None)
    for key in ['TMPDIR','TMP','TEMP','QAIRT_TMP_DIR']:env[key]=str(scratch)
    worker.write(phase/'command.json',{'argv':command,'request_sha256':worker.sha(a.request),'release_sha256':worker.sha(a.release),'guard_sha256':worker.sha(GUARD),'effective_environment':{k:env.get(k) for k in ['PYTHONPATH','LD_LIBRARY_PATH','PYTHONDONTWRITEBYTECODE','OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS','TMPDIR','TMP','TEMP','QAIRT_TMP_DIR']},'bounds':request['bounds']})
    module=types.ModuleType('retained_cpu_guard');module.__file__=str(GUARD);exec(compile(GUARD.read_bytes(),str(GUARD),'exec'),module.__dict__)
    result=module.supervise(command,phase/'guard',100,env=env,grace=20)
    print(json.dumps(result,indent=2));raise SystemExit(0 if result['exit_code']==0 else 1)


if __name__=='__main__':main()
