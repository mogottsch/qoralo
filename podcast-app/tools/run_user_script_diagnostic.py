#!/usr/bin/env python3
"""One bounded normal-input SCRIPT reproduction. Every output/raw receipt is PRIVATE.
No permission prompt loop: --execute is an explicit invocation of the assigned repair.
No device writes until exact identity, stable known DB and no active user jobs are proved.
"""
import argparse, fcntl, hashlib, io, json, os, re, shlex, signal, subprocess, tarfile, time
from pathlib import Path
from prepare_wiring_gate import PROJECT, digest
from run_wiring_gate import APP, TEST_APP, Device
from duration_phone_guard import PhoneGuard, close_inherited_fds, host_identity, require, validate_snapshot
from short_product_preservation import rows, compare, compare_files
from run_short_product_gate import private_inventory


def compare_script(before, after, owned):
    result = compare(before, after, owned)
    # Narrow the old two-route comparison to SCRIPT only; no TTS/catalog/playback/audio side effects.
    for table in ('chapter_audio', 'playback_state', 'agent_messages'):
        require(before[table] == after[table], 'script diagnostic changed '+table)
    old_catalog={r['id']:r for r in before['installed_models']};new_catalog={r['id']:r for r in after['installed_models']}
    require({k:v for k,v in old_catalog.items() if k!='gemma-4-e2b'}=={k:v for k,v in new_catalog.items() if k!='gemma-4-e2b'}, 'non-Gemma catalog changed')
    old_jobs={j['id'] for j in before['generation_jobs']}
    added=[j for j in after['generation_jobs'] if j['id'] not in old_jobs]
    require(len(added)<=1 and all(j['episodeId']==owned and j['kind']=='SCRIPT' for j in added), 'extra/non-SCRIPT job')
    result['newScriptJobs']=len(added);result['newTtsJobs']=0
    result['allowedGlobalChanges']='only exact verified Gemma catalog upsert'
    return result


def validate_owner(ownership, identity, run, before_ids, candidate, original_episode, original_job):
    owned=ownership.get('episodeId')
    require(ownership.get('runId')==run and ownership.get('createdThroughMainUi') is True,'unbound ownership receipt')
    require(isinstance(owned,str) and re.fullmatch(r'[a-f0-9]{8}(-[a-f0-9]{4}){3}-[a-f0-9]{12}',owned) and owned not in before_ids,'stale/pre-existing owned episode')
    require(identity.get('appApkSha256')==candidate['app']['sha256'] and identity.get('testApkSha256')==candidate['test']['sha256'],'driver APK identity mismatch')
    require(identity.get('originalEpisodeId')==original_episode and identity.get('originalJobId')==original_job,'driver original case mismatch')
    return owned


def require_safe_closure(state, owned):
    require(all(j['status'] in ('QUEUED','RUNNING','COMPLETE','FAILED') for j in state['generation_jobs']),'unknown job status; no force-stop')
    active=[j for j in state['generation_jobs'] if j['status'] in ('QUEUED','RUNNING')]
    require(all(owned and j['episodeId']==owned and j['kind']=='SCRIPT' for j in active),'active USER job; no force-stop')


def independent_cleanup(actions, errors):
    """Observation failure cannot skip safety closure or independent file/DB observations."""
    for phase, action in actions:
        try: action()
        except BaseException as error: errors.append({'phase':phase,'error':repr(error)})


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--run-id',required=True);parser.add_argument('--original-episode',required=True)
    parser.add_argument('--original-job',required=True);parser.add_argument('--execute',action='store_true')
    parser.add_argument('--revision-id');parser.add_argument('--revision-sha256');parser.add_argument('--edit-instruction-sha256')
    args=parser.parse_args();candidate=json.loads(args.candidate.read_text());candidate_sha=digest(args.candidate)
    capacity_only=candidate['kind']=='user-capacity-guard'
    edit_probe=candidate['kind']=='existing-edit-probe'
    no_new_episode=capacity_only or edit_probe
    instrument_seconds=300 if edit_probe else (120 if capacity_only else 600)
    require(re.fullmatch(r'(?:capacity-ui|user-script|edit-probe)-[a-z0-9-]{1,48}',args.run_id),'invalid run ID')
    require(candidate['kind'] in ('user-script-diagnostic','user-capacity-guard','existing-edit-probe'),'wrong candidate kind')
    if capacity_only:require(args.run_id.startswith('capacity-ui-') and args.revision_id and args.revision_sha256,'missing exact capacity draft binding')
    if edit_probe:require(args.run_id.startswith('edit-probe-') and args.revision_id and args.revision_sha256 and args.edit_instruction_sha256,'missing exact saved edit binding')
    require(digest(Path(__file__))==candidate['controllerSha256'],'controller changed')
    for kind in ('app','test'):require(digest(Path(candidate[kind]['path']))==candidate[kind]['sha256'],'APK changed')
    require(candidate['hostGuardSha256']==host_identity()['sha256'],'guard changed')
    if not args.execute:
        print(json.dumps({'mode':'plan_only','adbUsed':False,'candidateSha256':candidate_sha,
            'scope':'one reconstructed EDIT request and recovery UI; ZERO jobs/revisions/committed episode writes/TTS/Play' if edit_probe else ('existing full draft capacity guard/UI; ZERO model/jobs/data writes' if capacity_only else 'one fresh normal-input SCRIPT copy, reviewON; zero edit/TTS/Play'),
            'driverSeconds':None if edit_probe else (90 if capacity_only else 540),'instrumentSeconds':instrument_seconds}));return
    close_inherited_fds();os.umask(0o077);out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    device=Device('/home/moritz/Android/Sdk/platform-tools/adb','R5CW81PR8SY',out)
    guard=PhoneGuard(device,out,args.candidate,candidate_sha,host_identity()['sha256'])
    def save(name,value):(out/name).write_text(json.dumps(value,indent=2)+'\n')
    def stable(label):
        a=guard.snapshot(label,1);b=guard.snapshot(label,2)
        require(a==b,'unstable DB/WAL snapshot; do not disturb app')
        return a
    def installed(expected):
        actual={}
        for package,sha in expected.items():
            p=device.shell('pm path '+package,timeout=10).strip()
            require(re.fullmatch(r'package:/data/app/[^\s]+/base\.apk',p),'unexpected package path')
            actual[package]=device.shell('sha256sum '+shlex.quote(p.removeprefix('package:')),timeout=15).split()[0]
            require(actual[package]==sha,'installed APK mismatch')
        return actual
    def stop_idle_or_owned(state,owned):
        require_safe_closure(state,owned)
        for package in (APP,TEST_APP):device.shell('am force-stop '+package,timeout=10)
        guard.idle()
    pull_number=0;receipt_root=None
    def pull_private():
        nonlocal pull_number,receipt_root
        pull_number+=1
        paths=[f'files/user-failure-diagnostics/{args.run_id}',f'files/user-failure-diagnostics/{args.run_id}-driver']
        script='set --; '+''.join(f'if test -d {shlex.quote(p)}; then set -- "$@" {shlex.quote(p)}; fi; ' for p in paths)+'if test "$#" -gt 0; then tar -cf - "$@"; else printf NO_RECEIPTS; fi'
        result=device.run(['exec-out',f'run-as {APP} sh -c '+shlex.quote(script)],timeout=30,binary=True)
        raw=result.read_bytes();(out/f'private-receipts-{pull_number:02d}.tar').write_bytes(raw)
        require(len(raw)<=32*1024*1024,'private receipt archive bound')
        if raw==b'NO_RECEIPTS':return None
        extracted=out/f'private-extracted-{pull_number:02d}';extracted.mkdir(mode=0o700,exist_ok=False);receipt_root=extracted
        with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
            for member in archive:
                if member.isdir():continue
                require(member.isfile() and any(member.name.startswith(p+'/') for p in paths),'unsafe receipt member')
                relative=Path(member.name).relative_to('files/user-failure-diagnostics');require('..' not in relative.parts,'unsafe receipt path')
                p=extracted/relative;p.parent.mkdir(parents=True,exist_ok=True)
                data=archive.extractfile(member).read()
                require(not p.exists(),'duplicate receipt member')
                p.write_bytes(data)
        driver=extracted/(args.run_id+'-driver')
        if not (driver/'ownership.json').is_file():return None
        return validate_owner(json.loads((driver/'ownership.json').read_text()),json.loads((driver/'identity.json').read_text()),
            args.run_id,{e['id'] for e in rows(before)['episodes']},candidate,args.original_episode,args.original_job)
    cleanup={'errors':[],'deviceDataClear':False,'originalEpisodeUntouchedByController':True};before=None;files_before=None;owned=None;setup=False;launched=False
    def interrupt(*_):raise InterruptedError('controller interrupted; bounded owned cleanup only')
    signal.signal(signal.SIGTERM,interrupt);signal.signal(signal.SIGINT,interrupt)
    def remember(value):
        nonlocal owned
        if value is not None:
            require(owned is None or owned==value,'ownership changed; retain first binding')
            owned=value
    def small_private_json(name):
        p=f'files/user-failure-diagnostics/{args.run_id}-driver/{name}'
        raw=device.run(['exec-out',f'run-as {APP} head -c 8193 '+shlex.quote(p)],timeout=10,binary=True).read_bytes()
        require(len(raw)<=8192,'minimal ownership receipt bound')
        return json.loads(raw)
    def minimal_ownership():
        value=validate_owner(small_private_json('ownership.json'),small_private_json('identity.json'),args.run_id,
            {e['id'] for e in rows(before)['episodes']},candidate,args.original_episode,args.original_job)
        remember(value)
    def capture_logs():
        uid_text=device.shell('cmd package list packages -U '+APP,timeout=10)
        uid_map=dict(re.findall(r'package:(\S+) uid:(\d+)',uid_text));require(APP in uid_map,'app UID unavailable')
        log=device.run(['logcat','-d','-b','main','-b','crash','--uid='+uid_map[APP],'-v','threadtime'],timeout=20,binary=True)
        log.rename(out/'private-app-uid-logcat.txt')
    def close_owned():
        # This fresh safety check is independent of whole-tar/log/preservation parsing.
        device.enforce_quota=False
        current=rows(stable('safety-before-close'))
        stop_idle_or_owned(current,owned)
        remaining=[j for j in current['generation_jobs'] if j['status'] in ('QUEUED','RUNNING')]
        if remaining:
            require(all(j['status']=='RUNNING' for j in remaining),'owned QUEUED row retained; do not launch dispatcher/retry')
            device.shell(f'am start -W -n {APP}/dev.vibevoice.podcast.MainActivity',timeout=15)
            deadline=time.monotonic()+20
            while True:
                now=rows(stable(f'owned-watchdog-{device.counter}'))
                active=[j for j in now['generation_jobs'] if j['status'] in ('QUEUED','RUNNING')]
                if not active:break
                require(all(j['episodeId']==owned and j['status']=='RUNNING' for j in active),'foreign work appeared; no stop')
                require(time.monotonic()<deadline,'owned process-death reconciliation deadline')
                time.sleep(2)
            stop_idle_or_owned(now,None)
            cleanup['ownedProcessDeathReconciledByNormalWatchdog']=True
        cleanup['allActualPidsAbsent']=True
    def disarm_control():
        require(cleanup.get('allActualPidsAbsent'),'process closure unproven; preserve controls')
        script='if test -e files/user-failure-diagnostics/active.json; then sha256sum files/user-failure-diagnostics/active.json; else echo ABSENT; fi'
        observed=device.shell(f'run-as {APP} sh -c '+shlex.quote(script)).strip()
        if observed!='ABSENT':
            require(owned is not None,'unknown control ownership; preserve')
            original_path=f'files/user-failure-diagnostics/{args.run_id}-driver/control-original.json'
            raw=device.run(['exec-out',f'run-as {APP} head -c 8193 '+shlex.quote(original_path)],timeout=10,binary=True).read_bytes()
            require(len(raw)<=8192 and json.loads(raw)['episodeId']==owned and json.loads(raw)['runId']==args.run_id,'unbound control')
            require(observed.split()[0]==hashlib.sha256(raw).hexdigest(),'foreign control; preserve')
            device.shell(f'run-as {APP} rm files/user-failure-diagnostics/active.json')
        cleanup['controlAbsent']=device.shell(f'run-as {APP} sh -c '+shlex.quote('if test -e files/user-failure-diagnostics/active.json; then echo PRESENT; else echo ABSENT; fi')).strip()=='ABSENT'
    after_state={}
    def capture_files_after():after_state['files']=private_inventory(device,out,'after')
    def capture_database_after():
        after_state['database']=stable('after');validate_snapshot(after_state['database'])
    def check_preservation():
        require(cleanup.get('allActualPidsAbsent') and 'files' in after_state and 'database' in after_state,'incomplete independent preservation observations')
        preservation=compare_script(rows(before),rows(after_state['database']),owned)
        preservation['files']=compare_files(files_before,after_state['files'],owned)
        if no_new_episode:
            require(rows(before)['installed_models']==rows(after_state['database'])['installed_models'],'existing-draft probe changed model catalog')
            preservation['allRowsCatalogAndEpisodeFilesUnchanged']=True
            preservation['allowedGlobalChanges']='none (existing-draft probe)'
            if capacity_only:preservation['newModelCalls']=0
            else:preservation['modelObservation']='See private model-result/receipt; preservation comparison does not measure model calls'
        save('preservation.json',preservation)
    with (PROJECT.parent/'artifacts/locks/phone.lock').open('a+') as lock:
        os.set_inheritable(lock.fileno(),False)
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:
            guard.identity();save('installed-before.json',installed(candidate['priorInstalled']))
            before=stable('before');validate_snapshot(before);before_rows=rows(before)
            original=next(r for r in before_rows['episodes'] if r['id']==args.original_episode)
            original_job=next(j for j in before_rows['generation_jobs'] if j['id']==args.original_job)
            require(original['phase']==('SCRIPT_DRAFT' if capacity_only else 'FAILED') and original['reviewEnabled']==1 and original_job['episodeId']==args.original_episode and original_job['kind']==('AGENT_EDIT' if edit_probe else 'SCRIPT') and original_job['status']==('COMPLETE' if capacity_only else 'FAILED'),'original case changed')
            if no_new_episode:
                revision=next(r for r in before_rows['script_revisions'] if r['id']==args.revision_id)
                require(original['activeRevisionId']==args.revision_id and original['lockedRevisionId'] is None and revision['episodeId']==original['id'] and revision['contentHash']==args.revision_sha256,'existing draft revision changed')
            if edit_probe:
                message=next(m for m in before_rows['agent_messages'] if m['id']==original_job['requestMessageId'])
                require(original_job['requestedRevisionId']==args.revision_id and message['episodeId']==original['id'] and message['baseRevisionId']==args.revision_id and message['role']=='USER' and hashlib.sha256(message['text'].encode()).hexdigest()==args.edit_instruction_sha256,'saved edit request changed')
            sources=[s for s in before_rows['episode_sources'] if s['episodeId']==args.original_episode];require(len(sources)==1,'not the observed one-source case')
            files_before=private_inventory(device,out,'before')
            require(device.shell(f'run-as {APP} sh -c '+shlex.quote('if test -e files/short-product-e2e/active.json || test -e files/user-failure-diagnostics/active.json; then echo ARMED; else echo CLEAR; fi')).strip()=='CLEAR','foreign diagnostic control; preserve it')
            no_old=f'test ! -e files/user-failure-diagnostics/{args.run_id} && test ! -e files/user-failure-diagnostics/{args.run_id}-driver'
            device.shell(f'run-as {APP} sh -c '+shlex.quote(no_old),timeout=10)
            # First actual mutation: close only idle app/test, after stable no-active-work proof.
            stop_idle_or_owned(before_rows,None);setup=True
            installations={}
            for kind,package in (('app',APP),('test',TEST_APP)):
                changed=candidate['priorInstalled'][package]!=candidate[kind]['sha256']
                if changed:device.run(['install','-r','-t',candidate[kind]['path']],timeout=180)
                installations[package]={'installed':changed,'reusedExactInstalledBytes':not changed}
            save('install-operations.json',installations)
            save('installed-candidate.json',installed({APP:candidate['app']['sha256'],TEST_APP:candidate['test']['sha256']}))
            prelaunch=stable('before-instrument');require(prelaunch==before,'DB changed during installation');validate_snapshot(prelaunch);guard.idle()
            save('private-original-bindings.json',{'episodeId':args.original_episode,'jobId':args.original_job,'sourceSha256':sources[0]['sha256'],'instructionsSha256':hashlib.sha256(original['instructions'].encode()).hexdigest()})
            command=['shell','am','instrument','-w','-e','class','dev.vibevoice.podcast.e2e.UserScriptReproductionTest#reproduceNormalInputScriptOnly',
                '-e','userScriptDiagnostic','one-private-script-v1','-e','diagnosticRun',args.run_id,
                '-e','appApkSha256',candidate['app']['sha256'],'-e','testApkSha256',candidate['test']['sha256'],
                '-e','originalEpisodeId',args.original_episode,'-e','originalJobId',args.original_job,
                '-e','originalSourceSha256',sources[0]['sha256'],'-e','originalInstructionsSha256',hashlib.sha256(original['instructions'].encode()).hexdigest(),
                TEST_APP+'/androidx.test.runner.AndroidJUnitRunner']
            if capacity_only:
                command=['shell','am','instrument','-w','-e','class','dev.vibevoice.podcast.e2e.ExistingDraftCapacityTest#fullDraftCannotLockOrDispatchAudio',
                    '-e','capacityDiagnostic','existing-draft-no-model-v1','-e','diagnosticRun',args.run_id,
                    '-e','appApkSha256',candidate['app']['sha256'],'-e','testApkSha256',candidate['test']['sha256'],
                    '-e','originalEpisodeId',args.original_episode,'-e','revisionId',args.revision_id,'-e','revisionSha256',args.revision_sha256,
                    TEST_APP+'/androidx.test.runner.AndroidJUnitRunner']
            if edit_probe:
                command=['shell','am','instrument','-w','-e','class','dev.vibevoice.podcast.e2e.ExistingEditDiagnosticTest#captureOneExistingEditAndVerifyDraftRecovery',
                    '-e','editDiagnostic','existing-failed-edit-v1','-e','diagnosticRun',args.run_id,
                    '-e','appApkSha256',candidate['app']['sha256'],'-e','testApkSha256',candidate['test']['sha256'],
                    '-e','originalEpisodeId',args.original_episode,'-e','originalJobId',args.original_job,
                    '-e','revisionId',args.revision_id,'-e','revisionSha256',args.revision_sha256,
                    '-e','editInstructionSha256',args.edit_instruction_sha256,TEST_APP+'/androidx.test.runner.AndroidJUnitRunner']
                structured=candidate.get('structuredEditResponse')
                if structured:
                    command[-1:-1]=['-e','referenceRequestSha256',structured['referenceRequestSha256'],
                        '-e','responseSchemaSha256',structured['schemaSha256']]
            launched=True
            device.run(command,timeout=instrument_seconds)
            if not no_new_episode:minimal_ownership()
            remember(pull_private())
        except BaseException as error:
            save('private-controller-failure.json',{'error':repr(error),'launched':launched})
        finally:
            if setup:
                # Quota/capture faults must not prevent bounded safety cleanup. Each action is independent.
                device.enforce_quota=False
                actions=[]
                if launched:
                    if not no_new_episode:actions += [('minimal-ownership',minimal_ownership)]
                    actions += [('private-log',capture_logs),('private-receipts-before',lambda: remember(pull_private()))]
                actions += [('owned-safe-closure',close_owned),('owned-control-disarm',disarm_control)]
                if launched:actions += [('private-receipts-after',lambda: remember(pull_private()))]
                actions += [('independent-files-after',capture_files_after),('independent-db-after',capture_database_after),
                            ('preservation',check_preservation)]
                independent_cleanup(actions,cleanup['errors'])
            cleanup['ownedEpisodeId']=owned;cleanup['launched']=launched
            save('cleanup.json',cleanup)
            fcntl.flock(lock,fcntl.LOCK_UN)
    print(json.dumps({'output':str(out),'launched':launched,'ownedEpisodeId':owned,'cleanupErrors':cleanup['errors'],'phoneLockReleased':True}))

if __name__=='__main__':main()
