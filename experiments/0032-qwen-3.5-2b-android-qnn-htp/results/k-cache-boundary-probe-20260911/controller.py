#!/usr/bin/env python3
"""External bounds for the assigned paired host probe; no retry/resume logic."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import threading
import time
import types

EXP=Path(__file__).resolve().parents[2]
WORK=EXP/'.local/k-cache-boundary-probe-20260911/attempt-01'
PY=EXP.parents[1]/'artifacts/venv-executorch-1.2/bin/python'
WORKER=EXP/'tools/k_cache_boundary_probe.py'
SDK=Path('/home/moritz/opt/qairt/2.49.0.260730')


def run(phase,budget,request_sha=None):
    g=WORK/'guards'/phase;g.mkdir(parents=True,exist_ok=False)
    scratch=WORK/'scratch'/phase;scratch.mkdir(parents=True,exist_ok=False)
    env=dict(os.environ);env.pop('PYTHONPATH',None)
    env.update(QNN_SDK_ROOT=str(SDK),PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4')
    env.update({k:str(scratch) for k in ('TMPDIR','TMP','TEMP','QAIRT_TMP_DIR')})
    site=PY.parent.parent/'lib/python3.11/site-packages'
    env['LD_LIBRARY_PATH']=':'.join(map(str,[SDK/'lib/x86_64-linux-clang',site/'executorch/backends/qualcomm/sdk/libcxx-14.0.0',site/'executorch/extension/pybindings']))
    env['PATH']=str(EXP.parents[1]/'artifacts/tools/flatbuffers-25.12.19')+':'+env['PATH']
    command=['nice','-n','15','ionice','-c','2','-n','7','prlimit','--as=4294967296','--','taskset','--cpu-list','0,1,2,3',str(PY)]
    if phase=='tests':command += [str(EXP/'tests/test_k_cache_boundary_probe.py')]
    else:
        command += [str(WORKER),phase,'--root',str(WORK)]
        if request_sha:command += ['--request-sha',request_sha]
    (g/'command.json').write_text(json.dumps({'command':command,'scratch':str(scratch),'limits':{'AS_bytes':4294967296,'CPUs':[0,1,2,3],'seconds':budget,'grace_seconds':20}},indent=2)+'\n')
    module=types.ModuleType('owned_guard');path=EXP/'tools/qwen_host_guard.py';exec(compile(path.read_bytes(),str(path),'exec'),module.__dict__)
    done=threading.Event()
    def stop_watch():
        while not done.wait(.1):
            if (WORK/'STOP').exists():(g/'STOP').touch();return
    watcher=threading.Thread(target=stop_watch,daemon=True);watcher.start()
    try:r=module.supervise(command,g,budget,env=env,grace=20)
    finally:done.set();watcher.join()
    pid=r['child_pid'];assert not Path(f'/proc/{pid}').exists()
    try:os.killpg(pid,0)
    except ProcessLookupError:pass
    else:raise RuntimeError('Worker group remains')
    cleanup={'pid':pid,'reaped':r['child_reaped'],'group_absent':True,'scratch_empty':not any(scratch.iterdir())}
    (g/'cleanup.json').write_text(json.dumps(cleanup,indent=2)+'\n')
    print(json.dumps({'phase':phase,**r,'cleanup':cleanup},indent=2),flush=True)
    if r['exit_code']!=0 or r['reason']!='process_exit':raise RuntimeError('Phase stopped; preserve first outcome: '+phase)
    return r


def main():
    a=argparse.ArgumentParser();a.add_argument('mode',choices=('prepare','execute'));args=a.parse_args()
    if args.mode=='prepare':
        WORK.mkdir(parents=True,exist_ok=False);run('tests',30);run('prepare',60)
        print('Prepared exact request SHA:',hashlib.sha256((WORK/'request.json').read_bytes()).hexdigest())
    else:
        sha=hashlib.sha256((WORK/'request.json').read_bytes()).hexdigest();start=time.monotonic();rows=[]
        try:
            for phase,seconds in [('compile',120),('runtime',60)]:
                if (WORK/'STOP').exists():raise RuntimeError('STOP requested')
                left=240-(time.monotonic()-start)
                if left<=0:raise TimeoutError('Active cap')
                rows.append(run(phase,min(seconds,left),sha))
        finally:
            result={'phases':rows,'elapsed_seconds':time.monotonic()-start,'request_sha256':sha,'automatic_retry':False}
            with (WORK/'controller-result.json').open('x') as f:json.dump(result,f,indent=2);f.write('\n')


if __name__=='__main__':main()
