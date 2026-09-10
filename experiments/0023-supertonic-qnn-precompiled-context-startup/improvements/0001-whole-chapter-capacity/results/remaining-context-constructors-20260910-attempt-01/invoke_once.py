#!/usr/bin/env python3
"""Receipt capture around the exact released launcher; one explicit component only."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

RESULT=Path(__file__).resolve().parent
TRACK=RESULT.parents[1]
ORDER=['text','vector','vocoder']


def write(path,value):
    with path.open('x') as f:json.dump(value,f,indent=2);f.write('\n')


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def main():
    component=sys.argv[1]
    if component not in ORDER:raise ValueError('only the released three components')
    for earlier in ORDER[:ORDER.index(component)]:
        receipt=json.loads((RESULT/earlier/'outcome.json').read_text())
        if not receipt['all_gates_passed']:raise RuntimeError('stop on first failure; no later component')
    req=TRACK/f'protocol/remaining-constructors/{component}.request.NOT_APPROVED.json'
    request=json.loads(req.read_text());phase=Path(request['phase_dir']);out=RESULT/component
    if phase.exists() or (out/'launcher-command.json').exists():raise FileExistsError('no retry/resume')
    argv=['python',str(TRACK/'tools/run_component_constructor.py'),'--request',str(req),'--release',request['approval_path'],'--execute']
    write(out/'launcher-command.json',{'argv':argv,'attempts_allowed':1,'automatic_retry':False})
    start=time.monotonic()
    with (out/'launcher.stdout.log').open('xb') as stdout,(out/'launcher.stderr.log').open('xb') as stderr:
        process=subprocess.run(argv,stdout=stdout,stderr=stderr)
    launch={'exit_code':process.returncode,'elapsed_seconds':time.monotonic()-start,'attempts':1,'automatic_retry':False}
    write(out/'launcher-result.json',launch)
    # Preserve raw metadata and logs before any extra saved-result classification.
    raw=out/'raw';raw.mkdir()
    for file in sorted(phase.rglob('*')):
        if file.is_file() and file.suffix in ('.json','.jsonl','.log','.txt'):
            dest=raw/file.relative_to(phase);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(file,dest)
    def saved(name):
        file=phase/name
        return json.loads(file.read_text()) if file.exists() else None
    guard=saved('guard/supervisor.json');container=saved('container-cleanup.json');result=saved('data/result.json');verification=saved('data/final-verification.json')
    pid=guard['child_pid'] if guard else None
    group_absent=None
    if pid is not None:
        try:os.killpg(pid,0)
        except ProcessLookupError:group_absent=True
        else:group_absent=False
    cleanup={'child_pid':pid,'child_reaped':guard.get('child_reaped') if guard else None,'pid_absent':not Path(f'/proc/{pid}').exists() if pid else None,'process_group_absent':group_absent,
             'container_absent':container.get('container_absent') if container else None,'scratch_empty':not any((phase/'scratch').rglob('*')) if (phase/'scratch').exists() else None,'name_label_cleanup_atomic':False}
    write(out/'cleanup.json',cleanup)
    artifacts=[]
    for file in sorted((phase/'data').glob('*')):
        if file.is_file() and file.suffix in ('.onnx','.bin'):
            artifacts.append({'path':str(file),'bytes':file.stat().st_size,'sha256':sha(file),'storage':'LOCAL_ONLY_preserve_actual_bytes'})
    write(out/'local-artifacts.json',{'artifacts':artifacts,'hashes_are_not_substitutes_for_bytes':True})
    if phase.exists():
        with (phase/'PRESERVE.md').open('x') as f:f.write('Preserve actual descriptor/context and any partial artifacts plus complete logs. LOCAL-ONLY; migrate bytes, not just hashes. This component release is consumed: no retry or forward. Durable raw receipts are in '+str(out)+'.\n')
    matches=False
    if result and result.get('external_context'):
        by_name={Path(v['path']).name:v for v in artifacts};matches=True
        for name,key in [(f'{component}-context.onnx','descriptor'),(f'{component}-context_qnn.bin','binary')]:
            actual=by_name.get(name,{});expected=result['external_context'][key]
            matches &= actual.get('sha256')==expected['sha256'] and actual.get('bytes')==expected['bytes']
    passed=bool(launch['exit_code']==0 and result and result['status']=='constructor_and_artifact_gates_passed_no_execution' and result['python_InferenceSession_calls']==1 and result['Session_Run_calls']==0
        and verification and verification['status']=='all_pins_unchanged' and matches and all(cleanup.get(k) is True for k in ['child_reaped','pid_absent','process_group_absent','container_absent','scratch_empty']))
    outcome={'component':component,'all_gates_passed':passed,'launcher':launch,'guard':guard,'result':result,'final_verification':verification,'cleanup':cleanup,'postclose_artifact_hashes_match':matches}
    write(out/'outcome.json',outcome)
    print(json.dumps(outcome,indent=2))
    if not passed:raise SystemExit(1)


if __name__=='__main__':main()
