#!/usr/bin/env python3
"""One non-neural publication recovery of the completed owned app WAV. No synthesis/replay."""
import argparse,fcntl,hashlib,io,json,os,re,shlex,signal,sys,tarfile,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from run_wiring_gate import Device,APP,TEST_APP
from prepare_wiring_gate import PROJECT,digest
from duration_phone_guard import PhoneGuard,host_identity,close_inherited_fds,validate_snapshot,require
from short_product_preservation import rows,compare_files,TABLES
from run_short_product_gate import private_inventory
from run_user_script_diagnostic import independent_cleanup
from run_app_gate import safe_close,parse_health

SCOPE={'episodeId':'e22a61c9-ec57-46f1-a700-83d55ef88e08','sourceJobId':'27a86e7407164a1b1f0768c21ab6dc8de4e9574cf99a17f31d8628654b88a9b6',
    'revisionId':'c337a09b-38be-4b25-a899-d677b6873bb2','revisionSha256':'5e8a47c83a00fb6a1fc0e4876cee892a5496307dd631488b0e6072f429c5d414',
    'completedWavePath':'e22a61c9-ec57-46f1-a700-83d55ef88e08/chapters/.provider-d8cfdd4d-1e0d-4f0c-9b62-5c49011acc8b/complete-chapter.wav',
    'wavSha256':'2194bce66f8abd05bdf10fefc5cf4aaef49cac647992f637db319b7d14be532a'}

def compare_recovery(before,after):
    owned=SCOPE['episodeId'];allowed={'phase','failurePhase','failureMessage','updatedAtEpochMs','currentChapterPosition','finalAudioPath','finalAudioSha256','finalAudioByteCount','durationMs','timelinePath','timelineSha256','timelineByteCount'}
    report={}
    for table in TABLES:
        key='rowId' if table=='chapters' else ('episodeId' if table=='playback_state' else 'id')
        old={r[key]:r for r in before[table]};new={r[key]:r for r in after[table]}
        for k,v in old.items():
            require(k in new,'original row removed')
            if table=='episodes' and k==owned:
                require({a:b for a,b in v.items() if a not in allowed}=={a:b for a,b in new[k].items() if a not in allowed},'immutable recovery episode field changed')
            else:require(v==new[k],'original/history/catalog row changed: '+table)
        added=[r for k,r in new.items() if k not in old]
        require(not added or table in ('generation_jobs','chapter_audio','playback_state'),'unexpected recovery row addition')
        require(len(added)<=1 and all(r['episodeId']==owned for r in added),'unowned recovery addition')
        if table=='generation_jobs':require(all(r['kind']=='AUDIO' and r['requestedRevisionId']==SCOPE['revisionId'] and r['id']!=SCOPE['sourceJobId'] for r in added),'invalid recovery attempt')
        if table=='chapter_audio':require(all(r['lockedRevisionId']==SCOPE['revisionId'] and r['position']==0 and r['sha256']==SCOPE['wavSha256'] and r['relativePath']==owned+'/chapters/chapter-000.wav' for r in added),'invalid recovered chapter ownership/hash')
        report[table]={'existingRowsRetained':len(old),'ownedAdded':len(added)}
    episode=next(e for e in after['episodes'] if e['id']==owned)
    require(episode['phase'] in ('FAILED','LOCKED','GENERATING_AUDIO','FROZEN_READY'),'unexpected publication phase')
    if episode['phase']=='FROZEN_READY':
        jobs=[j for j in after['generation_jobs'] if j['episodeId']==owned and j['id'] not in {r['id'] for r in before['generation_jobs']}]
        require(len(jobs)==1 and jobs[0]['status']=='COMPLETE' and episode['finalAudioSha256']==SCOPE['wavSha256'] and episode['finalAudioPath']==owned+'/final/'+jobs[0]['id']+'/episode.wav','Ready artifact not owned by completed recovery')
    return {'tables':report,'failedJobAndAllOriginalFilesMustRemainUnchanged':True,'newNeuralCalls':0,'ownedEpisodePublicationStateOnly':True}

def main():
    p=argparse.ArgumentParser();p.add_argument('--candidate',type=Path,required=True);p.add_argument('--run-id',required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--execute',action='store_true');a=p.parse_args()
    require(re.fullmatch(r'provider-app-[a-z0-9-]{1,48}',a.run_id),'invalid recovery run ID')
    c=json.loads(a.candidate.read_text());require(c['kind']=='provider-publication-recovery' and c['controllerSha256']==digest(Path(__file__)),'wrong recovery candidate/controller')
    require(c['hostGuardSha256']==host_identity()['sha256'],'guard changed')
    for k in ('app','test'):require(digest(Path(c[k]['path']))==c[k]['sha256'],'APK changed')
    if not a.execute:print(json.dumps({'scope':'non-neural owned publication recovery','adbCalls':0,'neuralCalls':0,'instrumentationSeconds':120}));return
    close_inherited_fds();os.umask(0o077);out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    d=Device('/home/moritz/Android/Sdk/platform-tools/adb','R5CW81PR8SY',out);g=PhoneGuard(d,out,a.candidate,digest(a.candidate),host_identity()['sha256'])
    def interrupted(*_):raise InterruptedError('publication controller interrupted; owned cleanup only')
    signal.signal(signal.SIGTERM,interrupted);signal.signal(signal.SIGINT,interrupted)
    def save(name,value):(out/name).write_text(json.dumps(value,indent=2)+'\n')
    def stable(label):
        x=g.snapshot(label,1);y=g.snapshot(label,2);require(x==y,'unstable database');validate_snapshot(x);return x
    def identity(expected):
        got={}
        for pkg,value in expected.items():
            line=d.shell('pm path '+pkg).strip();require(line.startswith('package:/data/app/') and line.endswith('/base.apk'),'unexpected APK path')
            got[pkg]=d.shell('sha256sum '+shlex.quote(line[len('package:'):])).split()[0];require(got[pkg]==value,'installed identity differs')
        return got
    def stop():
        state=rows(stable('safety-close'));safe_close(state,SCOPE['episodeId'])
        require(not any(j['status']=='QUEUED' for j in state['generation_jobs']),'queued work retained, no dispatch retry')
        active=[j for j in state['generation_jobs'] if j['status']=='RUNNING']
        for pkg in (APP,TEST_APP):d.shell('am force-stop '+pkg)
        g.idle()
        if active:
            d.shell(f'am start -W -n {APP}/dev.qoralo.podcast.MainActivity')
            deadline=time.monotonic()+25
            while True:
                current=rows(stable('watchdog-'+str(d.counter)));safe_close(current,SCOPE['episodeId'])
                if not any(j['status'] in ('QUEUED','RUNNING') for j in current['generation_jobs']):break
                require(time.monotonic()<deadline,'recovery watchdog closure incomplete');time.sleep(1)
            for pkg in (APP,TEST_APP):d.shell('am force-stop '+pkg)
            g.idle();cleanup['ownedOrphanReconciled']=True
        cleanup['allActualPidsAbsent']=True
    pulls=0
    def pull():
        nonlocal pulls
        pulls+=1;names=[f'files/provider-integration/{a.run_id}-driver',f'files/episodes/{SCOPE["episodeId"]}']
        script='set --; '+''.join(f'if test -d {x}; then set -- "$@" {x}; fi; ' for x in names)+'tar -cf - "$@"'
        p=d.run(['exec-out',f'run-as {APP} sh -c '+shlex.quote(script)],timeout=90,binary=True);raw=p.read_bytes();(out/f'private-recovery-{pulls:02d}.tar').write_bytes(raw)
        require(len(raw)<192*1024**2,'archive bound');dest=out/f'private-extracted-{pulls:02d}';dest.mkdir()
        with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
            for item in archive:
                if item.isdir():continue
                require(item.isfile() and any(item.name.startswith(x+'/') for x in names) and '..' not in Path(item.name).parts,'unsafe recovery archive')
                file=dest/item.name;file.parent.mkdir(parents=True,exist_ok=True);require(not file.exists(),'duplicate archive');file.write_bytes(archive.extractfile(item).read())
    def controls_absent():
        tests=' || '.join('test -e '+x for x in ['files/provider-integration/active.json','files/user-failure-diagnostics/active.json','files/short-product-e2e/active.json'])
        require(d.shell(f'run-as {APP} sh -c '+shlex.quote('if '+tests+'; then echo ARMED; else echo CLEAR; fi')).strip()=='CLEAR','unexpected diagnostic control remains')
        cleanup['controlsAbsent']=True
    after={};cleanup={'errors':[],'neuralCalls':0,'deviceDataClear':False};setup=False;launched=False
    def files_after():after['files']=private_inventory(d,out,'after')
    def db_after():after['db']=stable('after')
    def preservation():
        result=compare_recovery(rows(before),rows(after['db']));result['files']=compare_files(files_before,after['files'],SCOPE['episodeId']);save('preservation.json',result)
    with (PROJECT.parent/'artifacts/locks/phone.lock').open('a+') as lock:
        os.set_inheritable(lock.fileno(),False);fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:
            g.identity();save('installed-before.json',identity(c['priorInstalled']));before=stable('before');b=rows(before);safe_close(b,None)
            ep=next(e for e in b['episodes'] if e['id']==SCOPE['episodeId']);job=next(j for j in b['generation_jobs'] if j['id']==SCOPE['sourceJobId'])
            require(ep['phase']=='FAILED' and ep['lockedRevisionId']==SCOPE['revisionId'] and ep['lockedContentHash']==SCOPE['revisionSha256'] and job['status']=='FAILED','recovery source state changed')
            files_before=private_inventory(d,out,'before');require(files_before.get('files/episodes/'+SCOPE['completedWavePath'])==SCOPE['wavSha256'],'completed bytes changed')
            health=parse_health(d.shell('cat /proc/meminfo'),d.shell('dumpsys battery'));save('health-before.json',health)
            require(health['availableMemoryKiB']>=768*1024 and health['batteryTemperatureC']<42,'non-neural copy/UI headroom unavailable')
            controls=' || '.join('test -e '+x for x in ['files/provider-integration/active.json','files/user-failure-diagnostics/active.json','files/short-product-e2e/active.json'])
            require(d.shell(f'run-as {APP} sh -c '+shlex.quote('if '+controls+'; then echo ARMED; else echo CLEAR; fi')).strip()=='CLEAR','foreign diagnostic control')
            d.shell(f'run-as {APP} sh -c '+shlex.quote(f'test ! -e files/provider-integration/{a.run_id}-driver'))
            stop();setup=True
            for k,pkg in [('app',APP),('test',TEST_APP)]:
                if c[k]['sha256']!=c['priorInstalled'][pkg]:d.run(['install','-r','-t','--user','0',c[k]['path']],timeout=180)
            save('installed-candidate.json',identity({APP:c['app']['sha256'],TEST_APP:c['test']['sha256']}));require(stable('prelaunch')==before,'data changed during update')
            cmd=['shell','am','instrument','-w','-e','class','dev.qoralo.podcast.e2e.ProviderPublicationRecoveryTest#publishExactCompletedChapterWithoutInference',
                '-e','providerRecovery','non-neural-v1','-e','diagnosticRun',a.run_id,'-e','appApkSha256',c['app']['sha256'],'-e','testApkSha256',c['test']['sha256']]
            for key,value in dict(SCOPE,ownedEpisodeId=SCOPE['episodeId']).items():cmd+=['-e',key,value]
            cmd+=[TEST_APP+'/androidx.test.runner.AndroidJUnitRunner'];launched=True;d.run(cmd,timeout=120);pull()
        except BaseException as error:save('private-failure.json',{'error':repr(error),'launched':launched})
        finally:
            d.enforce_quota=False
            if setup:
                actions=[('safe-closure',stop),('controls-absent',controls_absent)]
                if launched:actions += [('private-receipts',pull)]
                actions += [('files-after',files_after),('db-after',db_after),('preservation',preservation)]
                independent_cleanup(actions,cleanup['errors'])
            cleanup['launched']=launched;save('cleanup.json',cleanup);fcntl.flock(lock,fcntl.LOCK_UN)
    print(json.dumps({'output':str(out),'launched':launched,'cleanupErrors':cleanup['errors'],'phoneLockReleased':True,'neuralCalls':0}))
if __name__=='__main__':main()
