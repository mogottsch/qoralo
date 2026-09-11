#!/usr/bin/env python3
"""One standalone same-PTE/input device fixture; explicit scheduling handoff and full lock."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import time

EXP=Path(__file__).resolve().parents[1];REPO=EXP.parents[1]
HOST=EXP/'.local/k-cache-boundary-probe-20260911/attempt-01'
WORK=EXP/'.local/k-cache-v73-20260911/attempt-02'
REMOTE='/data/local/tmp/vibevoice-0032-kcache-20260911-02'
SDK=Path('/home/moritz/opt/qairt/2.49.0.260730')
ET=EXP/'.local/executorch'
ADB=Path('/home/moritz/Android/Sdk/platform-tools/adb')
SERIAL='R5CW81PR8SY'


def pin(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        while b:=f.read(1024*1024):h.update(b)
    return {'path':str(p),'bytes':p.stat().st_size,'sha256':h.hexdigest()}


def save(p,d):
    with p.open('x') as f:json.dump(d,f,indent=2);f.write('\n')


def prepare():
    WORK.mkdir(parents=True,exist_ok=False)
    request=json.loads((HOST/'request.json').read_text());compiled=json.loads((HOST/'compile/data/result.json').read_text())
    files=[('model.pte',Path(compiled['artifact']['path'])),('kcache_probe',ET/'build-android/examples/qualcomm/executor_runner/qnn_executor_runner'),('libqnn_executorch_backend.so',ET/'build-android/lib/executorch/backends/qualcomm/libqnn_executorch_backend.so')]
    for name in ('libQnnHtp.so','libQnnSystem.so','libQnnHtpV73Stub.so'):files.append((name,SDK/'lib/aarch64-android'/name))
    files.append(('libQnnHtpV73Skel.so',SDK/'lib/hexagon-v73/unsigned/libQnnHtpV73Skel.so'))
    for name,r in zip(('cache3.f32le','key3.f32le','cache15.f32le','key15.f32le'),request['inputs']):
        assert pin(Path(r['path']))==r;files.append((name,Path(r['path'])))
    assert pin(files[0][1])==compiled['artifact'] and compiled['artifact']['sha256']=='d88182196544514ee3dc888b05a68a3eab11d7be90f4f5befd4a8580a01faf0d'
    line=' '.join(REMOTE+'/'+n for n in ('cache3.f32le','key3.f32le','cache15.f32le','key15.f32le'))+'\n'
    (WORK/'input_list.txt').write_text(line);files.append(('input_list.txt',WORK/'input_list.txt'))
    command=['./kcache_probe','--model_path=model.pte','--input_list_path=input_list.txt','--output_folder_path=out','--warm_up=0','--iteration=1','--shared_buffer=false','--log_level=5','--profile_level=0','--etdump_path=out/etdump.etdp','--performance_output_path=out/inference_speed.txt']
    invoke='#!/system/bin/sh\nset -eu\ncd '+shlex.quote(REMOTE)+'\nexport LD_LIBRARY_PATH='+shlex.quote(REMOTE)+'\nexport ADSP_LIBRARY_PATH='+shlex.quote(REMOTE+';/vendor/lib/rfsa/adsp;/vendor/dsp/cdsp;/system/lib/rfsa/adsp')+'\nsha256sum -c SHA256SUMS >out/pre-run-hashes.txt\ntest "$(wc -l <input_list.txt)" -eq 1\nset +e\ntimeout -s TERM -k 5 60 sh -c '+shlex.quote('echo $$ > runner.pid; exec '+' '.join(shlex.quote(x) for x in command))+' >out/runner.stdout.log 2>out/runner.stderr.log\nrc=$?\nprintf "%s\\n" "$rc" >out/exit-code.txt\nsha256sum -c SHA256SUMS >out/post-run-hashes.txt\nexit "$rc"\n'
    (WORK/'invoke.sh').write_text(invoke);files.append(('invoke.sh',WORK/'invoke.sh'))
    rows=[{'remote_name':n,**pin(p)} for n,p in files]
    (WORK/'SHA256SUMS').write_text(''.join(r['sha256']+'  '+r['remote_name']+'\n' for r in rows))
    save(WORK/'binding.json',{'files':rows,'remote_root':REMOTE,'host_request':pin(HOST/'request.json'),'controller':pin(Path(__file__)),'command':command,'device_limit_seconds':60,'warmup':0,'iterations':1,'single_input_list_line':line,'source':pin(ET/'examples/qualcomm/executor_runner/qnn_executor_runner.cpp'),'link_command':pin(ET/'build-android/examples/qualcomm/executor_runner/CMakeFiles/qnn_executor_runner.dir/link.txt'),'scope':'one standalone fixture; no app/package/data operations; coordinated Janek handoff and full phone.lock required'})
    print('Offline binding ready:',WORK,flush=True)


def service_conflict(activity):
    # Room's idle invalidation binder is not a generation job. Unknown services
    # or active foreground/ongoing calls remain a scheduling conflict.
    if not activity.startswith('ACTIVITY MANAGER SERVICES'):
        raise ValueError('Service observation unavailable; cannot classify idle')
    headers=[s for s in activity.splitlines() if '* ServiceRecord{' in s]
    return ('isForeground=true' in activity or 'ongoingCalls=true' in activity or
            any('androidx.room.MultiInstanceInvalidationService' not in s for s in headers))


def execute(note):
    binding=json.loads((WORK/'binding.json').read_text());assert pin(Path(__file__))==binding['controller']
    for r in binding['files']:
        assert pin(Path(r['path']))=={k:r[k] for k in ('path','bytes','sha256')}
    assert binding['warmup']==0 and binding['iterations']==1
    assert (WORK/'input_list.txt').read_text()==binding['single_input_list_line']
    assert len(binding['single_input_list_line'].split())==4
    results=WORK/'device';results.mkdir(exist_ok=False)
    lock=(REPO/'artifacts/locks/phone.lock').open('a+')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    start=time.monotonic();counter=0;created=False;launched=False;pulled=False
    save(results/'reservation.json',{'owner':'Ben','handoff':note,'time_ns':time.time_ns(),'lock':str(REPO/'artifacts/locks/phone.lock')})
    print('PHONE RESERVED under full phone.lock; checking idle handoff before launch.',flush=True)
    def adb(*args,timeout=25,check=True,label='adb'):
        nonlocal counter
        counter+=1;t=time.monotonic();r=subprocess.run([str(ADB),'-s',SERIAL,*args],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout)
        stem=results/f'{counter:03d}-{label}';stem.with_suffix('.stdout').write_bytes(r.stdout);stem.with_suffix('.stderr').write_bytes(r.stderr)
        save(stem.with_suffix('.json'),{'args':args,'exit_code':r.returncode,'elapsed_seconds':time.monotonic()-t})
        if check and r.returncode:raise RuntimeError(f'{label} failed: {r.returncode}')
        return r
    def shell(s,**kw):return adb('shell',s,**kw)
    try:
        device=shell('getprop ro.product.model; getprop ro.soc.model; getprop ro.product.cpu.abi; getprop ro.build.fingerprint',label='device').stdout.decode().replace('\r','').splitlines()
        assert device[:3]==['SM-S918B','SM8550','arm64-v8a']
        activity=shell('dumpsys activity services dev.vibevoice.podcast',label='services').stdout.decode()
        # Inspect active/unknown services independently; do not confuse Room's
        # long-lived idle binder with work. Janek's actual handoff covers user scheduling.
        assert not service_conflict(activity), 'Active or unknown app service/job present; yield slot'
        procs=shell('pidof qwen35_explicit_state_runner qnn_executor_runner kcache_probe 2>/dev/null || true',label='other-runners').stdout.strip();assert not procs,'Other CLI runner active; yield slot'
        foreground=shell('dumpsys activity activities | grep -E "topResumedActivity|mResumedActivity"',check=False,label='foreground').stdout.decode()
        save(results/'idle-check.json',{'active_or_unknown_service':False,'other_CLI_jobs':False,'foreground_activity_recorded':foreground,'foreground_visibility_is_not_generation_evidence':True,'user_scheduling_basis':note})
        shell('dumpsys battery',check=False,label='battery-before');shell('dumpsys thermalservice',check=False,label='thermal-before')
        assert shell('test ! -e '+shlex.quote(REMOTE),check=False,label='fresh-root').returncode==0,'Remote root exists; never overwrite'
        shell('mkdir '+shlex.quote(REMOTE)+' && mkdir '+shlex.quote(REMOTE+'/out'),label='mkdir');created=True
        for r in binding['files']:adb('push',r['path'],REMOTE+'/'+r['remote_name'],label='push')
        adb('push',str(WORK/'SHA256SUMS'),REMOTE+'/SHA256SUMS',label='push-hashes')
        shell('cd '+shlex.quote(REMOTE)+' && sha256sum -c SHA256SUMS && chmod 755 kcache_probe && command -v timeout',label='verify-stage')
        assert time.monotonic()-start<120,'Staging exceeded scheduling budget'
        launched=True;save(results/'launch.json',{'time_ns':time.time_ns(),'command':binding['command'],'one_logical_forward_planned':True})
        print('PHONE ACTUAL START: one exact-list fixture, warmup0/iteration1.',flush=True)
        run=shell('sh '+shlex.quote(REMOTE+'/invoke.sh'),timeout=80,check=False,label='execute')
        adb('pull',REMOTE+'/out',str(results/'out'),timeout=35,label='pull-out');pulled=True
        shell('dumpsys battery',check=False,label='battery-after');shell('dumpsys thermalservice',check=False,label='thermal-after')
        save(results/'outcome.json',{'adb_execution_exit_code':run.returncode,'outputs_pulled':True,'model_or_app_modified':False,'elapsed_seconds':time.monotonic()-start})
    finally:
        cleanup={'remote_created':created,'launched':launched,'pulled_before_cleanup':pulled}
        if created:
            # Kill only an owned PID whose cwd and command identify this exact private fixture.
            cmd='cd '+shlex.quote(REMOTE)+'; if test -f runner.pid; then p=$(cat runner.pid); if test -e /proc/$p && test "$(readlink /proc/$p/cwd)" = '+shlex.quote(REMOTE)+' && tr "\\000" " " </proc/$p/cmdline | grep -q kcache_probe; then kill -TERM "$p"; sleep 1; kill -KILL "$p" 2>/dev/null || true; fi; fi'
            shell(cmd,check=False,label='owned-process-cleanup')
            absent=shell('pidof kcache_probe 2>/dev/null || true',label='process-absent').stdout.strip();cleanup['process_absent']=not bool(absent)
            if not pulled:
                rr=adb('pull',REMOTE+'/out',str(results/'partial-out'),timeout=35,check=False,label='pull-partial');cleanup['partial_pull_exit_code']=rr.returncode
            # Keep remote evidence if output recovery failed; never delete the only copy.
            if not absent and (pulled or cleanup.get('partial_pull_exit_code')==0):
                shell('rm -rf '+shlex.quote(REMOTE),label='remove-owned-root')
                cleanup['remote_absent']=shell('test ! -e '+shlex.quote(REMOTE),check=False,label='verify-root-absent').returncode==0
            else:cleanup['remote_retained_for_recovery']=True
        save(results/'cleanup.json',cleanup);save(results/'release.json',{'owner':'Ben','time_ns':time.time_ns(),'elapsed_seconds':time.monotonic()-start,'cleanup':cleanup})
        fcntl.flock(lock,fcntl.LOCK_UN);lock.close();print('PHONE RELEASED:',json.dumps(cleanup),flush=True)


if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('mode',choices=('prepare','run'));a.add_argument('--handoff-note');x=a.parse_args()
    if x.mode=='prepare':prepare()
    else:
        if not x.handoff_note:a.error('actual scheduling handoff note required, not an approval request')
        execute(x.handoff_note)
