#!/usr/bin/env python3
"""One explicitly authorized read-only diagnostic. All captured data stays PRIVATE."""
import fcntl, hashlib, json, os, re, shlex, signal, sys, time, traceback
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from run_wiring_gate import Device, APP, TEST_APP
from duration_phone_guard import close_inherited_fds, IDENTITY, SNAPSHOT, archive_files, validate_snapshot, require
from short_product_preservation import rows

ROOT=Path(__file__).resolve().parents[2]
EXPECTED={APP:'50a367b602d607a9a35d1836258c327b3c78fa9d9f6a835d7575139335937a47', TEST_APP:'8ed6c5e7958d87a677c9e98a0f86c764272a590837ec4b6f30a2c7d4d1f39e04'}

def main():
    close_inherited_fds(); os.umask(0o077)
    out=ROOT/'podcast-app/.local/user-edit-diagnostic'/datetime.now(timezone.utc).strftime('readonly-%Y%m%dt%H%M%Sz')
    out.mkdir(parents=True,exist_ok=False)
    device=Device('/home/moritz/Android/Sdk/platform-tools/adb', IDENTITY['ro.serialno'], out)
    began=time.monotonic(); report={'scope':'newest failed chapter-chat edit read-only diagnostic; all raw data private', 'privateRoot':str(out),'phoneWritesRequested':False,'generationRequested':False,'forceStopRequested':False,'lockAcquired':False}
    def dump(name,obj): (out/name).write_text(json.dumps(obj,indent=2)+'\n')
    def alarm(*_): raise TimeoutError('180s diagnostic deadline; no retry')
    signal.signal(signal.SIGALRM,alarm)
    def installed():
        result={}
        for package,expected in EXPECTED.items():
            path=device.shell('pm path '+package,timeout=10).strip()
            require(re.fullmatch(r'package:/data/app/[^\s]+/base\.apk',path),'unexpected installed APK path')
            value=device.shell('sha256sum '+shlex.quote(path.removeprefix('package:')),timeout=15).split()[0]
            result[package]=value
            require(value==expected,'installed identity differs from final nominated pair')
        return result
    def snapshot(label):
        raw=device.run(['exec-out',SNAPSHOT],timeout=20,binary=True)
        raw.rename(out/(label+'.tar'))
        return archive_files((out/(label+'.tar')).read_bytes())
    def file_pins(files): return {k:{'bytes':len(v),'sha256':hashlib.sha256(v).hexdigest()} for k,v in files.items()}
    with (ROOT/'artifacts/locks/phone.lock').open('a+') as lock:
        os.set_inheritable(lock.fileno(),False)
        try:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);report['lockAcquired']=True;signal.alarm(180)
            props=device.shell('; '.join('getprop '+k for k in IDENTITY),timeout=10).splitlines()
            require(props==list(IDENTITY.values()),'phone identity mismatch');report['deviceIdentityMatched']=True
            report['installedBefore']=installed()
            package_text=device.shell('cmd package list packages -U '+APP,timeout=10)
            package_uids=dict(re.findall(r'package:(\S+) uid:(\d+)',package_text))
            require(set(package_uids)=={APP,TEST_APP},'unexpected package UID inventory')
            report['pidsBefore']=device.shell(f'pidof {APP} {APP}:generation {TEST_APP}',timeout=10,check=False).strip()
            first=snapshot('before-1');second=snapshot('before-2')
            dump('snapshot-pins.json',{'first':file_pins(first),'second':file_pins(second),'identical':first==second})
            require(first==second,'DB/WAL/SHM changed between bounded reads; stop without retry')
            data=rows(first);dump('private-rows.json',data)
            active=[{k:j.get(k) for k in ('id','episodeId','kind','status','phase','currentUnit','totalUnits','updatedAtEpochMs')} for j in data['generation_jobs'] if j['status'] in ('QUEUED','RUNNING')]
            dump('private-active-jobs.json',active)
            report['activeJobCount']=len(active)
            require(not active,'active user job present; no further diagnostics or disturbance')
            report['database']=validate_snapshot(first)
            # UID-filtered read of existing buffers only; never clear or start logging in the app.
            device.run(['logcat','-d','-b','main','-b','system','-b','crash','--uid='+package_uids[APP],'-v','threadtime','-t','20000'],timeout=20)
            log=(out/f'{device.counter:03d}-command.stdout');log.rename(out/'private-app-uid-logcat.txt')
            require((out/'private-app-uid-logcat.txt').stat().st_size<=16*1024*1024,'app log capture exceeds 16MiB bound')
            script='set -eu; if test -d files/episodes; then test -z "$(find files/episodes -type l)"; find files/episodes -type f -exec sha256sum {} \\;; fi'
            device.run(['exec-out',f'run-as {APP} sh -c '+shlex.quote(script)],timeout=20,binary=True)
            (out/f'{device.counter:03d}-command.stdout').rename(out/'private-episode-file-pins.txt')
            report['controlAbsent']=device.shell(f'run-as {APP} sh -c '+shlex.quote('if test -e files/short-product-e2e/active.json; then echo PRESENT; else echo ABSENT; fi'),timeout=10).strip()=='ABSENT'
            window=device.shell('dumpsys window windows',timeout=10)
            (out/'private-window-before.txt').write_text(window)
            focused=[line.strip() for line in window.splitlines() if 'mCurrentFocus=' in line]
            app_focused=len(focused)==1 and (APP+'/') in focused[0]
            report['appFocusedForPrivateCapture']=app_focused
            if app_focused:
                raw=device.run(['exec-out','screencap','-p'],timeout=10,binary=True)
                raw.rename(out/'private-current-app.png')
                following=device.shell('dumpsys window windows',timeout=10)
                (out/'private-window-after.txt').write_text(following)
                report['privateCaptureOwnerStable']=focused==[line.strip() for line in following.splitlines() if 'mCurrentFocus=' in line]
            final=snapshot('after')
            dump('after-pins.json',file_pins(final));report['databaseBytesUnchanged']=first==final
            require(first==final,'app database changed during read-only diagnostic; no further reads/retry')
            report['installedAfter']=installed()
            report['pidsAfter']=device.shell(f'pidof {APP} {APP}:generation {TEST_APP}',timeout=10,check=False).strip()
            report['status']='captured_private_readonly'
        except BaseException as e:
            report['status']='blocked_or_stopped';report['error']=repr(e)
            (out/'private-controller-exception.txt').write_text(traceback.format_exc())
        finally:
            signal.alarm(0)
            if report['lockAcquired']: fcntl.flock(lock,fcntl.LOCK_UN)
            report['lockReleased']=report['lockAcquired'];report['elapsedSeconds']=time.monotonic()-began
            dump('capture-summary.json',report)
    print(json.dumps({k:report[k] for k in ('privateRoot','status','phoneWritesRequested','generationRequested','forceStopRequested','lockAcquired','lockReleased','elapsedSeconds') if k in report}))
if __name__=='__main__': main()
