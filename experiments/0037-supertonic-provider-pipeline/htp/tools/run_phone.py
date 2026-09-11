#!/usr/bin/env python3
"""One scheduled standalone HTP chapter, full lock and owned-resource cleanup.

Read-only live APK/job checks; no app stop/start/install/data writes. Complete
chunk WAVs are pulled during inference without playback. No retries/calibration.
"""
import argparse
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import time
from materialize import REPO, ROOT, sha

SERIAL = 'R5CW81PR8SY'
APP = 'dev.vibevoice.podcast.internal'
TEST_APP = APP+'.test'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stage', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    if os.environ.get('PHONE_SLOT_SCHEDULED') != 'yes':
        p.error('Pi must schedule the actual slot; PHONE_SLOT_SCHEDULED=yes required')
    for path in [args.stage, args.output]:
        if not path.resolve().is_relative_to((ROOT/'.local').resolve()):
            p.error('stage/output must be private HTP paths')
    args.stage=args.stage.resolve(); args.output=args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=False)
    out=args.output; (out/'available-chunks').mkdir()
    label=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+f'-{os.getpid()}'
    remote='/data/local/tmp/supertonic-0037-htp-'+label
    if not re.fullmatch(r'/data/local/tmp/supertonic-0037-htp-[0-9TZ]+-[0-9]+', remote):
        raise ValueError('unsafe owned remote path')
    q=shlex.quote
    env=dict(os.environ); env.pop('ADB_LIBUSB',None)
    def adb(*words, timeout=60, binary=False):
        return subprocess.run(['/usr/bin/adb','-s',SERIAL,*words], stdin=subprocess.DEVNULL,
            capture_output=True, text=not binary, timeout=timeout, env=env, close_fds=True)
    def shell(command, timeout=60):
        r=adb('shell',command,timeout=timeout)
        if r.returncode:
            raise RuntimeError('adb shell failed: '+r.stderr[:200])
        return r.stdout.strip()
    def write(name, value):
        (out/name).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
    def hashes():
        return {str(f.relative_to(args.stage)):sha(f) for f in args.stage.rglob('*') if f.is_file()}
    def identity():
        observed={key:shell('getprop '+key) for key in ['ro.product.model','ro.soc.model','ro.product.cpu.abi']}
        if observed!={'ro.product.model':'SM-S918B','ro.soc.model':'SM8550','ro.product.cpu.abi':'arm64-v8a'}:
            raise RuntimeError('wrong phone')
        return observed
    def app_idle():
        r=adb('shell',f'pidof {APP} {APP}:generation {TEST_APP}')
        if r.returncode!=1 or r.stdout.strip() or r.stderr.strip():
            raise RuntimeError('app/test PID is live or idle state unproven; yield without stopping it')
    def apks():
        observed={}
        for package in [APP,TEST_APP]:
            paths=shell('pm path '+package).splitlines()
            if len(paths)!=1 or not paths[0].startswith('package:/data/app/'):
                raise RuntimeError('installed APK identity unavailable')
            path=paths[0].removeprefix('package:')
            observed[package]=dict(path=path,sha256=shell('sha256sum '+q(path)).split()[0])
        return observed
    # Reuse only the existing host-side archive/WAL/schema validator. Device DB
    # is never opened in SQLite, checkpointed or repaired. Raw views stay private.
    sys.path.insert(0,str(REPO/'podcast-app/tools'))
    import duration_phone_guard as guard
    private=out/'.private-db'; private.mkdir(mode=0o700)
    def snapshot(phase):
        app_idle(); values=[]
        for i in [1,2]:
            r=adb('exec-out',guard.SNAPSHOT,timeout=30,binary=True)
            if r.returncode:
                raise RuntimeError('read-only app snapshot failed')
            path=private/f'{phase}-{i}.tar'; path.write_bytes(r.stdout); path.chmod(0o600)
            values.append(guard.archive_files(r.stdout))
        if values[0]!=values[1]:
            raise RuntimeError('app DB changed between read-only snapshots; yield')
        old_temp=tempfile.tempdir
        try:
            tempfile.tempdir=str(private)
            state=guard.validate_snapshot(values[0])
        finally:
            tempfile.tempdir=old_temp
        app_idle()
        metadata={name:dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest()) for name,data in values[0].items()}
        write('app-state-'+phase+'.json',dict(files=metadata,state=state,guard_source_sha256=sha(Path(guard.__file__))))
        return metadata
    def bounds():
        text=shell("awk '/^MemAvailable:/{print $2}' /proc/meminfo")
        temp=shell("dumpsys battery | awk '/^[[:space:]]*temperature:/{if(!found){t=$2;found=1}} END{print t}'")
        if not text.isdigit() or not temp.isdigit():
            raise RuntimeError('memory/temperature observation missing')
        observed=dict(available_kib=int(text),battery_temperature_tenths_c=int(temp))
        if int(text)<3584*1024 or int(temp)>=420:
            raise RuntimeError('need>=3.5GiB available and battery<42C')
        return observed
    def stop_owned():
        command=f"if [ -f {q(remote+'/evidence/runner.pid')} ]; then p=$(cat {q(remote+'/evidence/runner.pid')}); " \
            f"if [ \"$(readlink /proc/$p/exe)\" = {q(remote+'/runner')} ]; then kill -TERM $p; sleep 2; " \
            f"[ \"$(readlink /proc/$p/exe)\" != {q(remote+'/runner')} ] || kill -KILL $p; " \
            f"sleep 1; [ \"$(readlink /proc/$p/exe)\" != {q(remote+'/runner')} ] || exit 97; fi; fi"
        r=adb('shell',command,timeout=15)
        (out/'owned-process-cleanup.log').write_text(r.stdout+r.stderr)
        if r.returncode:
            raise RuntimeError('owned process cleanup not verified')
    attempt=dict(status='started',remote=remote,app_modified_by_controller=False,auto_playback=False,
                 min_initial_available_kib=3584*1024,native_as_limit_bytes=5<<30,native_rss_limit_kib=3*1024*1024,
                 min_running_available_kib=600*1024,initial_battery_ceiling_c=42,running_battery_ceiling_c=45,
                 native_alarm_seconds=1800,host_timeout_seconds=1840,host_chunk_poll_seconds=1)
    created=False; launched=False; proc=None; transfers=[]; pulled=set(); first_apks=None; first_db=None
    started=None; error=None; cleanup_error=None
    with (REPO/'artifacts/locks/phone.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:
            subprocess.run(['sha256sum','-c','stage-manifest.sha256'],cwd=args.stage,
                stdin=subprocess.DEVNULL,capture_output=True,check=True,timeout=60)
            expected=hashes(); write('local-stage-hashes.json',expected)
            provenance=json.loads((args.stage/'stage-provenance.json').read_text())
            freeze=json.loads((ROOT.parent/'protocol/freeze.json').read_text())
            if provenance['frozen_bundle_manifest_sha256']!=freeze['bundle_manifest_sha256']:
                raise RuntimeError('stage belongs to a different provider input freeze')
            attempt['controller_sha256']=sha(Path(__file__))
            manifest_names={line.split(None,1)[1] for line in (args.stage/'stage-manifest.sha256').read_text().splitlines()}
            if manifest_names != set(expected)-{'stage-manifest.sha256'}:
                raise RuntimeError('unmanifested stage payload')
            write('identity.json',identity())
            processes=shell('ps -A -o PID,ARGS'); (out/'processes-before.txt').write_text(processes+'\n')
            if re.search(r'llama-bench|qnn-net-run|/data/local/tmp/[^\n]*(?:runner|probe)',processes):
                raise RuntimeError('another benchmark process is live; yield')
            first_apks=apks(); write('installed-apks-before.json',first_apks)
            first_db=snapshot('before-stage')
            write('preflight-bounds.json',bounds())
            (out/'thermal-before.txt').write_text(shell('dumpsys thermalservice')+'\n')
            available=int(shell('df -Pk /data/local/tmp').splitlines()[-1].split()[3])
            needed=sum(f.stat().st_size for f in args.stage.rglob('*') if f.is_file())//1024+512*1024
            if available<needed:
                raise RuntimeError('insufficient private-stage disk headroom')
            shell('mkdir '+q(remote)); created=True
            r=adb('push',str(args.stage)+'/.',remote+'/',timeout=180)
            (out/'push.log').write_text(r.stdout+r.stderr)
            if r.returncode:
                raise RuntimeError('stage transfer failed')
            observed=shell(f'cd {q(remote)} && find . -type f -exec sha256sum {{}} +')
            (out/'phone-stage-sha256.txt').write_text(observed+'\n')
            actual={line.split(None,1)[1].removeprefix('./'):line.split(None,1)[0] for line in observed.splitlines()}
            if actual!=expected:
                raise RuntimeError('remote stage mismatch')
            shell(f'chmod 755 {q(remote+"/runner")} {q(remote+"/run_remote.sh")}')
            if snapshot('before-run')!=first_db or apks()!=first_apks:
                raise RuntimeError('app data/APK changed during stage; do not run')
            write('dispatch-bounds.json',bounds())
            command=f'cd {q(remote)} && sh ./run_remote.sh'
            (out/'command.txt').write_text(command+'\n')
            started=time.monotonic()
            proc=subprocess.Popen(['/usr/bin/adb','-s',SERIAL,'shell',command],stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env,close_fds=True)
            launched=True
            def pull_chunks():
                listing=shell(f'find {q(remote+"/evidence/run")} -maxdepth 1 -name "chunk-*.wav" 2>/dev/null || true; '
                    f'if [ -f {q(remote+"/evidence/run/chapter.wav")} ]; then echo __CHAPTER_COMPLETE__; fi')
                chapter_done='__CHAPTER_COMPLETE__' in listing.splitlines()
                for path in sorted(listing.splitlines()):
                    name=Path(path).name
                    if not re.fullmatch(r'chunk-[0-9]{3}\.wav',name) or name in pulled:
                        continue
                    t=time.monotonic(); r=adb('pull',path,str(out/'available-chunks'/name),timeout=30)
                    if r.returncode:
                        raise RuntimeError('complete chunk pull failed; no inference retry')
                    transfers.append(dict(chunk_file=name,host_ready_since_command_seconds=time.monotonic()-started,
                        transfer_seconds=time.monotonic()-t,sha256=sha(out/'available-chunks'/name),
                        chapter_complete_on_device_before_pull=chapter_done))
                    pulled.add(name); write('chunk-availability.json',transfers)
            while proc.poll() is None:
                time.sleep(1)
                app_idle() # If user starts the app, stop ONLY our owned runner.
                if time.monotonic()-started>1840:
                    raise TimeoutError('native run wall bound')
                pull_chunks()
            stdout,stderr=proc.communicate(timeout=10)
            (out/'adb-stdout.log').write_text(stdout); (out/'adb-stderr.log').write_text(stderr)
            pull_chunks()
            attempt.update(status='completed' if proc.returncode==0 else 'native_failed',returncode=proc.returncode,
                command_wall_seconds=time.monotonic()-started,completed_chunks_pulled=len(transfers),
                chunks_pulled_before_chapter_file=sum(not x['chapter_complete_on_device_before_pull'] for x in transfers),
                first_host_chunk_available_seconds=transfers[0]['host_ready_since_command_seconds'] if transfers else None)
            if proc.returncode:
                raise RuntimeError('first native route failed; preserve result, no retry')
        except BaseException as e:
            error=e; attempt.update(status='failed',error_type=type(e).__name__,error=str(e))
        finally:
            try:
                if created:
                    stop_owned()
                    if proc and proc.poll() is None:
                        try:
                            stdout,stderr=proc.communicate(timeout=20)
                        except subprocess.TimeoutExpired:
                            proc.kill(); stdout,stderr=proc.communicate(timeout=10)
                        (out/'adb-final.log').write_text(stdout+stderr)
                    if launched:
                        r=adb('pull',remote+'/evidence',str(out/'evidence'),timeout=180)
                        (out/'pull.log').write_text(r.stdout+r.stderr)
                        if r.returncode:
                            raise RuntimeError('evidence retrieval failed; owned private remote retained')
                    shell(f'rm -rf {q(remote)} && test ! -e {q(remote)}')
                    attempt['remote_removed']=True
                if first_apks is not None:
                    after=apks(); write('installed-apks-after.json',after)
                    attempt['installed_apks_unchanged']=after==first_apks
                    if after!=first_apks:
                        raise RuntimeError('installed APK changed externally; no restoration attempted')
                if first_db is not None:
                    after_db=snapshot('after')
                    attempt['app_database_files_unchanged']=after_db==first_db
                    if after_db!=first_db:
                        raise RuntimeError('app DB changed externally; no restoration attempted')
                (out/'thermal-after.txt').write_text(shell('dumpsys thermalservice')+'\n')
            except BaseException as e:
                cleanup_error=e; attempt.update(cleanup_error=str(e))
            write('attempt.json',attempt)
    print(out)
    if error is not None:
        raise error
    if cleanup_error is not None:
        raise cleanup_error


if __name__ == '__main__':
    main()
