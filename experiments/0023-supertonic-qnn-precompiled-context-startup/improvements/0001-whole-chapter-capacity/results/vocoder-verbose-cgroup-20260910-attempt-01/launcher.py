#!/usr/bin/env python3
"""One separately released vocoder diagnostic; same reviewed lifecycle.

Plan-only by default. No batch loop: execute separately and serially only under
component-specific releases. Name/label cleanup remains non-atomic.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time
import types
import diagnose_vocoder_context as worker

ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parents[3]
GUARD=REPO/'experiments/0032-qwen-3.5-2b-android-qnn-htp/tools/qwen_host_guard.py'


def command(request,request_path,release_path):
    root=Path(request['phase_dir'])
    env=request['environment']
    argv=['docker','run','--rm','--init','--pull=never','--network=none','--name',request['container_name'],
          '--label','supertonic-capacity-request='+worker.sha(request_path),'--memory=8g','--memory-swap=8g','--cpus=4','--pids-limit=128','--user','1000:1000']
    for source,readonly in ((REPO,True),(Path(request['sdk_root']),True),(root,False)):
        argv+=['--mount',f'type=bind,src={source},dst={source}'+(',readonly' if readonly else '')]
    for key,value in env.items():argv+=['--env',key+'='+value]
    argv+=['--workdir',str(root),request['docker_image_id'],'python3',str(ROOT/'tools/diagnose_vocoder_context.py'),
           '--request',str(request_path.resolve()),'--release',str(release_path.resolve()),'--execute']
    return argv


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--request',type=Path,required=True);p.add_argument('--release',type=Path);p.add_argument('--execute',action='store_true');a=p.parse_args()
    request=json.loads(a.request.read_text());release=a.release or Path(request['approval_path'])
    argv=command(request,a.request,release)
    if not a.execute:print(json.dumps({'status':'PLAN_ONLY_NO_DOCKER_OR_NATIVE_CALL','argv':argv},indent=2));return
    if a.release is None:p.error('explicit separate release required')
    worker.authorize(a.request,a.release)
    if worker.sha(__file__)!=request['launcher_sha256'] or worker.sha(GUARD)!=request['guard_sha256']:raise ValueError('launcher/guard source drift')
    phase=Path(request['phase_dir']).resolve()
    if not phase.is_relative_to(ROOT.resolve()) or phase.exists() or Path(request['output_dir'])!=phase/'data':raise ValueError('fresh owned phase/data required')
    phase.mkdir(parents=True);(phase/'scratch').mkdir();(phase/'guard').mkdir()
    worker.write(phase/'command.json',{'argv':argv,'request_sha256':worker.sha(a.request),'release_sha256':worker.sha(a.release)})
    started=time.monotonic();attempted=False;cleanup=None
    def inspect():
        return subprocess.run(['docker','container','inspect','--format','{{json .Config.Labels}}',request['container_name']],capture_output=True,text=True,timeout=10)
    try:
        before=inspect();worker.write(phase/'container-before.json',{'returncode':before.returncode,'stdout':before.stdout,'stderr':before.stderr})
        if before.returncode==0 or 'No such' not in before.stderr:raise RuntimeError('container name not proven absent')
        image=subprocess.run(['docker','image','inspect','--format','{{.Id}}',request['docker_image_id']],capture_output=True,text=True,timeout=10)
        if image.returncode or image.stdout.strip()!=request['docker_image_id']:raise RuntimeError('pinned image unavailable; no pull/build')
        module=types.ModuleType('retained_guard');module.__file__=str(GUARD);exec(compile(GUARD.read_bytes(),str(GUARD),'exec'),module.__dict__)
        attempted=True
        result=module.supervise(['nice','-n','15','ionice','-c','2','-n','7',*argv],phase/'guard',520,env=dict(os.environ),grace=20)
        if result['exit_code']!=0:raise RuntimeError('constructor attempt failed; no retry')
    finally:
        if attempted:
            after=inspect();cleanup={'inspect_returncode':after.returncode,'stdout':after.stdout,'stderr':after.stderr,'removal':None}
            if after.returncode==0:
                labels=json.loads(after.stdout)
                if labels.get('supertonic-capacity-request')!=worker.sha(a.request):
                    cleanup['ownership_error']='unexpected owner; refusing removal';worker.write(phase/'container-cleanup.json',cleanup)
                    raise RuntimeError('unexpected container owner; refusing removal')
                removed=subprocess.run(['docker','rm','-f',request['container_name']],capture_output=True,text=True,timeout=10)
                cleanup['removal']={'returncode':removed.returncode,'stdout':removed.stdout,'stderr':removed.stderr}
                after=inspect()
            cleanup['container_absent']=after.returncode!=0 and 'No such' in after.stderr
            cleanup['total_elapsed_seconds']=time.monotonic()-started
            worker.write(phase/'container-cleanup.json',cleanup)
            if not cleanup['container_absent']:raise RuntimeError('owned container cleanup incomplete')


if __name__=='__main__':main()
