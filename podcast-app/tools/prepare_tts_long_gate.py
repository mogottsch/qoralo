#!/usr/bin/env python3
"""Build one bounded long TTS variant over frozen3fd source, reusing native9 and ONE new data pack."""
from __future__ import annotations
import argparse
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from prepare_wiring_gate import PROJECT, digest
from duration_phone_guard import host_identity
from prepare_tts_long_pack import PACK_ID, NEW_ROOT, AUTHORITY

BASE='3fd75c06481bcc709d45da5c4933347f348e9079'
BASE_APP_SHA='78488901d63032b87d2d575c6bec5b7f578b3a7ee38c92e3c633ed943dcb96ab'
PATCH=[
 'app/src/debug/java/dev/vibevoice/podcast/runtime/RuntimeDiagnostics.kt',
 'app/src/debug/java/dev/vibevoice/podcast/wiring/TtsOnlyContract.kt',
 'app/src/debug/java/dev/vibevoice/podcast/wiring/TtsOnlyService.kt',
 'app/src/debug/assets/tts-only/contract.json','app/src/debug/assets/tts-only/canonical.txt',
 'app/src/androidTest/java/dev/vibevoice/podcast/wiring/TtsOnlyTest.kt',
 'app/src/testDebug/java/dev/vibevoice/podcast/wiring/TtsOnlyContractTest.kt',
 'app/src/testDebug/java/dev/vibevoice/podcast/wiring/TtsLongContractTest.kt',
 'app/src/debug/assets/tts-long/contract.json', 'app/src/debug/assets/tts-long/narration.txt',
]


def git(*args,env=None):return subprocess.check_output(['git',*args],cwd=PROJECT.parent,env=env)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--source-commit',required=True);parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    source=git('rev-parse',args.source_commit).decode().strip()
    def save(name,value):(out/name).write_text(json.dumps(value,indent=2)+'\n')
    def command(log,argv,cwd,env=None):
        with (out/log).open('w') as f:subprocess.run(argv,cwd=cwd,env=env,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=900,close_fds=True)
    try:
        input_paths=['tools/prepare_tts_long_gate.py','tools/prepare_tts_long_pack.py','tools/run_tts_long_gate.py',
                     'tools/tests/test_tts_long_scope.py','config/trusted-supertonic-long.json','docs/tts-long-engineering-gate.md']
        for path in input_paths:assert git('show',source+':podcast-app/'+path)==(PROJECT/path).read_bytes(),path
        save('source-inputs.json',{path:digest(PROJECT/path) for path in input_paths})
        baseline=PROJECT/'.local/duration-native-library-ready/cc473f8/app.apk';assert digest(baseline)==BASE_APP_SHA
        tracked=git('ls-tree','-r','--name-only',BASE,'--','podcast-app').decode().splitlines()
        build_paths=[p for p in tracked if not p.startswith(('podcast-app/evidence/','podcast-app/docs/','podcast-app/tools/'))]
        archive=git('archive',BASE,'--',*build_paths)
        build_root=out/'build-source';build_root.mkdir()
        with tarfile.open(fileobj=io.BytesIO(archive)) as t:t.extractall(build_root,filter='data')
        project=build_root/'podcast-app'
        for path in PATCH:
            data=git('show',source+':podcast-app/'+path)
            assert (PROJECT/path).read_bytes()==data,path
            p=project/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
        main_manifest=project/'app/src/main/AndroidManifest.xml';main=main_manifest.read_text()
        anchor='        <uses-native-library android:name="libOpenCL.so" android:required="false" />'
        assert main.count(anchor)==1 and 'libcdsprpc.so' not in main
        main_manifest.write_text(main.replace(anchor,anchor+'\n        <uses-native-library android:name="libcdsprpc.so" android:required="false" />'))
        component=git('show',source+':podcast-app/config/diagnostics/tts-only-components.xml').decode()
        node=ET.fromstring(component).find('./application/service');assert node is not None
        assert node.attrib['{http://schemas.android.com/apk/res/android}name']=='.wiring.TtsOnlyService'
        debug_manifest=project/'app/src/debug/AndroidManifest.xml';debug=debug_manifest.read_text()
        service='        <service android:name=".wiring.TtsOnlyService" android:exported="false" android:process=":generation" android:foregroundServiceType="dataSync" android:stopWithTask="false" />\n'
        assert debug.count('</application>')==1;debug_manifest.write_text(debug.replace('    </application>',service+'    </application>'))
        effective_paths=PATCH+['app/src/main/AndroidManifest.xml','app/src/debug/AndroidManifest.xml']
        with tempfile.TemporaryDirectory(prefix='tts-source-index-') as tmp:
            env=dict(os.environ,GIT_INDEX_FILE=tmp+'/index');git('read-tree',BASE,env=env)
            for path in effective_paths:
                blob=subprocess.check_output(['git','hash-object','-w','--stdin'],input=(project/path).read_bytes(),cwd=PROJECT.parent).decode().strip()
                git('update-index','--add','--cacheinfo','100644',blob,'podcast-app/'+path,env=env)
            tree=git('write-tree',env=env).decode().strip()
        expected={}
        for line in git('ls-tree','-r',tree,'--','podcast-app/app/src').decode().splitlines():
            desc,path=line.split('\t');expected[str(Path(path).relative_to('podcast-app'))]=desc.split()[2]
        assert {str(p.relative_to(project)) for p in (project/'app/src').rglob('*') if p.is_file()}==set(expected)
        for path,blob in expected.items():assert subprocess.check_output(['git','hash-object','--no-filters',str(project/path)]).decode().strip()==blob,path
        assert git('diff','--name-only',BASE,tree).decode().splitlines()==sorted('podcast-app/'+p for p in effective_paths)
        native={}
        with zipfile.ZipFile(baseline) as z:
            for name in z.namelist():
                if name.startswith('lib/arm64-v8a/') and name.endswith('.so'):
                    data=z.read(name);native[name]=__import__('hashlib').sha256(data).hexdigest()
                    if Path(name).name not in ['liblitertlm_jni.so','libandroidx.graphics.path.so']:
                        path=project/'app/runtime-libs/arm64-v8a'/Path(name).name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
        # Reuse the frozen bridge, do not compile it. This flag controls host CMake wiring only,
        # not a production BuildConfig/runtime option. All packaged native hashes must match.
        properties=(PROJECT/'local.properties').read_text()
        assert 'native.runtime.enabled=true' in properties
        (project/'local.properties').write_text(properties.replace('native.runtime.enabled=true','native.runtime.enabled=false'))
        contract=(project/'app/src/debug/assets/tts-long/contract.json').read_bytes()
        value=json.loads(contract)
        assert value['packId']==PACK_ID and digest(NEW_ROOT/'manifest.json')==value['supertonicManifestSha256']
        assert digest(project/'app/src/debug/assets/tts-long/narration.txt')==value['input']['sha256']
        assert digest(project/'app/src/debug/assets/tts-only/canonical.txt')=='424b38073a00cf48e4c3ebaa246aec0b6549b3ed56a1bf7cfa26d037fb29db67'
        assert git('show',source+':podcast-app/config/trusted-supertonic-long.json')==AUTHORITY.read_bytes()
        app_src=git('rev-parse',tree+':podcast-app/app/src').decode().strip()
        save('source-proof.json',{'baseSource':BASE,'overlaySource':source,'effectiveAppSrcTree':app_src,'changedSourcePaths':effective_paths,
            'allSourceBlobs':expected,'allFileSetsAndBlobsVerified':True,'nativeBridge':'exact frozen APK bytes reused; host CMake disabled only in isolated build local.properties',
            'baselineAppSha256':BASE_APP_SHA,'mainRenderAndCppChanged':False,'runtimeOptionsChanged':False,'sharedSourceWorktreeOrGradleOutputsReplaced':False,
            'overlayInputHashes':{p:digest(project/p) for p in effective_paths},'localPropertiesSha256':digest(project/'local.properties')})
        command('host-build.log',['./gradlew','--offline','--max-workers=2',':app:assembleDebug',':app:assembleDebugAndroidTest',':app:testDebugUnitTest','--tests','dev.vibevoice.podcast.wiring.TtsOnlyContractTest','--tests','dev.vibevoice.podcast.wiring.TtsLongContractTest'],project,env=dict(os.environ,PODCAST_TTS_LONG_PACK=str(NEW_ROOT)))
        for name,path in [('app','app/build/outputs/apk/debug/app-debug.apk'),('test','app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk')]:shutil.copy2(project/path,out/(name+'.apk'))
        suites=list((project/'app/build/test-results/testDebugUnitTest').glob('TEST-*.xml'))
        counts={k:sum(int(ET.parse(p).getroot().attrib.get(k,0)) for p in suites) for k in ['tests','failures','errors','skipped']}
        assert counts=={'tests':7,'failures':0,'errors':0,'skipped':0},counts
        (out/'junit').mkdir()
        for p in suites:shutil.copy2(p,out/'junit'/p.name)
        with zipfile.ZipFile(out/'app.apk') as z:
            actual={n:__import__('hashlib').sha256(z.read(n)).hexdigest() for n in z.namelist() if n.startswith('lib/') and n.endswith('.so')}
            assert actual==native,'native payload drift: hold, no new compilation authorized'
            assert z.read('assets/tts-long/contract.json')==contract
            assert z.read('assets/tts-long/narration.txt')==(project/'app/src/debug/assets/tts-long/narration.txt').read_bytes()
            assert z.read('assets/tts-only/contract.json')==(project/'app/src/debug/assets/tts-only/contract.json').read_bytes()
            assert z.read('assets/tts-only/canonical.txt')==(project/'app/src/debug/assets/tts-only/canonical.txt').read_bytes()
        command('trusted-runtime.log',['python3',str(PROJECT/'tools/verify_apk_runtime.py'),'--apk',str(out/'app.apk'),'--output',str(out/'trusted-runtime.json')],PROJECT)
        sdk=Path('/home/moritz/Android/Sdk/build-tools/35.0.0')
        for kind in ['app','test']:
            command(kind+'-manifest.txt',[str(sdk/'aapt2'),'dump','xmltree','--file','AndroidManifest.xml',str(out/(kind+'.apk'))],PROJECT)
            command(kind+'-signature.txt',[str(sdk/'apksigner'),'verify','--verbose','--print-certs',str(out/(kind+'.apk'))],PROJECT)
        save('native-byte-proof.json',{'baseline':native,'new':actual,'allNineExact':True})
        save('host-checks.json',{'focusedJvm':counts,'appAndTestAssembly':'passed','trustedNativeVerifier':'passed','nativePayloadsUnchanged':9,
            'cppOrModelCompilation':False,'physicalExecution':False,'fullUiOrJvmSuiteRerun':False,'profileHook':'debug-only; production adapter/options unchanged'})
        candidate={'schemaVersion':1,'kind':'tts-long','status':'host-validated-awaiting-exact-candidate-review-and-phone-slot','sourceCommit':source,'sourceDirty':False,
            'baseSourceCommit':BASE,'effectiveAppSrcTree':app_src,'contractSha256':__import__('hashlib').sha256(contract).hexdigest(),'contract':value,
            'hostGuardSha256':host_identity()['sha256'],'ttsControllerSha256':digest(PROJECT/'tools/run_tts_long_gate.py'),
            'privacyControllerSha256':digest(PROJECT/'tools/run_tts_only_gate.py'),
            'modelPack':{'id':PACK_ID,'root':str(NEW_ROOT),'manifestSha256':value['supertonicManifestSha256'],'authoritySha256':digest(AUTHORITY)},
            'phoneAuthorized':False,'sourceMode':'frozen diagnostic source + bounded long TTS debug overlay; exact existing native9; distinct data pack; not polished UI build'}
        for kind in ['app','test']:
            p=out/(kind+'.apk');candidate[kind]={'path':str(p),'bytes':p.stat().st_size,'sha256':digest(p)}
        candidate['evidenceBindings']={str(p.relative_to(out)):{'bytes':p.stat().st_size,'sha256':digest(p)} for p in sorted(out.rglob('*')) if p.is_file() and 'build-source' not in p.relative_to(out).parts and p.suffix!='.apk'}
        save('candidate.json',candidate)
        print(json.dumps({'sourceCommit':source,'effectiveAppSrcTree':app_src,'candidateSha256':digest(out/'candidate.json'),
            'appSha256':candidate['app']['sha256'],'testSha256':candidate['test']['sha256'],'hostGuardSha256':candidate['hostGuardSha256'],
            'ttsControllerSha256':candidate['ttsControllerSha256'],'output':str(out)},indent=2))
    except BaseException as error:save('build-failure.json',{'error':repr(error),'adbUsed':False});raise


if __name__=='__main__':main()
