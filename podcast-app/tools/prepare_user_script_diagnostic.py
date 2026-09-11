#!/usr/bin/env python3
"""Freeze an already-tested isolated build against committed source; no rebuild, ADB or model calls."""
import argparse, hashlib, json, re, shutil, subprocess, textwrap, xml.etree.ElementTree as ET, zipfile
from pathlib import Path
from prepare_wiring_gate import PROJECT, digest
from duration_phone_guard import host_identity


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source-commit',required=True);p.add_argument('--work',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--prior-candidate',type=Path,default=PROJECT/'.local/short-product-ready/export-only-03/candidate.json')
    mode=p.add_mutually_exclusive_group()
    mode.add_argument('--capacity-only',action='store_true')
    mode.add_argument('--existing-edit-probe',action='store_true')
    p.add_argument('--structured-edit',action='store_true');p.add_argument('--reference-request-sha256')
    a=p.parse_args()
    if a.existing_edit_probe:assert a.structured_edit,'Current EDIT source enables JSON schema; declare the changed setting explicitly'
    if a.structured_edit:assert a.existing_edit_probe and re.fullmatch(r'[0-9a-f]{64}',a.reference_request_sha256 or ''),'Missing prior actual request binding'
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    source=subprocess.check_output(['git','rev-parse',a.source_commit],cwd=PROJECT.parent,text=True).strip()
    build=a.work.resolve()/'build-source/podcast-app'
    names=subprocess.check_output(['git','ls-tree','-r','--name-only',source,'--','podcast-app/app/src','podcast-app/app/schemas','podcast-app/config','podcast-app/gradle','podcast-app/app/build.gradle.kts','podcast-app/build.gradle.kts','podcast-app/settings.gradle.kts','podcast-app/gradle.properties'],cwd=PROJECT.parent,text=True).splitlines()
    pins={}
    for name in names:
        relative=Path(name).relative_to('podcast-app');expected=subprocess.check_output(['git','show',source+':'+name],cwd=PROJECT.parent)
        assert (build/relative).read_bytes()==expected== (PROJECT/relative).read_bytes(),name
        pins[str(relative)]=hashlib.sha256(expected).hexdigest()
    assert 'native.runtime.enabled=false' in (build/'local.properties').read_text()
    config=(build/'app/build/generated/source/buildConfig/debug/dev/vibevoice/podcast/BuildConfig.java').read_text()
    assert 'SHORT_PRODUCT_E2E = true' in config and '"supertonic-3"' in config
    def save(name,data):(out/name).write_text(json.dumps(data,indent=2)+'\n')
    save('compiled-source-bindings.json',{'sourceCommit':source,'files':pins,'builtFromExactBytesBeforeCommitNomination':True,'nativeCompilation':False,'explicitProperty':'-Ppodcast.shortProductE2e=true'})
    (out/'generated-BuildConfig.java').write_text(config)
    structured=None
    if a.structured_edit:
        source_text=(build/'app/src/main/java/dev/vibevoice/podcast/runtime/GemmaEditResponseFormat.kt').read_text()
        schema=textwrap.dedent(re.search(r'EDIT_REVISION_JSON_SCHEMA = """\n(.*?)\n"""\.trimIndent\(\)',source_text,re.S).group(1))
        json.loads(schema);(out/'edit-response-schema.json').write_text(schema)
        structured={'version':re.search(r'EDIT_RESPONSE_FORMAT_VERSION = "([^"]+)"',source_text).group(1),
            'schemaSha256':hashlib.sha256(schema.encode()).hexdigest(),'referenceRequestSha256':a.reference_request_sha256,
            'decoderConstraintChanged':True,'samplingScalarsUnchanged':True,'parserRepair':False}
    prior=json.loads(a.prior_candidate.read_text())
    with zipfile.ZipFile(prior['app']['path']) as apk:
        previous={n:hashlib.sha256(apk.read(n)).hexdigest() for n in apk.namelist() if n.startswith('lib/') and n.endswith('.so')}
    artifacts={'app':build/'app/build/outputs/apk/debug/app-debug.apk','test':build/'app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk'}
    for name,path in artifacts.items():shutil.copy2(path,out/(name+'.apk'))
    with zipfile.ZipFile(out/'app.apk') as apk:
        current={n:hashlib.sha256(apk.read(n)).hexdigest() for n in apk.namelist() if n.startswith('lib/') and n.endswith('.so')}
    assert len(current)==9 and current==previous
    save('native-byte-proof.json',{'native9':current,'allNineUnchanged':True})
    junit=out/'junit';junit.mkdir();counts={'tests':0,'failures':0,'errors':0,'skipped':0};skipped=[]
    for f in (build/'app/build/test-results/testDebugUnitTest').glob('TEST-*.xml'):
        root=ET.parse(f).getroot()
        for k in counts:counts[k]+=int(root.attrib[k])
        skipped += [(t.attrib['classname'],t.attrib['name']) for t in root.findall('testcase') if t.find('skipped') is not None]
        shutil.copy2(f,junit/f.name)
    optional_long_pack=('dev.vibevoice.podcast.wiring.TtsLongContractTest','explicitLocalPackPassesProductionVerifierAndFullReconstruction')
    allowed_skips={optional_long_pack} if a.existing_edit_probe else set()
    assert counts['tests']>=28 and counts['failures']==counts['errors']==0
    assert counts['skipped']==len(skipped) and set(skipped)<=allowed_skips,skipped
    save('junit-scope.json',{'counts':counts,'passed':counts['tests']-counts['skipped'],'skipped':skipped,
        'optionalSkipReason':'Only the unrelated opt-in long TTS pack reconstruction may skip when PODCAST_TTS_LONG_PACK is unset; no edit/recovery test may skip'})
    for log in a.work.glob('host-build-*.log'):shutil.copy2(log,out/log.name)
    def command(log,argv):
        with (out/log).open('w') as f:subprocess.run(argv,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=120)
    command('host-python.log',['python3','-m','unittest','discover','-s',str(PROJECT/'tools/tests'),'-p','test_user_script_diagnostic.py','-v'])
    command('trusted-runtime.log',['python3',str(PROJECT/'tools/verify_apk_runtime.py'),'--apk',str(out/'app.apk'),'--output',str(out/'trusted-runtime.json')])
    sdk=Path('/home/moritz/Android/Sdk/build-tools/35.0.0')
    for kind in ('app','test'):
        command(kind+'-signature.txt',[str(sdk/'apksigner'),'verify','--verbose','--print-certs',str(out/(kind+'.apk'))])
        command(kind+'-manifest.txt',[str(sdk/'aapt2'),'dump','xmltree','--file','AndroidManifest.xml',str(out/(kind+'.apk'))])
    value={'schemaVersion':1,'kind':'existing-edit-probe' if a.existing_edit_probe else ('user-capacity-guard' if a.capacity_only else 'user-script-diagnostic'),'sourceCommit':source,'controllerSha256':digest(PROJECT/'tools/run_user_script_diagnostic.py'),
        'hostGuardSha256':host_identity()['sha256'],'priorInstalled':{'dev.vibevoice.podcast.internal':prior['app']['sha256'],'dev.vibevoice.podcast.internal.test':prior['test']['sha256']},
        'scope':('One reconstructed saved EDIT request with private raw/cause capture; recovery transaction always rolled back and recovery UI observed; ZERO jobs/revisions/committed episode writes/TTS/Play' if a.existing_edit_probe else ('Existing genuine full draft: capacity guard/UI only; ZERO model calls/jobs/committed episode writes' if a.capacity_only else 'One real-input fresh owned SCRIPT episode; original failed episode untouched; no edits/TTS/Play/retry; app-private diagnostic receipts only')),
        'driverSeconds':None if a.existing_edit_probe else (90 if a.capacity_only else 540),
        'driverDeadlineReason':'No in-app process killer; host bounds instrumentation and performs fresh safe closure' if a.existing_edit_probe else None,
        'scriptPollingSeconds':None if a.capacity_only or a.existing_edit_probe else 480,
        'hostInstrumentationSeconds':300 if a.existing_edit_probe else (120 if a.capacity_only else 600),
        'focusedJvm':counts,'neuralSettingsUnchanged':not a.structured_edit,'structuredEditResponse':structured,
        'sourceNotesGuidanceAligned':a.capacity_only or a.existing_edit_probe,'neuralCauseFixed':False,
        'buildProperty':'-Ppodcast.shortProductE2e=true','modelPacks':prior['modelPacks']}
    for kind in ('app','test'):
        f=out/(kind+'.apk');value[kind]={'path':str(f),'sha256':digest(f),'bytes':f.stat().st_size}
    value['evidenceBindings']={str(f.relative_to(out)):{'sha256':digest(f),'bytes':f.stat().st_size} for f in out.rglob('*') if f.is_file() and f.suffix!='.apk'}
    save('candidate.json',value)
    print(json.dumps({'candidateSha256':digest(out/'candidate.json'),'app':value['app'],'test':value['test'],'jvm':counts},indent=2))

if __name__=='__main__':main()
