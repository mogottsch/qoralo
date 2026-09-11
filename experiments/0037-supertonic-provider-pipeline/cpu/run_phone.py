#!/usr/bin/env python3
"""One guarded Android provider-pipeline run; promptly pull completed chunks.

No app changes, remote transcript text, auto playback, retries, or new generation.
"""
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

ROOT=Path(__file__).resolve().parents[3]
EXP=ROOT/'experiments/0037-supertonic-provider-pipeline'
SERIAL='R5CW81PR8SY'


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()


def main():
    if os.environ.get('PI_PHONE_SLOT')!='yes':raise RuntimeError('Pi must schedule behind Janek app work; PI_PHONE_SLOT=yes required')
    bundle=EXP/'.local/common/bundle';manifest=json.loads((bundle/'manifest.json').read_text())
    frozen=json.loads((EXP/'protocol/freeze.json').read_text())
    if digest(bundle/'manifest.json')!=frozen['bundle_manifest_sha256']:raise RuntimeError('bundle freeze changed')
    for name,expected in frozen['bundle_files_sha256'].items():
        if digest(bundle/name)!=expected:raise RuntimeError('frozen input bytes changed')
    for name,binding in frozen['cpu_original_model_bindings'].items():
        if digest(EXP/'.local/cpu/stage/models'/(name+'.onnx'))!=binding['sha256']:raise RuntimeError('original CPU graph changed')
    label=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-full'
    out=EXP/'.local/cpu'/label;out.mkdir(parents=True,exist_ok=False);(out/'available-chunks').mkdir()
    remote='/data/local/tmp/exp0037-cpu-'+label
    lock=open(ROOT/'artifacts/locks/phone.lock','a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    def adb(*args,timeout=60):return subprocess.run(['adb','-s',SERIAL,*args],capture_output=True,text=True,timeout=timeout)
    def shell(cmd,timeout=60):
        r=adb('shell',cmd,timeout=timeout)
        if r.returncode:raise RuntimeError('adb shell failed: '+r.stderr[:200])
        return r.stdout.strip()
    identity={k:shell('getprop '+v) for k,v in [('model','ro.product.model'),('soc','ro.soc.model'),('abi','ro.product.cpu.abi')]}
    if identity!={'model':'SM-S918B','soc':'SM8550','abi':'arm64-v8a'}:raise RuntimeError('wrong phone')
    (out/'identity.json').write_text(json.dumps(identity,indent=2)+'\n')
    processes=shell('ps -A -o PID,ARGS');(out/'processes-before.txt').write_text(processes)
    if re.search(r'qnn-net-run|ort-qnn|e2e-runner|/data/local/tmp/[^\n]*(?:runner|probe)',processes):raise RuntimeError('live benchmark conflict; yield without stopping it')
    before=shell('dumpsys thermalservice; dumpsys battery; cat /proc/meminfo');(out/'thermal-before.txt').write_text(before)
    def number(text,key):
        m=re.search(r'^\s*'+key+r':\s*(\d+)',text,re.M);return int(m.group(1)) if m else None
    if (number(before,'MemAvailable') or 0)<3*1024*1024:raise RuntimeError('need3GiB initial available memory')
    temp=number(before,'temperature')
    if temp is None or temp>=420:raise RuntimeError('missing/high initial battery temperature')
    stage=out/'stage';shutil.copytree(EXP/'.local/cpu/stage',stage);(stage/'bundle').mkdir()
    for name in ['runner-config.txt','manifest.json','style_dp.f32','style_ttl.f32','current_steps.f32','total_steps.f32','noise_stream.f32']:shutil.copyfile(bundle/name,stage/'bundle'/name)
    for chunk in manifest['chunks']:
        name=f'{chunk["index"]:03d}';(stage/'bundle'/name).mkdir()
        for filename in ['text_ids.i64','text_mask.f32']:shutil.copyfile(bundle/name/filename,stage/'bundle'/name/filename)
    hashes={str(p.relative_to(stage)):digest(p) for p in stage.rglob('*') if p.is_file()};(out/'stage-hashes.json').write_text(json.dumps(hashes,indent=2)+'\n')
    shell(f"mkdir '{remote}'");p=adb('push',str(stage)+'/.',remote+'/',timeout=180);(out/'push.log').write_text(p.stdout+p.stderr)
    if p.returncode:raise RuntimeError('stage transfer failed')
    remote_hashes=shell(f"cd '{remote}'; find . -type f -exec sha256sum {{}} +");(out/'phone-stage-sha256.txt').write_text(remote_hashes+'\n')
    observed={line.split(None,1)[1].removeprefix('./'):line.split(None,1)[0] for line in remote_hashes.splitlines()}
    if observed!=hashes:raise RuntimeError('remote stage hashes mismatch')
    shell(f"chmod 755 '{remote}/runner'")
    cmd=f"cd '{remote}'; export LD_LIBRARY_PATH='{remote}/lib'; ./runner models bundle output >stdout.txt 2>stderr.log & p=$!; echo $p >run.pid; wait $p; rc=$?; echo $rc >exit-code; exit $rc"
    (out/'command.txt').write_text(cmd+'\n');start=time.monotonic();proc=subprocess.Popen(['adb','-s',SERIAL,'shell',cmd],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    samples=[];transfers=[];pulled=set();aborted=None;pid=None
    def pull_chunks():
        listing=shell(f"find '{remote}/output' -maxdepth 1 -name 'chunk-*.wav' 2>/dev/null || true")
        for path in sorted(listing.splitlines()):
            name=Path(path).name
            if not re.fullmatch('chunk-[0-9]{3}\\.wav',name) or name in pulled:continue
            t=time.monotonic();p=adb('pull',path,str(out/'available-chunks'/name),timeout=30)
            if p.returncode:continue
            transfers.append({'chunk_file':name,'host_ready_since_command_seconds':time.monotonic()-start,'transfer_seconds':time.monotonic()-t,'sha256':digest(out/'available-chunks'/name)})
            pulled.add(name)
            (out/'chunk-availability.json').write_text(json.dumps(transfers,indent=2)+'\n')
    while proc.poll() is None:
        time.sleep(1)
        try:
            value=shell(f"cat '{remote}/run.pid'")
            if value.isdigit():pid=int(value)
            status=shell(f"cat /proc/{pid}/status 2>/dev/null; grep MemAvailable /proc/meminfo; dumpsys battery | grep temperature") if pid else ''
            sample={'elapsed_seconds':time.monotonic()-start,'rss_kib':number(status,'VmRSS'),'hwm_kib':number(status,'VmHWM'),'available_kib':number(status,'MemAvailable'),'battery_temperature_tenths_c':number(status,'temperature')};samples.append(sample)
            if (sample['rss_kib'] or 0)>4*1024*1024:aborted='RSS>4GiB'
            if sample['available_kib'] is not None and sample['available_kib']<600*1024:aborted='MemAvailable<600MiB'
            if (sample['battery_temperature_tenths_c'] or 0)>=450:aborted='battery>=45C'
            if time.monotonic()-start>1820:aborted='wall timeout'
            if aborted and pid:shell(f'kill -TERM {pid}');break
            pull_chunks()
        except Exception as e:
            samples.append({'elapsed_seconds':time.monotonic()-start,'monitor_error':str(e)})
            if time.monotonic()-start>1850:aborted='monitor timeout';break
    try:stdout,stderr=proc.communicate(timeout=20)
    except subprocess.TimeoutExpired:
        if pid:shell(f'kill -KILL {pid}')
        proc.kill();stdout,stderr=proc.communicate()
    pull_chunks();(out/'adb.log').write_text(stdout+stderr);(out/'monitor.json').write_text(json.dumps(samples,indent=2)+'\n')
    (out/'attempt.json').write_text(json.dumps({'returncode':proc.returncode,'abort_reason':aborted,'command_wall_seconds':time.monotonic()-start,'remote':remote,'host_output':str(out),'chunk_pull_during_inference':True,'host_first_chunk_observed_seconds':transfers[0]['host_ready_since_command_seconds'] if transfers else None},indent=2)+'\n')
    p=adb('pull',remote+'/.',str(out/'phone'),timeout=240);(out/'pull.log').write_text(p.stdout+p.stderr)
    if p.returncode:raise RuntimeError('full pull failed; private remote retained')
    (out/'thermal-after.txt').write_text(shell('dumpsys thermalservice; dumpsys battery; cat /proc/meminfo'))
    if not re.fullmatch('/data/local/tmp/exp0037-cpu-[0-9TZ]+-full',remote):raise RuntimeError('unsafe remote cleanup path')
    shell(f"rm -rf '{remote}'");(out/'cleanup.json').write_text(json.dumps({'removed':remote,'app_touched':False})+'\n');fcntl.flock(lock,fcntl.LOCK_UN);lock.close();print(out)
    if proc.returncode or aborted:raise SystemExit(2)

if __name__=='__main__':main()
