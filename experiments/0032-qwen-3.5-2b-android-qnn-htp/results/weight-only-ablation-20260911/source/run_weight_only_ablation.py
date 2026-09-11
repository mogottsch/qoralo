#!/usr/bin/env python3
"""Bound two CPU weight-only cases; no automatic retry or overlapping heavy job."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time
from compare_fp32_position1 import pin,check,save
from run_fp32_position1 import EXP,REPO,PYTHON,SITE,AS

WORK=EXP/'.local/weight-only-ablation-20260911/attempt-01'
PRIOR=EXP/'.local/fp32-controlled-position1-20260911/attempt-01'


def prepare():
    WORK.mkdir(parents=True,exist_ok=False)
    request=json.loads((PRIOR/'request.json').read_text())
    result=json.loads((PRIOR/'run/data/result.json').read_text())
    if result['status']!='completed_single_FP32_call':raise ValueError('Completed FP32 reference required')
    records=request['pins']+[check(result['raw_outputs'])]
    for path in [PRIOR/'run/data/result.json',Path(__file__),EXP/'tools/weight_only_ablation.py',EXP/'tests/test_weight_only_ablation.py',
        SITE/'executorch/backends/qualcomm/quantizer/qconfig.py',SITE/'executorch/backends/qualcomm/quantizer/observers/per_block_param_observer.py',
        SITE/'executorch/backends/qualcomm/builders/node_visitor.py',SITE/'torch/ao/quantization/fx/_decomposed.py',SITE/'torchao/quantization/quant_primitives.py']:
        records.append(pin(path))
    for record in records:check(record)
    request.update(kind='two_CPU_weight_only_cases_FP32_activations',cases=['per_channel','lpbq32'],deadline_seconds=180,
       fp32_outputs=result['raw_outputs']['path'],pins=records,maximum_full_model_forwards=2,
       scope='only Linear/Conv W4 reconstruction, embedding/norm/constants and activations remainFP32; LPBQ scale expansion is source-derived not observed internal SDK encoding')
    save(WORK/'request.json',request);print(json.dumps(pin(WORK/'request.json')))


def execute(note):
    from qwen_host_guard import supervise
    if not note.strip():raise ValueError('Actual resource handoff required')
    request=json.loads((WORK/'request.json').read_text())
    for record in request['pins']:check(record)
    mem={s.split(':')[0]:int(s.split()[1]) for s in Path('/proc/meminfo').read_text().splitlines()}
    if mem['MemAvailable']<18*1024**2:raise RuntimeError('Heavy slot lacks18GiB available; no model start')
    run=WORK/'run';run.mkdir(exist_ok=False);scratch=run/'scratch';scratch.mkdir()
    if subprocess.check_output(['stat','-f','-c','%T',str(scratch)],text=True).strip() in ('tmpfs','ramfs'):raise ValueError('Disk scratch required')
    env=dict(os.environ,PYTHONPATH=str(EXP/'tools'),PYTHONDONTWRITEBYTECODE='1',PYTHONUNBUFFERED='1',OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4',TMPDIR=str(scratch),TMP=str(scratch),TEMP=str(scratch),XDG_CACHE_HOME=str(scratch));env.pop('LD_LIBRARY_PATH',None)
    command=['nice','-n','15','ionice','-c','2','-n','7','prlimit','--as='+str(AS),'--','taskset','--cpu-list','0,1,2,3',str(PYTHON),str(EXP/'tools/weight_only_ablation.py'),'--request',str(WORK/'request.json'),'--output',str(run/'data')]
    save(run/'reservation.json',{'owner':'Ben','time_ns':time.time_ns(),'handoff':note,'AS':AS,'cpus':4,'available_kib':mem['MemAvailable']});save(run/'command.json',command)
    print('ACTUAL START: two CPU weight-only ablations, FP32 activations,18GiB AS/4CPU/180s',flush=True)
    result=supervise(command,run,180,env=env,grace=20)
    save(run/'scratch-before-cleanup.json',[str(p.relative_to(scratch)) for p in scratch.rglob('*')])
    for p in sorted((p for p in scratch.rglob('*') if p.is_dir()),key=lambda p:len(p.parts),reverse=True):
        if not any(p.iterdir()):p.rmdir()
    try:os.killpg(result['child_pid'],0);absent=False
    except ProcessLookupError:absent=True
    cleanup={'child_reaped':result['child_reaped'],'group_absent':absent,'scratch_empty':not any(scratch.iterdir()),'time_ns':time.time_ns(),'retry':False}
    save(run/'release.json',cleanup);print('RELEASED: '+json.dumps(cleanup),flush=True)
    if result['exit_code']!=0:raise SystemExit(result['exit_code'] or 1)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['prepare','run']);p.add_argument('--handoff-note',default='');a=p.parse_args();prepare() if a.action=='prepare' else execute(a.handoff_note)
