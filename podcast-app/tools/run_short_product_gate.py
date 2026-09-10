#!/usr/bin/env python3
"""Plan-only separate short product workflow. Never a long-request retry; no pack staging/data clear."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import shlex
import signal
import subprocess
import tarfile
from prepare_wiring_gate import PROJECT, digest
from run_wiring_gate import APP, TEST_APP, Device, DeviceSettings, stop_child
from duration_phone_guard import PhoneGuard, close_inherited_fds, host_identity, validate_snapshot, require
from run_tts_only_gate import capture_conditions
from short_product_preservation import rows, compare, parse_inventory, compare_files, validate_owned_control

CONTRACT_SHA='a39106380003a3a4c7b83c2f45066399e204d8aefade77ec88866f9062eccfc4'
PRIVACY_SHA='a62d204c380a5b2d0c8f7c5bd94729b6f823e18200feed2ebe24fa73962bec3c'
PACKS={'gemma-4-e2b':'9fb627ef9a4eb0ed49056c32bc16f2846e6edf68dc8d854b02af90e24e4e96cd',
       'supertonic-3':'dc4ac737924d7d62e57ff5e166707198095c49e51d77cfed04a44d9e9435952d',
       'supertonic-3-t2048-l2048-parity':'116fda95a907f6dc35bfe7c2144fe2818ed438cc109c1faa3f95cafc2fc84066'}
PRIOR={APP:'4e438b62fc4442e5dfefbed2a26c88f6872fb34989144e04727613e78aaaf8c8',
       TEST_APP:'56be356f5a68d0c415e2980bebca9346ece4972f4a0657f0700064ab683f8739'}


def check_sources(candidate):
    require(digest(PROJECT/'app/src/debug/assets/short-product-e2e/contract.json')==CONTRACT_SHA,'contract changed')
    require(digest(PROJECT/'tools/run_tts_only_gate.py')==PRIVACY_SHA,'privacy dependency changed')
    for name,sha in candidate['controllerSources'].items():require(digest(PROJECT/name)==sha,'controller dependency changed: '+name)


def verify_pack_manifests(device):
    for name,sha in PACKS.items():
        path=f'no_backup/model-packs/{name}/current/manifest.json'
        result=device.shell(f'run-as {APP} sh -c '+shlex.quote(f'test ! -L {path}; sha256sum {path}'))
        require(result.split()[0]==sha,'existing pack mismatch; no replacement/repair/staging')


def routine_closure(device, out):
    receipt={'purpose':'authorized exact-package routine test setup; no data clear','installed':{}}
    for package,sha in PRIOR.items():
        path=device.shell('pm path '+package).strip()
        require(re.fullmatch(r'package:/data/app/[^\s]+/base\.apk',path),'unexpected existing package path')
        actual=device.shell('sha256sum '+shlex.quote(path.removeprefix('package:'))).split()[0]
        require(actual==sha,'unexpected previous installed APK; no closure/install')
        receipt['installed'][package]={'apkSha256':actual}
    receipt['uids']=device.shell(f'cmd package list packages -U {APP}')
    require(set(re.findall(r'package:([^ ]+) uid:',receipt['uids']))=={APP,TEST_APP},'unexpected package UID inventory')
    receipt['pidsBefore']=device.shell(f'pidof {APP} {APP}:generation {TEST_APP}',check=False)
    (out/'routine-closure-before.json').write_text(json.dumps(receipt,indent=2))
    return receipt


def private_inventory(device,out,label):
    directory=out/'.private-user-files';directory.mkdir(mode=0o700,exist_ok=True)
    count=device.counter+1
    script='if test -d files/episodes; then test -z "$(find files/episodes -type l)"; find files/episodes -type f -exec sha256sum {} \\;; fi'
    try:device.run(['exec-out',f'run-as {APP} sh -c '+shlex.quote('set -e; '+script)],timeout=60,binary=True)
    finally:
        p=out/f'{count:03d}-command.stdout'
        if p.exists():p.rename(directory/(label+'.stdout'))
    return parse_inventory((directory/(label+'.stdout')).read_bytes())


def disarm_owned_control(device,out,run,owned,original):
    marker='files/short-product-e2e/active.json'
    private=out/'.private-control';private.mkdir(mode=0o700,exist_ok=True)
    counter=device.counter+1
    script=f'if test -L {marker}; then printf "UNSAFE\\n"; elif test -f {marker}; then cat {marker}; elif test ! -e {marker}; then printf "ABSENT\\n"; else printf "UNSAFE\\n"; fi'
    try:device.run(['exec-out',f'run-as {APP} sh -c '+shlex.quote(script)],timeout=30,binary=True)
    finally:
        p=out/f'{counter:03d}-command.stdout'
        if p.exists():p.rename(private/'before.stdout')
    current=(private/'before.stdout').read_bytes()
    if current==b'ABSENT\n':return {'controlAbsent':True,'hostRemovalPerformed':False}
    sha=validate_owned_control(current,original,run,owned,CONTRACT_SHA)
    # App/test/generation already stopped. Recheck current bytes immediately before removing ONLY this file.
    script=f'set -e; test ! -L {marker}; test "$(sha256sum {marker} | cut -d " " -f 1)" = {sha}; rm {marker}; test ! -e {marker}; test ! -L {marker}; printf "ABSENT\\n"'
    observed=device.shell(f'run-as {APP} sh -c '+shlex.quote(script))
    require(observed.strip()=='ABSENT','owned control disarm absence unproven')
    return {'controlAbsent':True,'hostRemovalPerformed':True,'matchedOriginalSha256':sha,'runId':run,'episodeId':owned}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('candidate','output'):parser.add_argument('--'+key,type=Path,required=True)
    parser.add_argument('--run-id',required=True);parser.add_argument('--execute',action='store_true')
    for key in ('candidate','host-guard','controller'):parser.add_argument('--approved-'+key+'-sha256')
    parser.add_argument('--adb',default='/home/moritz/Android/Sdk/platform-tools/adb');parser.add_argument('--serial',default='R5CW81PR8SY')
    args=parser.parse_args();value=json.loads(args.candidate.read_text())
    require(re.fullmatch(r'short-product-[a-z0-9-]{1,64}',args.run_id),'unsafe run ID')
    require(value['kind']=='short-production-plumbing' and not value['sourceDirty'] and value['contractSha256']==CONTRACT_SHA,'wrong candidate')
    check_sources(value)
    for key in ('app','test'):
        p=Path(value[key]['path']);require(p.stat().st_size==value[key]['bytes'] and digest(p)==value[key]['sha256'],'APK changed')
    if not args.execute:
        print(json.dumps({'mode':'plan_only','adbUsed':False,'logicalGemmaRequests':5,'wholeBriefChapters':2,'hostInstrumentationSeconds':930,
                          'packStaging':False,'dataClear':False,'longReadiness':False,'candidateSha256':digest(args.candidate)}));return
    require(os.environ.get('PODCAST_PHONE_PRIORITY')=='approved' and args.approved_candidate_sha256==digest(args.candidate)
            and args.approved_host_guard_sha256==host_identity()['sha256'] and args.approved_controller_sha256==digest(Path(__file__)),
            'exact independent candidate review and separate Pi phone slot required')
    os.umask(0o077);args.output.mkdir(parents=True,exist_ok=False);out=args.output
    lock=(PROJECT.parent/'artifacts/locks/phone.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);os.set_inheritable(lock.fileno(),False)
    device=Device(args.adb,args.serial,out);guard=PhoneGuard(device,out,args.candidate,args.approved_candidate_sha256,args.approved_host_guard_sha256)
    settings=DeviceSettings(device.shell);logs=None;identity=False;closure_allowed=False;launched=False;before=None;files_before=None;owned=None;original_control=None
    cleanup={'errors':[],'settingsErrors':[],'packagesAndDataRetained':True,'scratchCreated':False}
    (out/'candidate.json').write_text(json.dumps(value,indent=2));(out/'host-identity.json').write_text(json.dumps(host_identity(),indent=2))
    def interrupt(signum,frame):raise InterruptedError('signal; first attempt stops, cleanup only')
    signal.signal(signal.SIGINT,interrupt);signal.signal(signal.SIGTERM,interrupt)
    try:
        guard.identity();identity=True;receipt=routine_closure(device,out);closure_allowed=True
        device.shell(f'am force-stop {APP}; am force-stop {TEST_APP}');guard.idle()
        receipt['forceStoppedOnly']=[APP,TEST_APP];(out/'routine-closure.json').write_text(json.dumps(receipt,indent=2))
        settings.capture();capture_conditions(device,out,'before');verify_pack_manifests(device)
        check_sources(value);guard.checkpoint('before-app-install')
        before=guard.snapshot('preservation-before',1);files_before=private_inventory(device,out,'before')
        device.run(['install','-r','-t',value['app']['path']],timeout=180)
        check_sources(value);guard.checkpoint('before-test-install');device.run(['install','-r','-t',value['test']['path']],timeout=180)
        with (out/'logcat.txt').open('wb') as stdout,(out/'logcat.stderr').open('wb') as stderr:
            logs=subprocess.Popen(device.prefix+['logcat','-v','threadtime','-T','1'],stdout=stdout,stderr=stderr,start_new_session=True,close_fds=True)
        check_sources(value);guard.checkpoint('before-instrument')
        command=f'am instrument -w -r -e class dev.vibevoice.podcast.e2e.ShortProductE2eTest -e shortProductApproved {CONTRACT_SHA} -e shortProductRunId {args.run_id}'
        command+=f" -e appApkSha256 {value['app']['sha256']} -e testApkSha256 {value['test']['sha256']} {TEST_APP}/androidx.test.runner.AndroidJUnitRunner"
        launched=True;result=device.shell(command,timeout=930)
        (out/'instrumentation-summary.json').write_text(json.dumps({'ok':'OK (' in result and 'FAILURES!!!' not in result,'longReadiness':False}))
        require('OK (' in result and 'FAILURES!!!' not in result,'short product instrumentation failed; no retry')
    except BaseException as error:
        (out/'controller-failure.json').write_text(json.dumps({'error':repr(error),'launched':launched}));raise
    finally:
        signal.signal(signal.SIGINT,signal.SIG_IGN);signal.signal(signal.SIGTERM,signal.SIG_IGN);device.enforce_quota=False
        if closure_allowed:
            try:
                device.shell(f'am force-stop {APP}; am force-stop {TEST_APP}');guard.idle();cleanup['allActualPidsAbsent']=True
            except Exception as error:cleanup['errors'].append({'phase':'stop/pid','error':repr(error)})
        if launched:
            try:
                p=device.run(['exec-out','run-as',APP,'tar','-cf','-',f'files/short-product-e2e/{args.run_id}'],timeout=120,binary=True)
                archive=out/'private-run-evidence.tar';p.rename(archive)
                with tarfile.open(archive) as tar:
                    name=f'files/short-product-e2e/{args.run_id}/ownership.json'
                    if name in tar.getnames():owned=json.load(tar.extractfile(name))['episodeId']
                    control=f'files/short-product-e2e/{args.run_id}/control-original.json'
                    if control in tar.getnames():original_control=tar.extractfile(control).read()
                if owned:
                    require(re.fullmatch(r'[a-zA-Z0-9-]+',owned),'unsafe owned episode ID')
                    p=device.run(['exec-out','run-as',APP,'tar','-cf','-',f'files/episodes/{owned}'],timeout=120,binary=True)
                    p.rename(out/'owned-episode-artifacts.tar')
            except Exception as error:cleanup['errors'].append({'phase':'pull','error':repr(error)})
        if launched:
            try:
                require(cleanup.get('allActualPidsAbsent'),'cannot disarm while process absence is unproven')
                receipt=disarm_owned_control(device,out,args.run_id,owned,original_control)
                cleanup['controlAbsent']=receipt['controlAbsent'];(out/'control-disarm.json').write_text(json.dumps(receipt,indent=2))
            except Exception as error:cleanup['errors'].append({'phase':'owned-control-disarm','error':repr(error)})
        if identity and before is not None:
            try:
                after=guard.snapshot('preservation-after',1);second=guard.snapshot('preservation-after',2)
                require(after==second,'post-run DB snapshots unstable')
                validate_snapshot(after)
                report=compare(rows(before),rows(after),owned)
                report['artifacts']=compare_files(files_before,private_inventory(device,out,'after'),owned)
                report['ownedEpisodeId']=owned;report['privateSnapshots']='.private-db and .private-user-files; never publish full raw'
                (out/'preservation.json').write_text(json.dumps(report,indent=2))
            except Exception as error:cleanup['errors'].append({'phase':'preservation','error':repr(error)})
        if closure_allowed:
            try:verify_pack_manifests(device);capture_conditions(device,out,'after')
            except Exception as error:cleanup['errors'].append({'phase':'pack/conditions','error':repr(error)})
        cleanup['settingsErrors']=settings.restore()+guard.readback_settings()
        if logs is not None:
            try:stop_child(logs)
            except Exception as error:cleanup['errors'].append({'phase':'logcat','error':repr(error)})
        (out/'cleanup.json').write_text(json.dumps(cleanup,indent=2));fcntl.flock(lock,fcntl.LOCK_UN);lock.close()
        if cleanup['errors'] or cleanup['settingsErrors']:raise RuntimeError('cleanup/preservation incomplete; retain all evidence')


if __name__=='__main__':
    close_inherited_fds();main()
