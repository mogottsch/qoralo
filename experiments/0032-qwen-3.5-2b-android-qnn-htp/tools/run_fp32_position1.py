#!/usr/bin/env python3
"""Fresh-path preparation and bounded CPU FP32 worker; resource scheduling external."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from compare_fp32_position1 import check,pin,save

EXP=Path(__file__).resolve().parents[1]
REPO=EXP.parents[1]
PYTHON=REPO/'artifacts/venv-executorch-1.2/bin/python'
SITE=REPO/'artifacts/venv-executorch-1.2/lib/python3.11/site-packages'
WORK=EXP/'.local/fp32-controlled-position1-20260911/attempt-01'
SOURCE=EXP/'results/controlled-position1-paired-qnn-20260910/raw'
AS=18*1024**3


def prepare():
    WORK.mkdir(parents=True,exist_ok=False)
    header=SOURCE/'pack-header.json';h=json.loads(header.read_text())
    manifest=EXP/'results/host-histogram-precision-20260910/artifact-manifest.json'
    files=json.loads(manifest.read_text())['files']
    checkpoint=EXP/files['checkpoint']['path'];params=EXP/files['params']['path'];ids=EXP/files['input_ids']['path']
    prior={name:str(SOURCE/f'{name}-result.json') for name in ('qdq','qnn')}
    records=[]
    for key in ('checkpoint','params','input_ids','adapter_source'):
        record=dict(files[key],path=str(EXP/files[key]['path']));records.append(check(record))
    records.append(check(h['input_pack']))
    for path in prior.values():
        r=json.loads(Path(path).read_text());records.append(check(r['raw_outputs']))
        if r['submitted_input_values_sha256']!=h['input_values_sha256']:raise ValueError('Prior call/input lineage mismatch')
    for path in [header,manifest,*map(Path,prior.values()),Path(__file__),EXP/'tools/compare_fp32_position1.py',
                 EXP/'tools/controlled_position1.py',EXP/'tools/compare_qnn_trajectory.py',EXP/'tools/replay_saved_qdq.py',EXP/'tools/qwen_host_guard.py',
                 EXP/'tools/compile_exact_qnn.py',EXP/'tests/test_fp32_position1.py',PYTHON,
                 SITE/'executorch/examples/models/llama/model_args.py',SITE/'executorch/version.py',
                 SITE/'torch/__init__.py',SITE/'torch/lib/libtorch_cpu.so',SITE/'torch/lib/libtorch_python.so',SITE/'torch/lib/libc10.so']:
        records.append(pin(path))
    request={'kind':'one_unquantized_same_adapter_FP32_call_on_saved_controlled_p1','checkpoint':str(checkpoint),'params':str(params),
      'token_ids':str(ids),'pack_header':str(header),'prior_result_paths':prior,'pins':records,
      'address_space_bytes':AS,'cpu_affinity':[0,1,2,3],'deadline_seconds':600,'termination_grace_seconds':20,
      'maximum_full_model_forwards':1,'new_QNN_model_calls':0,'new_compiles':0,'canonical_campaign':False,
      'reference_scope':'unchanged converted checkpoint promoted to FP32 in same adapter; QDQ-origin history, not independent upstream implementation/FP32-origin trajectory',
      'source_facts':['Diagnostic compiler appends post-layer hidden states in layer order, after49 public outputs.',
        'Read-only hooks return None and copy exactly these24 post-layer outputs; original model forward is unchanged.',
        'Use copying load_state_dict, not meta/assign, to preserve plain A_log/dt_bias recurrence references.']}
    save(WORK/'request.json',request)
    save(WORK/'prepare.json',{'status':'prepared_no_model_load','request':pin(WORK/'request.json'),'pins_checked':len(records),'time_ns':time.time_ns()})
    print(json.dumps(pin(WORK/'request.json')))


def execute(note):
    from qwen_host_guard import supervise
    request=json.loads((WORK/'request.json').read_text())
    if not note.strip():raise ValueError('Actual resource handoff note required')
    for rec in request['pins']:check(rec)
    mem={s.split(':')[0]:int(s.split()[1]) for s in Path('/proc/meminfo').read_text().splitlines()}
    if mem['MemAvailable']<18*1024**2:raise RuntimeError('Less than18GiB available; preserve existing preparation and yield heavy slot')
    run=WORK/'run';run.mkdir(exist_ok=False);scratch=run/'scratch';scratch.mkdir()
    if subprocess.check_output(['stat','-f','-c','%T',str(scratch)],text=True).strip() in ('tmpfs','ramfs'):
        raise ValueError('Owned disk scratch required')
    env=dict(os.environ,PYTHONPATH=str(EXP/'tools'),PYTHONDONTWRITEBYTECODE='1',PYTHONUNBUFFERED='1',OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4',TMPDIR=str(scratch),TMP=str(scratch),TEMP=str(scratch),XDG_CACHE_HOME=str(scratch))
    env.pop('LD_LIBRARY_PATH',None)
    command=['nice','-n','15','ionice','-c','2','-n','7','prlimit','--as='+str(AS),'--','taskset','--cpu-list','0,1,2,3',str(PYTHON),
             str(EXP/'tools/compare_fp32_position1.py'),'--request',str(WORK/'request.json'),'--output',str(run/'data')]
    save(run/'reservation.json',{'owner':'Ben','time_ns':time.time_ns(),'handoff':note,'address_space_bytes':AS,'cpus':4,'available_kib':mem['MemAvailable']})
    save(run/'command.json',command)
    print('ACTUAL START: one full-model FP32 worker,18GiB AS/4CPU/600s, no QNN or phone.',flush=True)
    result=supervise(command,run,request['deadline_seconds'],env=env,grace=20)
    inventory=[{'path':str(p.relative_to(scratch)),'directory':p.is_dir(),'bytes':None if p.is_dir() else p.stat().st_size} for p in scratch.rglob('*')]
    save(run/'scratch-before-cleanup.json',inventory)
    for p in sorted((p for p in scratch.rglob('*') if p.is_dir()),key=lambda p:len(p.parts),reverse=True):
        if not any(p.iterdir()):p.rmdir()
    try:os.killpg(result['child_pid'],0);absent=False
    except ProcessLookupError:absent=True
    cleanup={'child_reaped':result['child_reaped'],'group_absent':absent,'scratch_empty':not any(scratch.iterdir()),'time_ns':time.time_ns(),'automatic_retry':False}
    save(run/'release.json',cleanup);print('RELEASED: '+json.dumps(cleanup),flush=True)
    if result['exit_code']!=0:raise SystemExit(result['exit_code'] or 1)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['prepare','run']);p.add_argument('--handoff-note',default='');args=p.parse_args()
    prepare() if args.action=='prepare' else execute(args.handoff_note)
