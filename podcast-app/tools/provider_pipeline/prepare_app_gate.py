#!/usr/bin/env python3
"""Freeze the already-built provider app/test/native source and data pack. No build or ADB here."""
import argparse,hashlib,json,shutil,subprocess,sys,xml.etree.ElementTree as ET,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];APP=ROOT/'podcast-app'
sys.path.insert(0,str(APP/'tools'))
from duration_phone_guard import host_identity
from run_app_gate import REPLAY

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument('--source-commit',required=True);p.add_argument('--work',type=Path,required=True)
    p.add_argument('--native-build',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--prior-candidate',type=Path,default=APP/'.local/user-edit-ready/candidate-02/candidate.json');p.add_argument('--publication-recovery',action='store_true');p.add_argument('--progressive-playback',action='store_true');p.add_argument('--synthetic-only',action='store_true');p.add_argument('--guard-probe-only',action='store_true');p.add_argument('--owned-memory-guard',action='store_true');p.add_argument('--guard-validation',type=Path);a=p.parse_args()
    if sum((a.synthetic_only,a.guard_probe_only,a.owned_memory_guard,a.publication_recovery))>1:raise ValueError('Different frozen execution phases')
    if (a.guard_probe_only or a.owned_memory_guard) and not a.progressive_playback:raise ValueError('Guard validation requires progressive candidate')
    if a.owned_memory_guard and a.guard_validation is None:raise ValueError('Validated non-neural guard evidence required before neural freeze')
    if a.synthetic_only and not a.progressive_playback:raise ValueError('Synthetic-only requires progressive validation')
    if a.publication_recovery and a.progressive_playback:raise ValueError('Different validation scopes')
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);build=a.work.resolve()/'build-source/podcast-app'
    commit=subprocess.check_output(['git','rev-parse',a.source_commit],cwd=ROOT,text=True).strip()
    names=subprocess.check_output(['git','ls-tree','-r','--name-only',commit,'--','podcast-app/app/src','podcast-app/app/schemas','podcast-app/config','podcast-app/app/build.gradle.kts','podcast-app/build.gradle.kts','podcast-app/settings.gradle.kts','podcast-app/gradle.properties'],cwd=ROOT,text=True).splitlines()
    pins={}
    for name in names:
        rel=Path(name).relative_to('podcast-app');raw=subprocess.check_output(['git','show',commit+':'+name],cwd=ROOT)
        if raw!=(build/rel).read_bytes() or raw!=(APP/rel).read_bytes():raise ValueError('source drift '+name)
        pins[str(rel)]=hashlib.sha256(raw).hexdigest()
    def save(name,value):(out/name).write_text(json.dumps(value,indent=2)+'\n')
    save('source-bindings.json',{'commit':commit,'files':pins,'credentialFreeBuildEnvironment':True})
    cfg=build/'app/build/generated/source/buildConfig/debug/dev/vibevoice/podcast/BuildConfig.java'
    config=cfg.read_text()
    if 'SHORT_PRODUCT_E2E = false' not in config or 'supertonic-3-provider' not in config:raise ValueError('wrong build selector')
    shutil.copy2(cfg,out/'BuildConfig.java')
    for key,source in [('app',build/'app/build/outputs/apk/debug/app-debug.apk'),('test',build/'app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk')]:shutil.copy2(source,out/(key+'.apk'))
    prior=json.loads(a.prior_candidate.read_text())
    def natives(path):
        with zipfile.ZipFile(path) as z:return {n:hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist() if n.startswith('lib/') and n.endswith('.so')}
    before=natives(prior['app']['path']);after=natives(out/'app.apk')
    changed=[n for n in after if before.get(n)!=after[n]]
    if set(before)!=set(after) or len(after)!=9 or any(n!='lib/arm64-v8a/libpodcast_runtime.so' for n in changed):raise ValueError('unexpected native change '+str(changed))
    native=a.native_build.resolve()/'libpodcast_runtime.so'
    strip=Path('/home/moritz/Android/Sdk/ndk/27.0.12077973/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-strip')
    stripped=out/'bridge-stripped-verification.so'
    strip_command=[str(strip),'--strip-unneeded','-o',str(stripped),str(native)]
    subprocess.run(strip_command,check=True,timeout=30,env={'HOME':str(Path.home()),'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'})
    if digest(stripped)!=after['lib/arm64-v8a/libpodcast_runtime.so']:raise ValueError('APK bridge differs from exact AGP-style stripping of nominated build')
    stripped_hash=digest(stripped);stripped.unlink()
    save('native-source-proof.json',{'nativeFiles':after,'changed':changed,'otherEightUnchanged':True,'bridgePath':str(native),
        'unstrippedBridgeSha256':digest(native),'packagedBridgeSha256':stripped_hash,'stripToolSha256':digest(strip),'stripCommand':strip_command,
        'nativeSources':{str(f.relative_to(APP)):digest(f) for f in (APP/'app/src/main/cpp').iterdir() if f.is_file()},
        'fmaContraction':'off','sourceBuilt':True})
    for f in a.native_build.glob('*.log'):shutil.copy2(f,out/('native-'+f.name))
    for f in a.work.glob('*build-*.log'):shutil.copy2(f,out/f.name)
    junit=out/'junit';junit.mkdir();counts={k:0 for k in ['tests','failures','errors','skipped']};skipped=[];suites={}
    for f in (build/'app/build/test-results/testDebugUnitTest').glob('TEST-*.xml'):
        e=ET.parse(f).getroot();suites[e.attrib['name']]=e.attrib
        for key in counts:counts[key]+=int(e.attrib[key])
        skipped += [t.attrib['classname']+'#'+t.attrib['name'] for t in e.findall('testcase') if t.find('skipped') is not None]
        shutil.copy2(f,junit/f.name)
    if counts['tests']<190 or counts['failures'] or counts['errors']:raise ValueError('unit failure/incomplete tests')
    allowed={'dev.vibevoice.podcast.wiring.TtsLongContractTest#explicitLocalPackPassesProductionVerifierAndFullReconstruction'}
    if not set(skipped)<=allowed:raise ValueError('unexpected skipped tests')
    for name in ['ProviderTextFrontendTest','ProviderAudioPlanTest','ProviderWaveAssemblyTest']:
        row=suites['dev.vibevoice.podcast.runtime.'+name]
        if int(row['skipped']) or int(row['tests'])<2:raise ValueError('required provider test skipped')
    save('host-tests.json',{'counts':counts,'passed':counts['tests']-counts['skipped'],'skipped':skipped})
    env={'HOME':str(Path.home()),'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'}
    def run(name,argv):
        with (out/name).open('w') as f:subprocess.run(argv,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=120,env=env)
    run('python-tests.log',['python3','-m','unittest','discover','-s',str(APP/'tools/provider_pipeline'),'-p','test_pipeline.py','-v'])
    run('runtime-proof.log',['python3',str(APP/'tools/verify_apk_runtime.py'),'--apk',str(out/'app.apk'),'--output',str(out/'runtime-proof.json')])
    sdk=Path('/home/moritz/Android/Sdk/build-tools/35.0.0')
    for key in ['app','test']:
        run(key+'-signature.txt',[str(sdk/'apksigner'),'verify','--verbose','--print-certs',str(out/(key+'.apk'))])
        run(key+'-manifest.txt',[str(sdk/'aapt2'),'dump','xmltree','--file','AndroidManifest.xml',str(out/(key+'.apk'))])
    pack=APP/'.local/model-packs/supertonic-3-provider/current';manifest=json.loads((pack/'manifest.json').read_text())
    binding=json.loads((APP/'config/trusted-supertonic-provider.json').read_text())
    if digest(pack/'manifest.json')!=binding['manifestSha256']:raise ValueError('provider manifest drift')
    for item in manifest['files']:
        file=pack/item['path']
        if file.stat().st_size!=item['bytes'] or digest(file)!=item['sha256']:raise ValueError('provider asset drift')
    shutil.copy2(pack/'manifest.json',out/'provider-manifest.json')
    value={'kind':'provider-publication-recovery' if a.publication_recovery else 'provider-app-integration','sourceCommit':commit,'controllerSha256':digest(Path(__file__).with_name('run_publication_recovery.py' if a.publication_recovery else 'run_app_gate.py')),
        'hostGuardSha256':host_identity()['sha256'],'priorInstalled':{ 'dev.vibevoice.podcast.internal':prior['app']['sha256'],'dev.vibevoice.podcast.internal.test':prior['test']['sha256']},
        'providerPack':{'root':str(pack),'manifestSha256':binding['manifestSha256'],'bytes':sum(x['bytes'] for x in manifest['files'])},
        'scope':'preserving install and eight synthetic-only playback UI cases; zero model construction/calls/new AUDIO jobs; explicit return before neural entry' if a.synthetic_only else 'new non-neural publication attempt for exact already-completed owned chapter; original failed job/plan/WAV and all other user data preserved' if a.publication_recovery else 'one normal AUDIO job from a labelled copy of the accepted487-word real chapter; no original episode/source/revision/job/playback mutation; no newSCRIPT/EDIT/modelsubstitution/forcedduration',
        'progressivePlayback':a.progressive_playback,
        'syntheticOnly':a.synthetic_only,
        'guardProbeOnly':a.guard_probe_only,
        'retainedCollectorReplaySource':REPLAY if a.guard_probe_only or a.owned_memory_guard else None,
        'ownedMemoryGuard':a.owned_memory_guard,
        'guardPlanningEnvelopeMiB':2048,
        'ownedPreContextAdmissionFloorKiB':2648*1024,
        'startupMemoryCreditKiB':0,
        'guardProactiveStopKiB':1280*1024,
        'guardEmergencyReserveKiB':600*1024,
        'syntheticAdmissionFloorKiB':2048*1024 if a.synthetic_only or a.guard_probe_only else 3072*1024 if a.owned_memory_guard else 3584*1024,
        'neuralAdmissionFloorKiB':3072*1024 if a.owned_memory_guard else 3584*1024,
        'syntheticPlaybackTestsBeforeModels':8 if a.progressive_playback else 0,
        'playbackScope':'explicit muted Play on owned episode only' if a.progressive_playback else 'no Play requested',
        'instrumentationSeconds':360 if a.synthetic_only else 120 if a.publication_recovery else 660,'driverAudioPollingSeconds':90 if a.publication_recovery else 600,'genericTextRange':[1,320],'genericLatentRange':[1,512],
        'steps':8,'speedHundredths':105,'gapFrames':13230,'frontend':'supertonic-py1.3.1 raw sentence grouping then globalUnicode14NFKD',
        'noCpuFallback':True,'noStreamingPlaybackClaim':a.synthetic_only or not a.progressive_playback,'legacyVectorStrictNumericalGate':'failed; preserved',
        'newAppWaveListening':'not_reviewed','independentReviewer':None,'hostTests':counts}
    for key in ['app','test']:
        file=out/(key+'.apk');value[key]={'path':str(file),'sha256':digest(file),'bytes':file.stat().st_size}
    if a.guard_probe_only:
        value['scope']='owned non-neural blocked-teardown guard + retained2194 real-IO collector replay + eight default/narrow regressions; never enters AUDIO'
        value['instrumentationSeconds']=450
    if a.owned_memory_guard:
        proof=json.loads(a.guard_validation.read_text())
        if proof.get('status')!='owned_non_neural_guard_passed' or not 0<=proof['stopToObservedProcessAbsentMs']<=3000 or proof['modelCalls']!=0 or not proof['failureDurableBeforeTermination'] or proof.get('managedUnwindBlockedTeardown') is not True or proof.get('affectedUiCases')!=8:raise ValueError('Guard probe not validated')
        replay=proof.get('collectorReplay',{})
        if replay.get('sourceMasterSha256')!=REPLAY['masterSha256'] or replay.get('newModelCalls')!=0 or replay.get('realRepoIO') is not True:raise ValueError('Production IO collector replay proof required')
        if proof.get('wholeStartFloorKiB')!=3072*1024 or proof.get('preContextFloorKiB')!=2648*1024 or proof.get('startupMemoryCreditKiB')!=0:raise ValueError('Guard phase-budget mismatch')
        if proof['appApkSha256']!=value['app']['sha256'] or proof['testApkSha256']!=value['test']['sha256']:raise ValueError('Guard probe used different APKs')
        value['guardValidation']={'path':str(a.guard_validation.resolve()),'sha256':digest(a.guard_validation)}
        value['syntheticPlaybackTestsBeforeModels']=0
        value['reusedExactApkUiCases']=8
        value['scope']='one provisional owned guarded AUDIO/livePlayer evaluation:3072MiB whole-start,2648MiB pre-context(full2048+600 recharged,no startup credit); not global relaxation/proven minimum; no resynthesis for UI'
    value['evidenceBindings']={str(f.relative_to(out)):{'sha256':digest(f),'bytes':f.stat().st_size} for f in out.rglob('*') if f.is_file() and f.suffix!='.apk'}
    save('candidate.json',value);print(json.dumps({'candidateSha256':digest(out/'candidate.json'),'app':value['app'],'test':value['test'],'hostTests':counts},indent=2))
if __name__=='__main__':main()
