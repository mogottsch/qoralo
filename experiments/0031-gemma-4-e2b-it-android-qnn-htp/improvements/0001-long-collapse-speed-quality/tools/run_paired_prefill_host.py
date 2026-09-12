#!/usr/bin/env python3
"""Plan-only bounded host half. Requires a NEW grant and released actual capture."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import shutil
import signal
import struct
import subprocess
import sys
import time

TRACK=Path(__file__).resolve().parents[1]
ROOT=TRACK/'.local/paired-prefill-host-runs'
VENV=TRACK.parents[1]/'.local/qairt-2.49.40-venv/bin/python'
POLICY=TRACK/'.local/matched-prefill-reference/policy-01/policy.json'
LEDGER=TRACK/'.local/matched-prefill-reference/inputs-01/ledger.json'
STAGE_SHA='b99056c1faa1e25823fd9bcda2a0968a0445cb93458dc1069e7d269eb9c54953'
INPUT_SHA='3b5c04febbc9d55c529ee7ece510607203dbdc8256a6abc05ba0498cf4e52b64'
G=1024**3


def save(path,data):Path(path).write_text(json.dumps(data,indent=2)+'\n')
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def assert_host_sources():
    bindings=json.loads((TRACK/'results/matched-prefill-reference-readiness-01/implementation-bindings.json').read_text())
    wanted={str(Path(__file__).resolve()),str(TRACK/'tools/declared_dlc_reference.py'),str(TRACK/'tools/matched_prefill_inputs.py')}
    if not wanted<=set(bindings):raise ValueError('frozen host source bindings missing')
    for path in wanted:
        if digest(path)!=bindings[path]:raise ValueError('frozen host source changed '+path)
    return {path:bindings[path] for path in sorted(wanted)}


def validate_phone(path):
    path=Path(path).resolve();x=json.loads(path.read_text())
    if x.get('reviewed_stage_digest')!=STAGE_SHA or x.get('process_exit_code')!=0 or not x.get('identity_verified') or not x.get('input_hashes_verified') or not x.get('raw_pull_completed') or not x.get('phone_lock_released') or x.get('cleanup')!='verified_absent':raise ValueError('successful hash-bound released phone capture required')
    device=path.parent/'raw/device';ids=[int(v) for v in (device/'input-token-ids.txt').read_text().split()]
    if len(ids)!=1929 or any(v<0 or v>=262144 for v in ids) or hashlib.sha256(struct.pack('<1929i',*ids)).hexdigest()!=INPUT_SHA:raise ValueError('actual input IDs differ')
    executions=[]
    with (device/'genie-verbose.log').open(errors='replace') as f:
        for line in f:
            match=re.search(r'Graph (ar128|ar1)_cl4096_1_of_1 execution finished with result (\S+)',line)
            if match:executions.append(match.groups())
            if 'GEMMA_PREFILL_CAPTURE_ERROR' in line:raise ValueError('capture failure marker')
    if executions!=[('ar128','0')]*16:raise ValueError('exact16 successful AR128 and zero AR1 required')
    if 'GEMMA_PREFILL_CAPTURE_ERROR' in (device/'runner.stderr').read_text(errors='replace'):raise ValueError('observer failed')
    return device/'prefill-capture'


def capacity():
    m={s.split(':')[0]:int(s.split()[1])*1024 for s in Path('/proc/meminfo').read_text().splitlines()}
    return {'mem_available':m['MemAvailable'],'swap_free':m['SwapFree'],'disk_free':shutil.disk_usage(TRACK).free}


def owned_usage(child,born):
    try:
        s=Path(f'/proc/{child.pid}/stat').read_text();fields=s[s.rfind(') ')+2:].split()
        if fields[19]!=born:return {'unavailable':'starttime mismatch'}
        io={line.split(':')[0]:int(line.split()[1]) for line in Path(f'/proc/{child.pid}/io').read_text().splitlines()}
        return {'starttime':born,'utime_ticks':int(fields[11]),'stime_ticks':int(fields[12]),'ticks_per_second':os.sysconf('SC_CLK_TCK'),'io':io}
    except (OSError,IndexError,ValueError) as e:return {'unavailable':type(e).__name__}


def internal(root,compute=False):
    root=Path(root).resolve()
    if not root.is_relative_to(ROOT):raise ValueError('owned run root required')
    grant=json.loads((root/'grant.json').read_text())
    if grant['unit'] not in Path('/proc/self/cgroup').read_text():raise PermissionError('internal worker requires its bounded systemd unit')
    if assert_host_sources()!=grant['host_source_bindings'] or digest(grant['phone_collection'])!=grant['phone_collection_sha256']:raise ValueError('run source/capture bindings changed')
    if compute:
        import numpy,scipy
        if numpy.__version__!='1.26.4' or scipy.__version__!='1.15.3':raise ValueError('pinned reference dependency version changed')
        resource.setrlimit(resource.RLIMIT_FSIZE,(128*1024**2,128*1024**2))
        from matched_prefill_inputs import run_reference_prefill
        result=run_reference_prefill(POLICY,root/'bound-inputs/ledger.json',root/'native',authorization_id=grant['grant_id'],wall_seconds=1760)
        print(json.dumps(result));return 0
    started=time.monotonic();child=None;reason=None;result={'compute_child_launched':False,'memory_lock_admission':False}
    def stop(sig,frame):
        nonlocal reason
        reason='guard_signal_'+str(sig)
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    try:
        before=capacity();save(root/'capacity-before.json',before)
        if before['mem_available']<16*G or before['swap_free']<10*G or before['disk_free']<64*G:raise RuntimeError('fresh headroom insufficient')
        capture=validate_phone(grant['phone_collection'])
        from matched_prefill_inputs import bind_captured_noncache
        bind_captured_noncache(capture,LEDGER,root/'bound-inputs')
        command=[str(VENV),'-B',str(Path(__file__).resolve()),'--internal-compute',str(root)]
        env={'PATH':'/usr/bin:/bin','HOME':str(root/'home'),'TMPDIR':str(root/'tmp'),'PYTHONDONTWRITEBYTECODE':'1','OMP_NUM_THREADS':'2','OPENBLAS_NUM_THREADS':'2','MKL_NUM_THREADS':'2','NUMEXPR_NUM_THREADS':'2'}
        save(root/'compute-command.json',{'argv':command,'environment':env,'close_fds':True})
        with (root/'child.stdout').open('xb') as so,(root/'child.stderr').open('xb') as se:child=subprocess.Popen(command,env=env,stdin=subprocess.DEVNULL,stdout=so,stderr=se,close_fds=True,start_new_session=True)
        stat=Path(f'/proc/{child.pid}/stat').read_text();born=stat[stat.rfind(') ')+2:].split()[19];save(root/'child-identity.json',{'pid':child.pid,'starttime':born});result['compute_child_launched']=True
        while child.poll() is None:
            c=capacity();elapsed=time.monotonic()-started
            with (root/'resources.jsonl').open('a') as f:f.write(json.dumps({'seconds':elapsed,**c,'child':owned_usage(child,born)})+'\n')
            if c['mem_available']<4*G or c['swap_free']<8*G or c['disk_free']<64*G:reason='headroom_floor'
            if elapsed>=1770:reason='1770s_work_budget_cleanup_reserved'
            if sum(p.stat().st_size for p in root.rglob('*') if p.is_file())>G:reason='owned_output_disk_cap_1GiB'
            if reason:
                os.killpg(child.pid,signal.SIGTERM)
                try:child.wait(timeout=12)
                except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait(timeout=5)
                break
            time.sleep(2)
        result['actual_child_exit']=child.wait()
    except BaseException as e:result['guard_error']=repr(e)
    finally:
        if child is not None and child.poll() is None:
            os.killpg(child.pid,signal.SIGTERM)
            try:child.wait(timeout=12)
            except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait(timeout=5)
        result.update(child_reaped=child is None or child.poll() is not None,stop_reason=reason,seconds=time.monotonic()-started,raw_retained=True,full_prefill_started=(root/'native/prefill-started.json').exists())
        save(root/'guard-result.json',result)
    return 0 if result.get('actual_child_exit')==0 and not reason and 'guard_error' not in result else 1


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true');p.add_argument('--run-id');p.add_argument('--pi-grant');p.add_argument('--phone-collection',type=Path);p.add_argument('--internal-guard',type=Path);p.add_argument('--internal-compute',type=Path);a=p.parse_args()
    if a.internal_guard:return internal(a.internal_guard)
    if a.internal_compute:return internal(a.internal_compute,True)
    if not a.execute:
        print(json.dumps({'mode':'plan_only','model_executed':False,'phone_access':False,'requires':['new Pi paired-checkpoint grant','successful released actual phone capture','fresh run ID'],'limits':{'memory_max_GiB':12,'swap_max_GiB':2,'CPU_cores':2,'total_seconds':1800,'work_seconds':1770,'new_output_disk_GiB':1,'trace_cap_MiB':64},'static_dequant_cache':'none; memory-map codes lazily, one F32 operand with1M-element dequant tiles; last-consumer activation release','HTP_caches_imported':False},indent=2));return 0
    if not a.run_id or not a.pi_grant or not a.phone_collection or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9._-]{0,69}',a.run_id) or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9._-]{0,69}',a.pi_grant):p.error('explicit new grant/run/capture required')
    validate_phone(a.phone_collection);host_sources=assert_host_sources()
    ROOT.mkdir(parents=True,exist_ok=True);grants=ROOT/'grants';grants.mkdir(exist_ok=True)
    with (grants/(a.pi_grant+'.json')).open('x') as f:json.dump({'run_id':a.run_id,'phone_collection_sha256':digest(a.phone_collection)},f)
    root=ROOT/a.run_id;root.mkdir(mode=0o700);(root/'home').mkdir();(root/'tmp').mkdir();unit='gemma-paired-host-'+a.run_id
    save(root/'grant.json',{'grant_id':a.pi_grant,'unit':unit,'phone_collection':str(a.phone_collection.resolve()),'phone_collection_sha256':digest(a.phone_collection),'host_source_bindings':host_sources})
    cmd=['systemd-run','--user','--wait','--collect','--unit='+unit,'--property=MemoryHigh=10G','--property=MemoryMax=12G','--property=MemorySwapMax=2G','--property=CPUQuota=200%','--property=TasksMax=128','--property=Nice=15','--property=IOSchedulingClass=idle','--property=RuntimeMaxSec=1800','--property=TimeoutStopSec=20','--property=KillMode=control-group','--property=OOMPolicy=kill','--property=StandardOutput=append:'+str(root/'guard.stdout'),'--property=StandardError=append:'+str(root/'guard.stderr'),'/usr/bin/env','-i','PATH=/usr/bin:/bin','HOME='+str(root/'home'),'TMPDIR='+str(root/'tmp'),'PYTHONDONTWRITEBYTECODE=1','OPENBLAS_NUM_THREADS=1','OMP_NUM_THREADS=1',str(VENV),'-B',str(Path(__file__).resolve()),'--internal-guard',str(root)]
    save(root/'launch-command.json',cmd)
    with (root/'service.stdout').open('xb') as so,(root/'service.stderr').open('xb') as se:proc=subprocess.run(cmd,stdout=so,stderr=se,close_fds=True)
    save(root/'service-exit.json',{'actual_service_exit':proc.returncode});return proc.returncode


if __name__=='__main__':raise SystemExit(main())
