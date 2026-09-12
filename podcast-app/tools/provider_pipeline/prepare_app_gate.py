#!/usr/bin/env python3
"""Freeze the already-built provider app/test/native source and data pack. No build or ADB here."""
import argparse,hashlib,json,shutil,subprocess,sys,xml.etree.ElementTree as ET,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];APP=ROOT/'podcast-app'
sys.path.insert(0,str(APP/'tools'))
from duration_phone_guard import host_identity

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument('--source-commit',required=True);p.add_argument('--work',type=Path,required=True)
    p.add_argument('--native-build',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--prior-candidate',type=Path,default=APP/'.local/user-edit-ready/candidate-02/candidate.json');a=p.parse_args()
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
    if set(before)!=set(after) or len(after)!=9 or changed!=['lib/arm64-v8a/libpodcast_runtime.so']:raise ValueError('unexpected native change '+str(changed))
    native=a.native_build.resolve()/'libpodcast_runtime.so'
    strip=Path('/home/moritz/Android/Sdk/ndk/27.0.12077973/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-strip')
    stripped=out/'bridge-stripped-verification.so'
    strip_command=[str(strip),'--strip-unneeded','-o',str(stripped),str(native)]
    subprocess.run(strip_command,check=True,timeout=30,env={'HOME':str(Path.home()),'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'})
    if digest(stripped)!=after[changed[0]]:raise ValueError('APK bridge differs from exact AGP-style stripping of nominated build')
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
    value={'kind':'provider-app-integration','sourceCommit':commit,'controllerSha256':digest(Path(__file__).with_name('run_app_gate.py')),
        'hostGuardSha256':host_identity()['sha256'],'priorInstalled':{ 'dev.vibevoice.podcast.internal':prior['app']['sha256'],'dev.vibevoice.podcast.internal.test':prior['test']['sha256']},
        'providerPack':{'root':str(pack),'manifestSha256':binding['manifestSha256'],'bytes':sum(x['bytes'] for x in manifest['files'])},
        'scope':'one normal AUDIO job from a labelled copy of the accepted487-word real chapter; no original episode/source/revision/job/playback mutation; no newSCRIPT/EDIT/modelsubstitution/forcedduration',
        'instrumentationSeconds':660,'driverAudioPollingSeconds':600,'genericTextRange':[1,320],'genericLatentRange':[1,512],
        'steps':8,'speedHundredths':105,'gapFrames':13230,'frontend':'supertonic-py1.3.1 raw sentence grouping then globalUnicode14NFKD',
        'noCpuFallback':True,'noStreamingPlaybackClaim':True,'legacyVectorStrictNumericalGate':'failed; preserved',
        'newAppWaveListening':'not_reviewed','independentReviewer':None,'hostTests':counts}
    for key in ['app','test']:
        file=out/(key+'.apk');value[key]={'path':str(file),'sha256':digest(file),'bytes':file.stat().st_size}
    value['evidenceBindings']={str(f.relative_to(out)):{'sha256':digest(f),'bytes':f.stat().st_size} for f in out.rglob('*') if f.is_file() and f.suffix!='.apk'}
    save('candidate.json',value);print(json.dumps({'candidateSha256':digest(out/'candidate.json'),'app':value['app'],'test':value['test'],'hostTests':counts},indent=2))
if __name__=='__main__':main()
