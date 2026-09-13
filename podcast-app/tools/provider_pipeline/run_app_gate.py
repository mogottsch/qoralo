#!/usr/bin/env python3
"""One owned normal-app provider AUDIO integration. All raw phone evidence stays private."""
import argparse,fcntl,hashlib,io,json,os,re,shlex,signal,sys,tarfile,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from run_wiring_gate import Device,APP,TEST_APP
from prepare_wiring_gate import PROJECT,digest
from duration_phone_guard import PhoneGuard,host_identity,close_inherited_fds,validate_snapshot,require
from short_product_preservation import rows,compare,compare_files
from run_short_product_gate import private_inventory
from run_user_script_diagnostic import independent_cleanup

REFERENCE={'episode':'7dbc3e96-f1cb-40b4-bb04-5df14f05c21a','revision':'8e303378-aa37-4647-81ac-60c670de21fe',
    'revisionSha256':'e7d9d969de14604ee49548f66a69a22df37ce001fac74a906e5e4e19f90972db','chapter':'chapter-5',
    'textSha256':'cbfd5bbef581f0e793b86a568f8d4aa87fe857f413e5c2ea4780b558fc71600b'}

REPLAY={'episodeId':'b8119444-092e-408e-b594-4e2e74e789a2',
    'jobId':'e827aec4ad568ac804f5bc90c46ac9f71676c942aad71f51b413235cb4afb37b',
    'masterSha256':'2194bce66f8abd05bdf10fefc5cf4aaef49cac647992f637db319b7d14be532a'}

REPLAY_COVERAGE=('tailPausePreserved','explicitResumeAtFrontier','autoResumeAtFrontier','miniNavigationSamePlayer',
    'availableOnlySeek','speedPreserved','manualTranscriptFollow','resumeFollowing','samePlayerFinalization','pausedAtEnd')

def validate_collector_replay(value,app_sha,test_sha):
    require(value.get('remainingUiReplayVerified') is True and all(value.get('coverage',{}).get(key) is True for key in REPLAY_COVERAGE),'remaining replay UI coverage incomplete')
    require(value.get('status')=='passed' and value.get('producerOffMain') is True and value.get('playerApplicationLooper')=='main' and value.get('sourceDataUnchanged') is True,'collector thread/preservation proof mismatch')
    require(value.get('realRepoIO') is True and value.get('replay') is True and value.get('htpConcurrency') is False,'replay scope mismatch')
    require(value.get('sourceEpisodeId')==REPLAY['episodeId'] and value.get('sourceJobId')==REPLAY['jobId'],'replay attempt mismatch')
    require(value.get('sourceMasterSha256')==REPLAY['masterSha256'] and value.get('newModelCalls')==0 and value.get('newAudioJobs')==0,'replay source/model scope mismatch')
    require(value.get('appApkSha256')==app_sha and value.get('testApkSha256')==test_sha,'replay APK mismatch')
    stages=value.get('stages',[])
    require(stages and len({s['playerIdentity'] for s in stages})==1 and all(s['muted'] and s['applicationLooper']=='main' for s in stages),'replay player identity/mute/thread mismatch')
    require(any(s['stage']=='replay-advanced-before-fixture-complete' and s['playing'] and s['absolutePositionMs']>900 for s in stages),'replay advancement missing')
    require(any(s['stage']=='same-player-after-fixture-complete' and s['playing'] for s in stages),'replay finalization missing')

def safe_close(data,owned):
    for job in data['generation_jobs']:
        require(job['status'] in ('COMPLETE','FAILED','QUEUED','RUNNING'),'unknown job status')
        if job['status'] in ('QUEUED','RUNNING'):
            require(owned is not None and job['episodeId']==owned and job['kind']=='AUDIO','foreign active work; never stop it')

def parse_health(memory,battery):
    mem=re.search(r'^MemAvailable:\s+(\d+) kB',memory,re.M)
    temp=re.search(r'^\s*temperature:\s*(-?\d+)',battery,re.M)
    require(mem is not None and temp is not None,'health preflight unavailable')
    return {'availableMemoryKiB':int(mem.group(1)),'batteryTemperatureC':int(temp.group(1))/10.0}

def require_quiet_audio(dump):
    # AudioTrack state is observable even when an older app has no MediaSession.
    section=re.search(r'PlaybackActivityMonitor[^\n]*\n.*?players:\s*\n(.*?)(?=\n\s*(?:ducked players|banned uids|player event|event log)|\Z)',dump,re.S|re.I)
    require(section is not None,'current audio playback section unavailable')
    current=[line for line in section.group(1).splitlines() if re.match(r'^\s*ID:\d+\s+--',line,re.I)]
    for line in current:
        state=re.search(r'--\s*state:\s*(\w+)',line,re.I)
        require(state is not None,'current audio player state unavailable')
        require(state.group(1).lower() not in ('started','2'),'existing active audio playback; preserve user listening')
    require(not re.search(r'^\s*(?:Actual mode|mMode|Audio mode|mode)\s*[:=]\s*MODE_IN_(?:CALL|COMMUNICATION)\b',dump,re.M|re.I),'active call/communication audio; preserve it')

def require_fresh_quiet_audio(dump,started,finished,now):
    require(0<=finished-started<=2 and 0<=now-finished<=1,'stale/unknown playback observation; refuse destructive close')
    require_quiet_audio(dump)

def admission_floor_kib(synthetic_only,guard_probe_only=False,owned_guard=False):
    return (2048 if synthetic_only or guard_probe_only else 3072 if owned_guard else 3584)*1024

def main():
    p=argparse.ArgumentParser();p.add_argument('--candidate',type=Path,required=True);p.add_argument('--run-id',required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--execute',action='store_true');a=p.parse_args()
    c=json.loads(a.candidate.read_text());require(c['kind']=='provider-app-integration','wrong candidate')
    progressive=bool(c.get('progressivePlayback'))
    synthetic_only=bool(c.get('syntheticOnly'))
    guard_probe_only=bool(c.get('guardProbeOnly'))
    owned_guard=bool(c.get('ownedMemoryGuard'))
    require(sum((synthetic_only,guard_probe_only,owned_guard))<=1,'mixed execution phases')
    if owned_guard:
        proof=c['guardValidation'];require(digest(Path(proof['path']))==proof['sha256'],'guard proof drift')
        validated=json.loads(Path(proof['path']).read_text())
        require(validated.get('wholeStartFloorKiB')==3072*1024 and validated.get('preContextFloorKiB')==2648*1024 and validated.get('startupMemoryCreditKiB')==0,'guard phase-budget mismatch')
        replay=validated['collectorReplay'];require(replay['sourceMasterSha256']==REPLAY['masterSha256'] and replay['newModelCalls']==0 and replay['realRepoIO'] is True,'collector replay proof missing')
        require(validated['status']=='owned_non_neural_guard_passed' and validated['appApkSha256']==c['app']['sha256'] and validated['testApkSha256']==c['test']['sha256'] and validated.get('managedUnwindBlockedTeardown') is True and validated.get('affectedUiCases')==8,'guard proof APK/teardown/UI mismatch')
    require(not synthetic_only or progressive,'synthetic-only requires progressive validation')
    require(re.fullmatch(r'provider-app-[a-z0-9-]{1,48}',a.run_id),'invalid run ID')
    require(digest(Path(__file__))==c['controllerSha256'] and host_identity()['sha256']==c['hostGuardSha256'],'controller/guard drift')
    for key in ['app','test']:require(digest(Path(c[key]['path']))==c[key]['sha256'],'APK drift')
    pack=Path(c['providerPack']['root']);manifest=json.loads((pack/'manifest.json').read_text())
    require(digest(pack/'manifest.json')==c['providerPack']['manifestSha256'],'pack manifest drift')
    for f in manifest['files']:require((pack/f['path']).stat().st_size==f['bytes'] and digest(pack/f['path'])==f['sha256'],'pack file drift')
    if not a.execute:
        print(json.dumps({'mode':'plan-only','adbCalls':0,'modelCalls':0,'scope':'non-neural only; no model entry allowed' if synthetic_only or guard_probe_only else 'one copied-real-chapter normal AUDIO job;0newSCRIPT/EDIT; no originals mutated','instrumentationSeconds':450 if guard_probe_only else 360 if synthetic_only else 660}));return
    close_inherited_fds();os.umask(0o077);out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    device=Device('/home/moritz/Android/Sdk/platform-tools/adb','R5CW81PR8SY',out)
    guard=PhoneGuard(device,out,a.candidate,digest(a.candidate),host_identity()['sha256'])
    def save(name,obj):(out/name).write_text(json.dumps(obj,indent=2)+'\n')
    def stable(label):
        x=guard.snapshot(label,1);y=guard.snapshot(label,2);require(x==y,'unstable DB/WAL; do not disturb app');validate_snapshot(x);return x
    def installed(expected):
        got={}
        for package,sha in expected.items():
            line=device.shell('pm path '+package,timeout=10).strip();require(re.fullmatch(r'package:/data/app/[^\s]+/base\.apk',line),'unexpected APK path')
            got[package]=device.shell('sha256sum '+shlex.quote(line[len('package:'):]),timeout=15).split()[0]
            require(got[package]==sha,'installed identity mismatch')
        return got
    def health(label,enforce=False):
        memory=device.shell('cat /proc/meminfo',timeout=10)
        battery=device.shell('dumpsys battery',timeout=10)
        value=parse_health(memory,battery)
        save(label+'.json',value)
        floor=admission_floor_kib(synthetic_only,guard_probe_only,owned_guard)
        if enforce:require(value['availableMemoryKiB']>=floor and value['batteryTemperatureC']<42,'phone headroom/thermal boundary')
    def fresh_quiet_audio():
        started=time.monotonic();text=device.shell('dumpsys audio',timeout=5);finished=time.monotonic()
        require_fresh_quiet_audio(text,started,finished,time.monotonic())
    def stop(state,owned):
        safe_close(state,owned)
        # A user may begin listening without creating a job. Refuse even our own active audio
        # here rather than silently interrupt unknown/foreign playback during package cleanup.
        for package in (APP,TEST_APP):
            fresh_quiet_audio()
            device.shell('am force-stop '+package,timeout=10)
        guard.idle()
    owned=None;before=None;files_before=None;setup=False;launched=False;remote_created=False;pull=0;candidate_installed=False
    ui_settings={};ui_changed=False
    def restore_ui():
        nonlocal ui_changed
        if not ui_changed:return
        original=ui_settings['densityOverride']
        device.shell('wm density '+(str(original) if original is not None else 'reset'),timeout=10)
        font=ui_settings['fontScale']
        device.shell('settings delete system font_scale' if font=='null' else 'settings put system font_scale '+shlex.quote(font),timeout=10)
        density=device.shell('wm density',timeout=10)
        value=re.search(r'Override density:\s*(\d+)',density)
        require((int(value.group(1)) if value else None)==original,'density restore differs')
        require(device.shell('settings get system font_scale',timeout=10).strip()==font,'font-scale restore differs')
        ui_changed=False
    remote='/data/local/tmp/'+a.run_id
    cleanup={'errors':[],'deviceDataClear':False,'originalsUntouchedByController':True}
    def interrupted(*_):raise InterruptedError('bounded owned provider gate interrupted')
    signal.signal(signal.SIGINT,interrupted);signal.signal(signal.SIGTERM,interrupted)
    def ownership():
        nonlocal owned
        def read(name):
            path=f'files/provider-integration/{a.run_id}-driver/{name}'
            raw=device.run(['exec-out',f'run-as {APP} head -c 8193 '+shlex.quote(path)],timeout=10,binary=True).read_bytes()
            require(len(raw)<=8192,'oversized owner metadata');return json.loads(raw)
        value=read('ownership.json');identity=read('identity.json');eid=value['episodeId']
        require(value['runId']==a.run_id and value['createdThroughMainUi'] is True and re.fullmatch(r'[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}',eid),'invalid owner')
        require(eid not in {e['id'] for e in rows(before)['episodes']},'pre-existing episode cannot be owned')
        require(identity['runId']==a.run_id and identity['appApkSha256']==c['app']['sha256'] and identity['testApkSha256']==c['test']['sha256'],'owner APK/run mismatch')
        require(identity['originalEpisodeId']==REFERENCE['episode'] and identity['originalRevisionId']==REFERENCE['revision'] and identity['rawChapterSha256']==REFERENCE['textSha256'],'reference binding changed')
        require(owned is None or owned==eid,'owner changed');owned=eid
    def receipts():
        nonlocal pull
        pull+=1
        paths=[f'files/provider-integration/{a.run_id}',f'files/provider-integration/{a.run_id}-driver']
        if progressive:paths.append(f'files/player-ui-captures/{a.run_id}')
        if guard_probe_only:paths.append(f'files/owned-guard-probe/{a.run_id}')
        if owned:paths.append(f'files/episodes/{owned}')
        script='set --; '+''.join(f'if test -d {shlex.quote(x)}; then set -- "$@" {shlex.quote(x)}; fi; ' for x in paths)+'if test "$#" -gt 0; then tar -cf - "$@"; else printf NO_RECEIPTS; fi'
        result=device.run(['exec-out',f'run-as {APP} sh -c '+shlex.quote(script)],timeout=90,binary=True)
        raw=result.read_bytes();result.rename(out/f'private-receipts-{pull:02d}.tar') # Preserve original bytes once, not twice against the host quota.
        if raw==b'NO_RECEIPTS':return
        require(len(raw)<192*1024**2,'bounded private episode archive')
        target=out/f'private-extracted-{pull:02d}';target.mkdir(mode=0o700)
        with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
            for member in archive:
                if member.isdir():continue
                require(member.isfile() and any(member.name.startswith(x+'/') for x in paths) and '..' not in Path(member.name).parts,'unsafe private archive member')
                path=target/member.name;path.parent.mkdir(parents=True,exist_ok=True);require(not path.exists(),'duplicate archive member')
                path.write_bytes(archive.extractfile(member).read())
    def log():
        uid=device.shell('cmd package list packages -U '+APP,timeout=10)
        mapping=dict(re.findall(r'package:(\S+) uid:(\d+)',uid));require(APP in mapping,'app UID unavailable')
        result=device.run(['logcat','-d','-b','main','-b','system','-b','crash','--uid='+mapping[APP],'-v','threadtime'],timeout=20,binary=True)
        result.rename(out/'private-app-logcat.txt')
    def closure():
        device.enforce_quota=False
        state=rows(stable('safety-before-close'))
        if guard_probe_only:require(not device.shell('pidof '+APP+':guard_probe',timeout=10,check=False).strip(),'probe still alive; do not hide ownership/termination failure with a package kill')
        stop(state,owned)
        active=[j for j in state['generation_jobs'] if j['status'] in ('QUEUED','RUNNING')]
        if active:
            require(all(j['status']=='RUNNING' for j in active),'queued work retained; no automatic dispatch retry')
            device.shell(f'am start -W -n {APP}/dev.vibevoice.podcast.MainActivity',timeout=15)
            deadline=time.monotonic()+25
            while True:
                state=rows(stable('watchdog-'+str(device.counter)));safe_close(state,owned)
                jobs=[j for j in state['generation_jobs'] if j['status'] in ('QUEUED','RUNNING')]
                if not jobs:break
                require(time.monotonic()<deadline,'owned watchdog closure timed out');time.sleep(1)
            stop(state,None);cleanup['ownedOrphanReconciledByNormalWatchdog']=True
        cleanup['allActualPidsAbsent']=True
    def disarm():
        require(cleanup.get('allActualPidsAbsent'),'process closure missing')
        path='files/provider-integration/active.json'
        got=device.shell(f'run-as {APP} sh -c '+shlex.quote(f'if test -e {path}; then sha256sum {path}; else echo ABSENT; fi'),timeout=10).strip()
        if got!='ABSENT':
            require(owned is not None,'unknown provider control owner')
            original=device.run(['exec-out',f'run-as {APP} head -c 8193 files/provider-integration/{a.run_id}-driver/control-original.json'],timeout=10,binary=True).read_bytes()
            require(len(original)<=8192 and hashlib.sha256(original).hexdigest()==got.split()[0],'provider control changed')
            record=json.loads(original);require(record['episodeId']==owned and record['runId']==a.run_id,'control owner mismatch')
            device.shell(f'run-as {APP} rm '+path,timeout=10)
        require(device.shell(f'run-as {APP} sh -c '+shlex.quote(f'test ! -e {path} && echo ABSENT'),timeout=10).strip()=='ABSENT','provider control remains')
        cleanup['controlAbsent']=True
    after={}
    def files_after():after['files']=private_inventory(device,out,'after')
    def db_after():after['db']=stable('after')
    def preservation():
        b=rows(before);end=rows(after['db']);result=compare(dict(b,installed_models=[]),dict(end,installed_models=[]),owned)
        # Catalog is a current verified-route cache, not episode history. Only the new verified TTS entry may replace the old TTS cache.
        unchanged=lambda rows:[m for m in rows['installed_models'] if m['route']!='SUPERTONIC_EXTERNAL_CONTEXT_QNN_HTP']
        require(unchanged(b)==unchanged(end),'unrelated model catalog changed')
        old_tts=[m for m in b['installed_models'] if m['route']=='SUPERTONIC_EXTERNAL_CONTEXT_QNN_HTP']
        new_tts=[m for m in end['installed_models'] if m['route']=='SUPERTONIC_EXTERNAL_CONTEXT_QNN_HTP']
        if new_tts!=old_tts:
            require(len(new_tts)==1 and new_tts[0]['id']==manifest['id'] and new_tts[0]['version']==manifest['version'] and new_tts[0]['rootPath'].endswith('/model-packs/'+manifest['id']+'/current') and new_tts[0]['manifestSha256']==c['providerPack']['manifestSha256'],'unexpected catalog mutation')
            route=json.loads(new_tts[0]['runtimeProvenanceJson']);require(route['model']=='SUPERTONIC_3_PROVIDER_PIPELINE' and route['backend']=='QNN_HTP' and route['cpuFallbackEnabled'] is False,'unverified provider cache')
        added=[j for j in end['generation_jobs'] if j['id'] not in {r['id'] for r in b['generation_jobs']}]
        require(len(added)<=1 and all(j['episodeId']==owned and j['kind']=='AUDIO' for j in added),'unexpected job outside single AUDIO scope')
        require(end['agent_messages']==b['agent_messages'],'chat history changed')
        result['files']=compare_files(files_before,after['files'],owned)
        result['newAudioJobs']=len(added);result['newScriptOrEditJobs']=0;result['allowedCatalogChange']='only exact verified provider TTS cache'
        save('preservation.json',result)
    def remove_remote():
        if remote_created:
            require(device.shell(f'cat {remote}/owner',timeout=10).strip()==a.run_id,'remote owner mismatch')
            device.shell('rm -rf '+shlex.quote(remote),timeout=20)
            require(device.shell('test ! -e '+shlex.quote(remote)+' && echo ABSENT',timeout=10).strip()=='ABSENT','remote cleanup incomplete')
        require(device.shell('test ! -e '+shlex.quote(remote)+' && echo ABSENT',timeout=10).strip()=='ABSENT','remote absence unproven')
        cleanup['remoteAbsent']=True
    with (PROJECT.parent/'artifacts/locks/phone.lock').open('a+') as lock:
        os.set_inheritable(lock.fileno(),False);fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:
            guard.identity();save('installed-before.json',installed(c['priorInstalled']));health('health-before')
            before=stable('before');state=rows(before);safe_close(state,None)
            if progressive:
                audio_state=device.shell('dumpsys audio',timeout=15)
                (out/'private-audio-state-before.txt').write_text(audio_state)
                require_quiet_audio(audio_state)
            ref=next(r for r in state['script_revisions'] if r['id']==REFERENCE['revision'])
            chapter=next(r for r in state['chapters'] if r['revisionId']==ref['id'] and r['stableChapterId']==REFERENCE['chapter'])
            require(ref['episodeId']==REFERENCE['episode'] and ref['contentHash']==REFERENCE['revisionSha256'] and hashlib.sha256(chapter['text'].encode()).hexdigest()==REFERENCE['textSha256'],'real reference changed')
            files_before=private_inventory(device,out,'before')
            controls=' || '.join('test -e '+x for x in ['files/provider-integration/active.json','files/user-failure-diagnostics/active.json','files/short-product-e2e/active.json'])
            require(device.shell(f'run-as {APP} sh -c '+shlex.quote('if '+controls+'; then echo ARMED; else echo CLEAR; fi'),timeout=10).strip()=='CLEAR','foreign diagnostics armed')
            device.shell(f'run-as {APP} sh -c '+shlex.quote(f'test ! -e files/provider-integration/{a.run_id} && test ! -e files/provider-integration/{a.run_id}-driver'),timeout=10)
            stop(state,None);setup=True
            health('health-after-idle-close',True)  # Same limits, after authorized closure of proven-idle app caches and before staging/model work.
            for kind,package in [('app',APP),('test',TEST_APP)]:
                if c['priorInstalled'][package]!=c[kind]['sha256']:device.run(['install','-r','-t',c[kind]['path']],timeout=180)
            save('installed-candidate.json',installed({APP:c['app']['sha256'],TEST_APP:c['test']['sha256']}));candidate_installed=True
            destination='no_backup/model-packs/'+manifest['id']+'/current'
            present=device.shell(f'run-as {APP} sh -c '+shlex.quote(f'if test -d {destination}; then echo PRESENT; else echo MISSING; fi'),timeout=10).strip()
            if present=='MISSING':
                device.shell('test ! -e '+remote+' && mkdir '+remote+' && echo '+a.run_id+' > '+remote+'/owner',timeout=10);remote_created=True
                device.run(['push',str(pack),remote+'/pack'],timeout=600);device.shell('chmod -R a+rX '+remote,timeout=20)
                incoming='no_backup/model-packs/'+manifest['id']+'/.incoming-'+a.run_id
                device.shell(f'run-as {APP} sh -c '+shlex.quote(f'set -eu; mkdir -p no_backup/model-packs/{manifest["id"]}; test ! -e {incoming}; cp -R {remote}/pack {incoming}; test ! -e {destination}; mv {incoming} {destination}'),timeout=90)
            for item in [{'path':'manifest.json','sha256':c['providerPack']['manifestSha256']},*manifest['files']]:
                got=device.shell(f'run-as {APP} sha256sum '+shlex.quote(destination+'/'+item['path']),timeout=30).split()[0];require(got==item['sha256'],'device provider pack mismatch')
            pre=stable('before-instrument');require(pre==before,'database changed during update');guard.idle()
            fresh_quiet_audio()
            if guard_probe_only:
                output=device.run(['shell','am','instrument','-w','-e','class',
                    'dev.vibevoice.podcast.e2e.OwnedAudioGuardProbeTest,dev.vibevoice.podcast.ui.LiveCollectorRegressionTest',
                    '-e','ownedGuardProbe','true','-e','diagnosticRun',a.run_id,'-e','profile','guard-probe',
                    '-e','sourceEpisodeId',REPLAY['episodeId'],'-e','sourceJobId',REPLAY['jobId'],'-e','expectedMasterSha256',REPLAY['masterSha256'],
                    '-e','appApkSha256',c['app']['sha256'],'-e','testApkSha256',c['test']['sha256'],
                    TEST_APP+'/androidx.test.runner.AndroidJUnitRunner'],timeout=90)
                receipts()
                require(re.search(r'OK \(2 tests\)',output) is not None and 'FAILURES!!!' not in output,'owned non-neural guard/collector replay regression failed')
                result_file=out/f'private-extracted-{pull:02d}/files/owned-guard-probe/{a.run_id}/probe-result.json'
                require(result_file.is_file(),'guard probe success receipt missing')
                result=json.loads(result_file.read_text())
                require(result['status']=='owned_non_neural_guard_passed' and result['stopToObservedProcessAbsentMs']<=3000 and result['modelCalls']==0 and result['failureDurableBeforeTermination'] and result.get('managedUnwindBlockedTeardown') is True,'guard probe evidence failed')
                require(rows(stable('after-guard-probe'))==rows(before),'guard probe changed user rows')
                replay_file=out/f'private-extracted-{pull:02d}/files/player-ui-captures/{a.run_id}/live-collector/.private-ui/replay.json'
                require(replay_file.is_file(),'real IO collector replay receipt missing')
                replay=json.loads(replay_file.read_text());validate_collector_replay(replay,c['app']['sha256'],c['test']['sha256'])
                guard_probe_result=dict(result,collectorReplay={'sha256':digest(replay_file),'sourceMasterSha256':REPLAY['masterSha256'],'newModelCalls':0,'realRepoIO':True,'remainingUiReplayVerified':True,'coverage':replay['coverage']})
            if progressive and not owned_guard:
                density=device.shell('wm density',timeout=10);size=device.shell('wm size',timeout=10)
                override=re.search(r'Override density:\s*(\d+)',density)
                effective_size=re.search(r'Override size:\s*(\d+)x(\d+)',size) or re.search(r'Physical size:\s*(\d+)x(\d+)',size)
                require(effective_size is not None,'display size unavailable')
                ui_settings={'densityOverride':int(override.group(1)) if override else None,'fontScale':device.shell('settings get system font_scale',timeout=10).strip()}
                save('ui-settings-before.json',ui_settings)
                for profile in ['default','narrow-font2']:
                    if profile=='narrow-font2':
                        ui_changed=True
                        device.shell('wm density '+str(round(int(effective_size.group(1))*160/320)),timeout=10)
                        device.shell('settings put system font_scale 2.0',timeout=10)
                    fresh_quiet_audio()
                    synthetic=device.run(['shell','am','instrument','-w','-e','class',
                        'dev.vibevoice.podcast.ui.PersistentPlayerRegressionTest,dev.vibevoice.podcast.ui.ProgressivePlayerRegressionTest',
                        '-e','diagnosticRun',a.run_id,'-e','profile',profile,
                        TEST_APP+'/androidx.test.runner.AndroidJUnitRunner'],timeout=180)
                    require(re.search(r'OK \(4 tests\)',synthetic) is not None and 'FAILURES!!!' not in synthetic,'synthetic '+profile+' playback regression failed; no model run')
                    synthetic_state=rows(stable('after-synthetic-'+profile))
                    require(synthetic_state==rows(before),'synthetic tests changed user database')
                    stop(synthetic_state,None)
                    save('synthetic-playback-'+profile+'.json',{'tests':4,'profile':profile,'status':'passed','modelCalls':0,'realNeuralRun':False})
                restore_ui()
            if guard_probe_only:
                save('guard-probe-result.json',dict(guard_probe_result,affectedUiCases=8))
                return # Dedicated non-neural phase; never enter AUDIO here.
            if synthetic_only:
                save('synthetic-only-result.json',{'status':'ui_tests_passed_not_neural_e2e','tests':8,'modelCalls':0,'modelConstructions':0,'newAudioJobs':0,'neuralStageEntered':False,'admissionFloorKiB':2048*1024})
                return # finally performs preservation/settings/identity/cleanup; never fall through to AUDIO.
            health('health-before-inference',True)
            fresh_quiet_audio()
            command=['shell','am','instrument','-w','-e','class','dev.vibevoice.podcast.e2e.ProviderAppIntegrationTest#copiedRealChapterCompletesNormalAudioJob',
                '-e','providerIntegration','copied-real-chapter-v1','-e','diagnosticRun',a.run_id,
                '-e','appApkSha256',c['app']['sha256'],'-e','testApkSha256',c['test']['sha256'],
                '-e','originalEpisodeId',REFERENCE['episode'],'-e','originalRevisionId',REFERENCE['revision'],
                '-e','originalRevisionSha256',REFERENCE['revisionSha256'],'-e','originalChapterId',REFERENCE['chapter'],
                '-e','chapterSha256',REFERENCE['textSha256'],TEST_APP+'/androidx.test.runner.AndroidJUnitRunner']
            if progressive:command[-1:-1]=['-e','progressivePlayback','true']
            if owned_guard:command[-1:-1]=['-e','ownedMemoryGuard','true']
            launched=True;device.run(command,timeout=660);ownership();receipts()
            result_file=out/f'private-extracted-{pull:02d}/files/provider-integration/{a.run_id}-driver/driver-result.json'
            require(result_file.is_file(),'owned E2E did not produce a success receipt; preserve its first result')
            result=json.loads(result_file.read_text())
            require(result.get('episodeId')==owned and result.get('newAudioJobs')==1 and result.get('status')=='copied_real_chapter_normal_audio_complete','owned E2E result mismatch')
            if owned_guard:require(result.get('ownedMemoryGuardVerified') is True,'owned guard proof missing')
            if progressive:require(result.get('progressivePlaybackVerified') is True and result.get('mutedPlayer') is True,'progressive proof incomplete')
            save('e2e-result.json',{'status':'passed','episodeId':owned,'driverReceiptSha256':digest(result_file),'progressivePlaybackVerified':progressive,'syntheticTestsRunHere':0 if owned_guard else 8 if progressive else 0,'reusedExactApkUiCases':8 if owned_guard else 0})
        except BaseException as error:save('private-controller-failure.json',{'error':repr(error),'launched':launched})
        finally:
            device.enforce_quota=False
            if setup:
                actions=[]
                if launched:actions += [('minimal-owner',ownership),('logs',log),('receipts-before',receipts)]
                elif progressive:actions += [('synthetic-receipts',receipts)]
                actions += [('safe-closure',closure),('control-disarm',disarm),('ui-settings-restore',restore_ui)]
                if launched:actions += [('receipts-after',receipts)]
                actions += [('files-after',files_after),('db-after',db_after),('preservation',preservation),('health-after',lambda:health('health-after')),('installed-after',lambda:save('installed-after.json',installed({APP:c['app']['sha256'],TEST_APP:c['test']['sha256']} if candidate_installed else c['priorInstalled']))),('remote-cleanup',remove_remote)]
                independent_cleanup(actions,cleanup['errors'])
            cleanup['ownedEpisodeId']=owned;cleanup['launched']=launched;save('cleanup.json',cleanup)
            fcntl.flock(lock,fcntl.LOCK_UN)
    print(json.dumps({'output':str(out),'launched':launched,'ownedEpisodeId':owned,'cleanupErrors':cleanup['errors'],'phoneLockReleased':True}))

if __name__=='__main__':main()
