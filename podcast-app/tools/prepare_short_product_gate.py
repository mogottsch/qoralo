#!/usr/bin/env python3
"""Freeze the normal/coherent app with explicit short plumbing property, native9 reuse; no ADB/model calls."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import xml.etree.ElementTree as ET
import zipfile
from prepare_wiring_gate import PROJECT, digest
from duration_phone_guard import host_identity
from run_short_product_gate import CONTRACT_SHA, CONTINUATION_SHA, EXPORT_SHA, PACKS, PRIOR

BASE_APK_SHA='78488901d63032b87d2d575c6bec5b7f578b3a7ee38c92e3c633ed943dcb96ab'
CONTROLLERS=['tools/run_short_product_gate.py','tools/short_product_preservation.py']


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--source-commit',required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--reuse-app-candidate',type=Path)
    parser.add_argument('--continuation',action='store_true')
    parser.add_argument('--export-only',action='store_true')
    args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    assert not (args.continuation and args.export_only)
    assert not args.export_only or args.reuse_app_candidate, 'export-only must reuse the unchanged app'
    contract_sha=EXPORT_SHA if args.export_only else CONTINUATION_SHA if args.continuation else CONTRACT_SHA
    asset='short-product-export' if args.export_only else 'short-product-continuation' if args.continuation else 'short-product-e2e'
    asset_source='androidTest' if args.export_only else 'debug'
    previous=json.loads(args.reuse_app_candidate.read_text()) if args.reuse_app_candidate else None
    def git(*argv):return subprocess.check_output(['git',*argv],cwd=PROJECT.parent)
    source=git('rev-parse',args.source_commit).decode().strip()
    def save(name,value):(out/name).write_text(json.dumps(value,indent=2)+'\n')
    def command(name,argv,cwd=PROJECT,env=None):
        with (out/name).open('w') as log:subprocess.run(argv,cwd=cwd,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=900,close_fds=True,check=True)
    try:
        names=git('ls-tree','-r','--name-only',source,'--','podcast-app').decode().splitlines()
        build_paths=[p for p in names if not p.startswith(('podcast-app/evidence/','podcast-app/docs/','podcast-app/tools/'))]
        for path in build_paths:
            require_path=PROJECT.parent/path
            assert require_path.read_bytes()==git('show',source+':'+path),path
        for path in CONTROLLERS+['tools/prepare_short_product_gate.py','tools/short_product_artifacts.init.gradle','tools/tests/test_short_product_scope.py','tools/tests/test_short_continuation_scope.py','tools/tests/test_short_export_scope.py','tools/tests/fixtures/SafRootReadinessFixture.java']:
            assert (PROJECT/path).read_bytes()==git('show',source+':podcast-app/'+path),path
        build_root=out/'build-source';build_root.mkdir()
        with tarfile.open(fileobj=io.BytesIO(git('archive',source,'--',*build_paths))) as tar:tar.extractall(build_root,filter='data')
        project=build_root/'podcast-app'
        baseline=PROJECT/'.local/duration-native-library-ready/cc473f8/app.apk';assert digest(baseline)==BASE_APK_SHA
        native={}
        with zipfile.ZipFile(baseline) as archive:
            for name in archive.namelist():
                if name.startswith('lib/arm64-v8a/') and name.endswith('.so'):
                    data=archive.read(name);native[name]=hashlib.sha256(data).hexdigest()
                    if Path(name).name not in ['liblitertlm_jni.so','libandroidx.graphics.path.so']:
                        p=project/'app/runtime-libs/arm64-v8a'/Path(name).name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
        assert len(native)==9
        properties=(PROJECT/'local.properties').read_text();assert 'native.runtime.enabled=true' in properties
        (project/'local.properties').write_text(properties.replace('native.runtime.enabled=true','native.runtime.enabled=false'))
        for route in ('gemma-4-e2b','supertonic-3'):
            assert digest(PROJECT/'.local/model-packs'/route/'current/manifest.json')==PACKS[route]
        assert digest(project/f'app/src/{asset_source}/assets/{asset}/contract.json')==contract_sha
        assert digest(project/'app/src/main/cpp/podcast_runtime.cpp')=='a3de4cd62a83275977036516ff1e0c04a3beda454794e7c331aed7b936ad8b35'
        if previous:
            if args.export_only:assert previous['kind']=='short-production-continuation' and previous['app']['sha256']==PRIOR['dev.qoralo.podcast.internal']
            else:assert previous['kind']==('short-production-continuation' if args.continuation else 'short-production-plumbing') and previous['contractSha256']==contract_sha
            assert digest(Path(previous['app']['path']))==previous['app']['sha256']
            for path in build_paths:
                if '/src/androidTest/' not in path and '/src/test/' not in path and '/src/testDebug/' not in path:
                    assert git('show',source+':'+path)==git('show',previous['sourceCommit']+':'+path),path
            save('app-reuse.json',{'previousCandidateSha256':digest(args.reuse_app_candidate),'appSha256':previous['app']['sha256'],
                 'compiledAppSourceAndBuildInputsUnchanged':True,'sourceAppCommit':previous['sourceCommit'],'noAppRepackOrRebuild':True})
        source_blobs={line.split('\t')[1].removeprefix('podcast-app/'):line.split('\t')[0].split()[2]
                      for line in git('ls-tree','-r',source,'--','podcast-app/app/src').decode().splitlines()}
        if args.continuation or args.export_only:
            assert git('rev-parse',source+':podcast-app/app/src/main')==git('rev-parse','9e3b513:podcast-app/app/src/main'),'continuation must not change production main code'
        save('source-proof.json',{'sourceCommit':source,'productionMainUnchangedForContinuation':args.continuation or args.export_only,'effectiveAppSrcTree':git('rev-parse',source+':podcast-app/app/src').decode().strip(),
             'allSourceBlobs':source_blobs,'buildInputs':{p.removeprefix('podcast-app/'):digest(PROJECT.parent/p) for p in build_paths},
             'explicitProperty':'-Ppodcast.shortProductE2e=true','longDefaultPropertiesUnchanged':True,
             'localPropertiesSha256':digest(project/'local.properties'),'sharedSourceOrGradleOutputsReplaced':False,'nativeCompilation':False,
             'nativeBaselineApkSha256':BASE_APK_SHA,'mode':'real normal coordinator/dispatcher/UI with owned observation/bounds-only debug seams; short plumbing, not long readiness'})
        init=PROJECT/'tools/short_product_artifacts.init.gradle'
        env=dict(os.environ,COHERENT_ARTIFACT_OUTPUT=str(out/'resolved-artifacts.json'))
        app_tasks=[] if previous else [':app:assembleDebug']
        command('host-build.log',['./gradlew','--offline','--max-workers=2','--no-configuration-cache','-Ppodcast.shortProductE2e=true','-I',str(init),
            ':app:coherentArtifactInputs',*app_tasks,':app:assembleDebugAndroidTest',':app:testDebugUnitTest',
            '--tests','dev.qoralo.podcast.e2e.ShortProductPolicyTest','--tests','dev.qoralo.podcast.generation.GenerationCoordinatorTest',
            '--tests','dev.qoralo.podcast.runtime.GemmaChapterPromptTest','--tests','dev.qoralo.podcast.runtime.GemmaEditPromptTest','--tests','dev.qoralo.podcast.e2e.ShortContinuationPolicyTest'],project,env)
        artifacts=json.loads((out/'resolved-artifacts.json').read_text())
        save('resolved-artifact-hashes.json',{r['file']:{'sha256':digest(Path(r['file'])),'bytes':Path(r['file']).stat().st_size} for r in artifacts})
        if previous:
            assert json.loads((out/'resolved-artifact-hashes.json').read_text())==json.loads((args.reuse_app_candidate.parent/'resolved-artifact-hashes.json').read_text())
            shutil.copy2(previous['app']['path'],out/'app.apk')
        else:shutil.copy2(project/'app/build/outputs/apk/debug/app-debug.apk',out/'app.apk')
        shutil.copy2(project/'app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk',out/'test.apk')
        generated=(project/'app/build/generated/source/buildConfig/debug/dev/qoralo/podcast/BuildConfig.java').read_text()
        assert 'SHORT_PRODUCT_E2E = true' in generated and '"supertonic-3"' in generated and PACKS['supertonic-3'] in generated
        (out/'generated-BuildConfig.java').write_text(generated)
        suites=list((project/'app/build/test-results/testDebugUnitTest').glob('TEST-*.xml'))
        counts={key:sum(int(ET.parse(p).getroot().attrib.get(key,0)) for p in suites) for key in ('tests','failures','errors','skipped')}
        assert counts['tests']>=6 and counts['failures']==counts['errors']==counts['skipped']==0,counts
        (out/'junit').mkdir()
        for p in suites:shutil.copy2(p,out/'junit'/p.name)
        with zipfile.ZipFile(out/'app.apk') as archive:
            actual={n:hashlib.sha256(archive.read(n)).hexdigest() for n in archive.namelist() if n.startswith('lib/') and n.endswith('.so')}
            assert actual==native,'native byte drift; stop, no rebuild/replacement authorized'
            if not args.export_only:assert hashlib.sha256(archive.read(f'assets/{asset}/contract.json')).hexdigest()==contract_sha
        if args.export_only:
            with zipfile.ZipFile(out/'test.apk') as archive:assert hashlib.sha256(archive.read(f'assets/{asset}/contract.json')).hexdigest()==contract_sha
        save('native-byte-proof.json',{'baseline':native,'candidate':actual,'allNineExact':True,'noCmakeOrModelCompilation':True})
        command('trusted-runtime.log',['python3',str(PROJECT/'tools/verify_apk_runtime.py'),'--apk',str(out/'app.apk'),'--output',str(out/'trusted-runtime.json')])
        sdk=Path('/home/moritz/Android/Sdk/build-tools/35.0.0')
        for kind in ('app','test'):
            command(kind+'-manifest.txt',[str(sdk/'aapt2'),'dump','xmltree','--file','AndroidManifest.xml',str(out/(kind+'.apk'))])
            command(kind+'-signature.txt',[str(sdk/'apksigner'),'verify','--verbose','--print-certs',str(out/(kind+'.apk'))])
        command('focused-python.log',['python3','-m','unittest','discover','-s',str(PROJECT/'tools/tests'),'-p','test_short_product_scope.py','-v'])
        python_count=int(re.search(r'Ran (\d+) tests', (out/'focused-python.log').read_text()).group(1))
        if args.continuation:
            command('focused-continuation-python.log',['python3','-m','unittest','discover','-s',str(PROJECT/'tools/tests'),'-p','test_short_continuation_scope.py','-v'])
            python_count+=int(re.search(r'Ran (\d+) tests', (out/'focused-continuation-python.log').read_text()).group(1))
        if args.export_only:
            command('focused-export-python.log',['python3','-m','unittest','discover','-s',str(PROJECT/'tools/tests'),'-p','test_short_export_scope.py','-v'])
            python_count+=int(re.search(r'Ran (\d+) tests', (out/'focused-export-python.log').read_text()).group(1))
        save('host-checks.json',{'focusedJvm':counts,'focusedPython':python_count,'appAndTestAssembly':'app byte-exact reuse; test assembly passed' if previous else 'passed','native9':'byte-exact reuse',
             'dependencyInventory':len(artifacts),'physicalExecution':False,'fullBaselineOrUiMatrixRerun':False,'longReadiness':False})
        candidate={'schemaVersion':1,'kind':'short-product-export-only' if args.export_only else 'short-production-continuation' if args.continuation else 'short-production-plumbing','sourceCommit':source,'sourceDirty':False,'phoneAuthorized':False,
            'contractSha256':contract_sha,'contract':json.loads((project/f'app/src/{asset_source}/assets/{asset}/contract.json').read_text()),
            'hostGuardSha256':host_identity()['sha256'],'controllerSources':{p:digest(PROJECT/p) for p in CONTROLLERS},
            'privacyControllerSha256':digest(PROJECT/'tools/run_tts_only_gate.py'),'expectedPriorInstalledApks':PRIOR,
            'buildProperty':'-Ppodcast.shortProductE2e=true','modelPacks':{r:{'root':str(PROJECT/'.local/model-packs'/r/'current'),'manifestSha256':PACKS[r]} for r in ('gemma-4-e2b','supertonic-3')},
            'scope':'EXPORT-ONLY existing Ready master; ZERO new LLM/TTS/jobs; unchanged app' if args.export_only else 'MULTI-STAGE real owned review continuation; ZERO new LLM, ONE AUDIO job' if args.continuation else 'ONE owned short genuine production workflow; NOT a long input retry/full chapter readiness','status':'awaiting exact independent review and separate Pi phone release'}
        for kind in ('app','test'):
            p=out/(kind+'.apk');candidate[kind]={'path':str(p),'bytes':p.stat().st_size,'sha256':digest(p)}
        candidate['evidenceBindings']={p.relative_to(out).as_posix():{'bytes':p.stat().st_size,'sha256':digest(p)} for p in out.rglob('*')
            if p.is_file() and 'build-source' not in p.relative_to(out).parts and p.suffix!='.apk'}
        save('candidate.json',candidate)
        print(json.dumps({'output':str(out),'candidateSha256':digest(out/'candidate.json'),'appSha256':candidate['app']['sha256'],
            'testSha256':candidate['test']['sha256'],'hostGuardSha256':candidate['hostGuardSha256'],'sourceCommit':source},indent=2))
    except BaseException as error:
        save('build-failure.json',{'error':repr(error),'adbUsed':False,'modelCalls':0});raise


if __name__=='__main__':main()
