#!/usr/bin/env python3
"""Bounded standalone Android CPU attempt; whole phone.lock, private evidence."""
import argparse
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
EXP=ROOT/'experiments/0036-supertonic-whole-chapter-cpu-htp'
SERIAL='R5CW81PR8SY'

def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['dp','full']);p.add_argument('--latent-extent',type=int,default=0);a=p.parse_args()
    if os.environ.get('PI_PHONE_SLOT')!='yes':p.error('Pi scheduling slot required: PI_PHONE_SLOT=yes')
    label=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+a.action
    out=EXP/'.local/cpu'/label;out.mkdir(parents=True,exist_ok=False)
    remote='/data/local/tmp/exp0036-cpu-'+label
    lock=open(ROOT/'artifacts/locks/phone.lock','a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    def adb(*args,timeout=60):
        return subprocess.run(['adb','-s',SERIAL,*args],capture_output=True,text=True,timeout=timeout)
    def shell(cmd,timeout=60):
        r=adb('shell',cmd,timeout=timeout)
        if r.returncode:raise RuntimeError('adb shell failed: '+r.stderr[:200])
        return r.stdout.strip()
    identity={k:shell('getprop '+prop) for k,prop in [('model','ro.product.model'),('soc','ro.soc.model'),('abi','ro.product.cpu.abi')]}
    if identity!={'model':'SM-S918B','soc':'SM8550','abi':'arm64-v8a'}:raise RuntimeError('wrong phone')
    (out/'identity.json').write_text(json.dumps(identity,indent=2)+'\n')
    (out/'processes-before.txt').write_text(shell('ps -A'))
    (out/'thermal-before.txt').write_text(shell('dumpsys thermalservice; dumpsys battery; cat /proc/meminfo'))
    stage=EXP/'.local/cpu/stage'
    bundle=EXP/'.local/common/input-bundle'
    # Only required files, no raw reference text. Tensors are nonetheless PRIVATE.
    local_stage=out/'stage';local_stage.mkdir();shutil.copy(stage/'runner',local_stage/'runner');shutil.copytree(stage/'lib',local_stage/'lib');(local_stage/'models').mkdir();(local_stage/'bundle').mkdir()
    for name in (['duration'] if a.action=='dp' else ['duration','text','vector','vocoder']):shutil.copy(stage/'models'/(name+'.onnx'),local_stage/'models'/(name+'.onnx'))
    for src in bundle.iterdir():
        if src.suffix in ('.f32','.i64') or src.name=='manifest.json':shutil.copy(src,local_stage/'bundle'/src.name)
    hashes={str(x.relative_to(local_stage)):hashlib.sha256(x.read_bytes()).hexdigest() for x in local_stage.rglob('*') if x.is_file()}
    (out/'stage-hashes.json').write_text(json.dumps(hashes,indent=2)+'\n')
    shell("mkdir '"+remote+"'")
    push=adb('push',str(local_stage)+'/.',remote+'/',timeout=180)
    (out/'push.log').write_text(push.stdout+push.stderr)
    if push.returncode:raise RuntimeError('push failed')
    shell(f"chmod 755 '{remote}/runner'")
    phone_hashes=shell(f"cd '{remote}'; find . -type f -exec sha256sum {{}} +")
    (out/'phone-stage-sha256.txt').write_text(phone_hashes+'\n')
    for line in phone_hashes.splitlines():
        digest,name=line.split(None,1)
        if hashes[name.removeprefix('./')]!=digest:raise RuntimeError('phone hash mismatch')
    cmd=f"cd '{remote}'; export LD_LIBRARY_PATH='{remote}/lib'; ./runner models bundle output {a.action} {a.latent_extent} 4 >stdout.json 2>stderr.log & p=$!; echo $p >run.pid; wait $p; rc=$?; echo $rc >exit-code; exit $rc"
    (out/'command.txt').write_text(cmd+'\n')
    start=time.monotonic();process=subprocess.Popen(['adb','-s',SERIAL,'shell',cmd],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    samples=[];aborted=None;pid=None
    while process.poll() is None:
        time.sleep(2)
        try:
            value=shell(f"cat '{remote}/run.pid'")
            if value.isdigit():pid=int(value)
            status=shell(f"cat /proc/{pid}/status 2>/dev/null; grep MemAvailable /proc/meminfo; dumpsys battery | grep temperature") if pid else ''
            def number(key):
                match=re.search(r'^\s*'+key+r':\s*(\d+)',status,re.M);return int(match.group(1)) if match else None
            sample={'elapsed_seconds':time.monotonic()-start,'rss_kib':number('VmRSS'),'hwm_kib':number('VmHWM'),'available_kib':number('MemAvailable'),'battery_temperature_tenths_c':number('temperature')};samples.append(sample)
            if (sample['rss_kib'] or 0)>4*1024*1024:aborted='RSS >4GiB'
            if sample['available_kib'] is not None and sample['available_kib']<600*1024:aborted='MemAvailable <600MiB'
            if (sample['battery_temperature_tenths_c'] or 0)>=450:aborted='battery >=45C'
            if time.monotonic()-start>(200 if a.action=='dp' else 1820):aborted='wall timeout'
            if aborted and pid:
                shell(f"kill -TERM {pid}");break
        except Exception as error:
            samples.append({'elapsed_seconds':time.monotonic()-start,'monitor_error':str(error)})
            if time.monotonic()-start>1850:
                aborted='monitor timeout';break
    try:stdout,stderr=process.communicate(timeout=20)
    except subprocess.TimeoutExpired:
        if pid:shell(f"kill -KILL {pid}")
        process.kill();stdout,stderr=process.communicate()
    (out/'adb.log').write_text(stdout+stderr)
    (out/'monitor.json').write_text(json.dumps(samples,indent=2)+'\n')
    (out/'attempt.json').write_text(json.dumps({'action':a.action,'returncode':process.returncode,'abort_reason':aborted,'phone_command_wall_seconds':time.monotonic()-start,'remote':remote,'host_output':str(out)},indent=2)+'\n')
    pull=adb('pull',remote+'/.',str(out/'phone'),timeout=240)
    (out/'pull.log').write_text(pull.stdout+pull.stderr)
    if pull.returncode:raise RuntimeError('pull failed; private remote retained')
    (out/'thermal-after.txt').write_text(shell('dumpsys thermalservice; dumpsys battery; cat /proc/meminfo'))
    # Retain first outcomes locally, remove only our uniquely named private phone directory.
    if not re.fullmatch('/data/local/tmp/exp0036-cpu-[0-9TZ]+-(dp|full)',remote):raise RuntimeError('unsafe cleanup path')
    shell(f"rm -rf '{remote}'")
    (out/'cleanup.json').write_text(json.dumps({'removed':remote,'app_touched':False})+'\n')
    fcntl.flock(lock,fcntl.LOCK_UN);lock.close()
    print(str(out))
    if process.returncode or aborted:raise SystemExit(2)

if __name__=='__main__':main()
