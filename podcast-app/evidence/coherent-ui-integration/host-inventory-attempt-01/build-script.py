from pathlib import Path
import datetime, hashlib, json, os, re, shutil, subprocess, tempfile, xml.etree.ElementTree as ET, zipfile

project = Path(__file__).resolve().parents[1]
repo = project.parent
source = 'fb16b90e493c24e2d0b5f289c393b4cd5b5abd4f'
out = project / '.local/integration-ready/fb16b90'
out.mkdir(parents=True, exist_ok=False)
plan = json.loads((project/'docs/coherent-ui-integration-source-plan.json').read_text())
base = plan['baseSource']

def git(*args, env=None):
    return subprocess.check_output(['git', *args], cwd=repo, env=env)

def sha(path):
    with Path(path).open('rb') as f: return hashlib.file_digest(f, 'sha256').hexdigest()

def dump(name, obj):
    (out/name).write_text(json.dumps(obj, indent=2)+'\n')

def entries(tree, prefix):
    result = {}
    for line in git('ls-tree','-r',tree,'--',prefix).decode().splitlines():
        desc,path = line.split('\t'); mode,kind,blob = desc.split()
        assert kind == 'blob', path
        result[path] = {'mode':mode,'gitBlob':blob}
    return result

def check_sources(expected):
    actual = {str(p.relative_to(repo)) for p in (project/'app/src').rglob('*') if p.is_file()}
    assert actual == set(expected), {'extra':list(actual-set(expected)), 'missing':list(set(expected)-actual)}
    for path,item in expected.items():
        assert not (repo/path).is_symlink(), path
        assert git('hash-object','--no-filters',path).decode().strip() == item['gitBlob'], path

old_files = sorted({p for family in ['ui-build','form-ack-ready','text-layout-ready','text-readability-ready','duration-ready','duration-build','frozen-candidates','wiring-ready']
    for p in (project/'.local'/family).rglob('*') if p.is_file() and (p.suffix=='.apk' or p.name=='candidate.json')})
old_hashes = {str(p.relative_to(project)):sha(p) for p in old_files}
outputs = {'app':project/'app/build/outputs/apk/debug/app-debug.apk', 'test':project/'app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk'}
originals = {kind:project/f'.local/frozen-candidates/c893963/{kind}.apk' for kind in outputs}
assert all(sha(outputs[k])==sha(originals[k]) for k in outputs)
assert sha(project/'.local/ui-build/polish-05/app.apk')=='4bbf162acbd93f6bff38c0aa042f044af9fd289a5f15f0b2e49ba6763daf1fcd'
shutil.copy2(Path(__file__),out/'build-script.py')
started = datetime.datetime.now(datetime.timezone.utc).isoformat()
try:
    with tempfile.TemporaryDirectory(prefix='podcast-coherent-index-') as tmp:
        env = dict(os.environ,GIT_INDEX_FILE=tmp+'/index')
        git('read-tree',base,env=env)
        paths = [r['path'] for r in plan['replacements']]
        assert len(paths)==16 and len(set(paths))==16
        for r in plan['replacements']:
            item = entries(r['sourceCommit'],r['path'])[r['path']]
            assert item['gitBlob']==r['gitBlob']
            git('update-index','--add','--cacheinfo',item['mode'],item['gitBlob'],r['path'],env=env)
        union = git('write-tree',env=env).decode().strip()
    assert git('diff','--name-only',base,union,'--','podcast-app/app/src').decode().splitlines()==sorted(paths)
    src_tree = git('rev-parse',union+':podcast-app/app/src').decode().strip()
    assert src_tree == plan['expectedCombinedAppSrcTree'] == git('rev-parse',source+':podcast-app/app/src').decode().strip()
    expected = entries(union,'podcast-app/app/src')
    check_sources(expected)
    source_proof = {'sourceCommit':source,'baseSource':base,'formSource':plan['approvedFormSource'],
        'readabilitySource':plan['approvedReadabilitySource'],'appSrcTree':src_tree,'replacements':plan['replacements'],
        'sourceFiles':[{ 'path':p,**v,'sha256':sha(repo/p)} for p,v in sorted(expected.items())],
        'noExcludedSources':True,'noExtraOrUntrackedSources':True,'allBlobBytesMatch':True}
    unchanged = ['app/src/debug','app/src/main/cpp','app/src/main/res','app/src/main/AndroidManifest.xml',
        'app/src/androidTest/java/dev/vibevoice/podcast/gallery','app/src/main/java/dev/vibevoice/podcast/generation',
        'app/src/main/java/dev/vibevoice/podcast/runtime','app/src/main/java/dev/vibevoice/podcast/model']
    unchanged += ['app/src/main/java/dev/vibevoice/podcast/ui/'+n for n in ['PlayerScreen.kt','GeneratingScreen.kt','LibraryScreen.kt','CommonUi.kt','theme']]
    invariants = {}
    for path in unchanged:
        full = 'podcast-app/'+path
        a = git('rev-parse',base+':'+full).decode().strip(); b = git('rev-parse',source+':'+full).decode().strip()
        assert a==b,path
        invariants[path]=a
    source_proof['unchangedPolish05BlobsOrTrees']=invariants
    dump('source-union.json',source_proof)
    # Track all source/build/test/tool/authority inputs, excluding narrative evidence.
    tracked = entries(source,'podcast-app')
    inputs = {}
    for path,item in tracked.items():
        rel = str(Path(path).relative_to('podcast-app'))
        if rel.startswith(('docs/','evidence/')) or rel in ['README.md','.gitignore']: continue
        assert git('hash-object','--no-filters',path).decode().strip()==item['gitBlob'],path
        inputs[path] = {**item,'sha256':sha(repo/path),'bytes':(repo/path).stat().st_size}
    props = {}
    for line in (project/'local.properties').read_text().splitlines():
        if '=' in line and not line.lstrip().startswith('#'):
            k,v=line.split('=',1);props[k.strip()]=v.strip()
    assert props['native.runtime.enabled']=='true'
    local_inputs = [project/'local.properties']+sorted((project/'app/runtime-libs').rglob('*.so'))
    headers = Path(props['onnxruntime.include.dir'])
    local_inputs += sorted(p for p in headers.rglob('*') if p.is_file())
    local_records = {str(p):{'sha256':sha(p),'bytes':p.stat().st_size} for p in local_inputs}
    dump('build-inputs.json',{'trackedInputs':inputs,'localInputs':local_records,
        'selectedLocalProperties':{k:props[k] for k in ['native.runtime.enabled','onnxruntime.include.dir','gemma.manifest.sha256','supertonic.manifest.sha256']},
        'buildScriptSha256':sha(out/'build-script.py'),'sourceCommit':source})
    init = out/'artifact-inputs.init.gradle'
    init.write_text('''import groovy.json.JsonOutput
allprojects { p ->
    if (p.path == ':app') {
        tasks.register('coherentArtifactInputs') {
            doLast {
                def records = []
                ['debugCompileClasspath','debugRuntimeClasspath','debugAndroidTestCompileClasspath','debugAndroidTestRuntimeClasspath','debugUnitTestCompileClasspath','debugUnitTestRuntimeClasspath','releaseCompileClasspath','releaseRuntimeClasspath'].each { name ->
                    p.configurations.getByName(name).resolvedConfiguration.resolvedArtifacts.each { a ->
                        records << [configuration:name, id:a.moduleVersion.id.toString(), classifier:a.classifier, file:a.file.canonicalPath]
                    }
                }
                [p.rootProject,p].unique().each { owner ->
                    owner.buildscript.configurations.getByName('classpath').resolvedConfiguration.resolvedArtifacts.each { a ->
                        records << [configuration:owner.path+':buildscript',id:a.moduleVersion.id.toString(),classifier:a.classifier,file:a.file.canonicalPath]
                    }
                }
                new File(System.getenv('COHERENT_ARTIFACT_OUTPUT')).text = JsonOutput.prettyPrint(JsonOutput.toJson(records))+'\\n'
            }
        }
    }
}
''')
    env = dict(os.environ,COHERENT_ARTIFACT_OUTPUT=str(out/'resolved-artifacts.json'),ANDROID_HOME='/home/moritz/Android/Sdk',ANDROID_SDK_ROOT='/home/moritz/Android/Sdk')
    command = ['./gradlew','--offline','--max-workers=2','--init-script',str(init),':app:coherentArtifactInputs',
        ':app:testDebugUnitTest',':app:lintDebug',':app:compileReleaseKotlin',':app:assembleDebug',':app:assembleDebugAndroidTest']
    dump('commands.json',{'host':command,'python':['python3','-m','unittest','discover','-s','tools/tests','-v'],'startedAt':started})
    with (out/'host-build.log').open('w') as log:
        subprocess.run(command,cwd=project,env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=900)
    with (out/'python-tests.log').open('w') as log:
        subprocess.run(['python3','-m','unittest','discover','-s','tools/tests','-v'],cwd=project,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=60)
    suites = sorted((project/'app/build/test-results/testDebugUnitTest').glob('TEST-*.xml'))
    counts = {key:sum(int(ET.parse(p).getroot().attrib.get(key,0)) for p in suites) for key in ['tests','failures','errors','skipped']}
    assert counts=={'tests':113,'failures':0,'errors':0,'skipped':0},counts
    text=(out/'python-tests.log').read_text();assert 'Ran 15 tests' in text and text.rstrip().endswith('OK')
    (out/'junit').mkdir()
    for p in suites:shutil.copy2(p,out/'junit'/p.name)
    artifact_records=json.loads((out/'resolved-artifacts.json').read_text())
    for item in artifact_records:
        p=Path(item['file']);item.update(sha256=sha(p),bytes=p.stat().st_size)
    dump('resolved-artifacts-hashes.json',artifact_records)
    for kind,path in outputs.items():shutil.copy2(path,out/f'{kind}.apk')
    def native_entries(apk):
        with zipfile.ZipFile(apk) as z:
            return {n:{'sha256':hashlib.sha256(z.read(n)).hexdigest(),'bytes':z.getinfo(n).file_size} for n in sorted(z.namelist()) if n.startswith('lib/') and n.endswith('.so')}
    old_native=native_entries(project/'.local/ui-build/polish-05/app.apk');new_native=native_entries(out/'app.apk')
    dump('native-payload-comparison.json',{'polish05':old_native,'combined':new_native,'exactEntrySetAndHashesMatch':old_native==new_native})
    assert old_native==new_native,'native payload changed: hold candidate, no preparation authorized'
    with (out/'runtime-verification.log').open('w') as log:
        subprocess.run(['python3','tools/verify_apk_runtime.py','--apk',str(out/'app.apk'),'--output',str(out/'apk-runtime-provenance.json')],cwd=project,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=60)
    with zipfile.ZipFile(out/'app.apk') as z:
        dex=b''.join(z.read(n) for n in z.namelist() if n.endswith('.dex'))
        for name in ['FormSubmissionState','FormSubmissionFeedbackKt']:
            assert ('Ldev/vibevoice/podcast/ui/'+name+';').encode() in dex,name
    classes=['ScreenSemanticsTest','UiInteractionRegressionTest','PasteImeRegressionTest','TextReadabilityPolicyTest','TextReadabilityClippingTest','FormSubmissionInteractionTest']
    with zipfile.ZipFile(out/'test.apk') as z:
        dex=b''.join(z.read(n) for n in z.namelist() if n.endswith('.dex'))
        for name in classes+['TextReadabilityAssertions','TextLayoutDiagnostics']:
            assert ('Ldev/vibevoice/podcast/ui/'+name+';').encode() in dex,name
        fixture=z.read('assets/text-layout/measured-labels.json')
        assert fixture==(project/'app/src/androidTest/assets/text-layout/measured-labels.json').read_bytes()
    check_sources(expected)
    assert all(sha(repo/p)==r['sha256'] for p,r in inputs.items())
    assert all(sha(p)==r['sha256'] for p,r in local_records.items())
    log=(out/'host-build.log').read_text()
    dump('host-checks.json',{'jvm':counts,'jvmTaskUpToDate':':app:testDebugUnitTest UP-TO-DATE' in log,'pythonPassed':15,
        'lintDebug':'passed','releaseKotlin':'passed','appAndTestAssembly':'passed','nativePayloadMatches05':True,
        'trustedRuntimeVerifier':'passed','formAndReadabilityClassesPresent':True,'fixtureSha256':hashlib.sha256(fixture).hexdigest(),
        'androidExecution':'not run; separate Nik gate required','modelsLoaded':False,'finishedAt':datetime.datetime.now(datetime.timezone.utc).isoformat()})
except BaseException as error:
    dump('build-failure.json',{'type':type(error).__name__,'message':str(error)})
    raise
finally:
    for kind,path in outputs.items():shutil.copy2(originals[kind],path)
    assert all(sha(outputs[k])==sha(originals[k]) for k in outputs)
    assert all(sha(project/path)==h for path,h in old_hashes.items())
    dump('restoration.json',{'oldFrozenFilesUnchanged':old_hashes,'c893OutputsRestored':{k:sha(p) for k,p in outputs.items()},'noSourceFilesReplaced':True})

proposed={'requiresSeparatePiAssignment':True,'operator':'Nik','serial':'emulator-5556','classes':classes,'methodsPerCondition':28,
    'conditions':['default OS','actual320dp/OSfont2'],'maximumInvocations':2,'perInvocationSeconds':180,
    'capture':{'librarySourcesSmokeSeconds':80,'pasteActualImeSmokeSeconds':100,'full15FramesPerConditionSeconds':600,
        'remainingImeInvocations':7,'perImeSeconds':100,'reuseSuccessfulDefaultPasteIme':True},'noRetries':True}
bindings={str(p.relative_to(out)):{'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(out.rglob('*')) if p.is_file()}
candidate={'schemaVersion':1,'status':'host-validated-awaiting-independent-coherent-gate','sourceCommit':source,'appSrcTree':src_tree,
    'appApk':{'path':str((out/'app.apk').relative_to(repo)),'sha256':sha(out/'app.apk')},
    'testApk':{'path':str((out/'test.apk').relative_to(repo)),'sha256':sha(out/'test.apk')},
    'effectiveComposition':{'base':base,'form':plan['approvedFormSource'],'readability':plan['approvedReadabilitySource'],'replacementPaths':16},
    'evidenceBindings':bindings,'proposedAndroidGate':proposed,'noEmulatorPhysicalModelExecution':True}
dump('candidate.json',candidate)
print(json.dumps({'source':source,'appSrcTree':src_tree,'appSha256':sha(out/'app.apk'),'testSha256':sha(out/'test.apk'),
    'candidateSha256':sha(out/'candidate.json'),'output':str(out)},indent=2))
