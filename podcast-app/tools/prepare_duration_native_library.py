#!/usr/bin/env python3
"""Offline manifest-only derivative of the exact frozen load-only APK; never ADB."""
from __future__ import annotations
import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile

from prepare_wiring_gate import PROJECT, digest
from duration_manifest_overlay import LIBRARY, ANDROID, patch_manifest
from duration_phone_guard import host_identity

BASE='3fd75c06481bcc709d45da5c4933347f348e9079'
PIN='806c9b6db0766eb3a7455cc2bd23a68c61153d257f4b0f0b7bb98ced6972238d'
SDK=Path('/home/moritz/Android/Sdk/build-tools/35.0.0')
OVERLAY='config/diagnostics/duration-fastrpc-native-library.xml'
INPUTS=['tools/prepare_duration_native_library.py','tools/duration_manifest_overlay.py',OVERLAY,
        'tools/tests/test_duration_manifest_overlay.py','tools/tests/fixtures/duration-baseline-manifest.axml']


def git(*args,env=None):
    return subprocess.check_output(['git',*args],cwd=PROJECT.parent,env=env)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-commit',required=True)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    source=git('rev-parse',args.source_commit).decode().strip()
    def save(name,value): (out/name).write_text(json.dumps(value,indent=2)+'\n')
    def run(name,argv):
        with (out/name).open('w') as log:
            subprocess.run(argv,cwd=PROJECT,stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,check=True,timeout=120,close_fds=True)
    try:
        baseline_path=PROJECT/'.local/duration-ready/3fd75c0/candidate.json'
        assert digest(baseline_path)==PIN
        baseline=json.loads(baseline_path.read_text())
        for kind in ('app','test'):
            item=baseline[kind];assert digest(Path(item['path']))==item['sha256']
        for path in INPUTS:
            assert (PROJECT/path).read_bytes()==git('show',source+':podcast-app/'+path),path
        element=ET.parse(PROJECT/OVERLAY).getroot().find('./application/uses-native-library')
        assert element is not None and element.attrib=={f'{{{ANDROID}}}name':LIBRARY,f'{{{ANDROID}}}required':'false'}
        manifest_path='podcast-app/app/src/main/AndroidManifest.xml'
        original_source=git('show',BASE+':'+manifest_path)
        anchor=b'        <uses-native-library android:name="libOpenCL.so" android:required="false" />'
        assert original_source.count(anchor)==1 and LIBRARY.encode() not in original_source
        effective_source=original_source.replace(anchor,anchor+b'\n        <uses-native-library android:name="libcdsprpc.so" android:required="false" />')
        (out/'effective-AndroidManifest.xml').write_bytes(effective_source)
        blob=subprocess.check_output(['git','hash-object','-w','--stdin'],input=effective_source,cwd=PROJECT.parent).decode().strip()
        with tempfile.TemporaryDirectory(prefix='duration-manifest-index-') as tmp:
            env=dict(os.environ,GIT_INDEX_FILE=tmp+'/index')
            git('read-tree',BASE,env=env);git('update-index','--cacheinfo','100644',blob,manifest_path,env=env)
            tree=git('write-tree',env=env).decode().strip()
        assert git('diff','--name-only',BASE,tree).decode().splitlines()==[manifest_path]
        app_src=git('rev-parse',tree+':podcast-app/app/src').decode().strip()
        baseline_apk=Path(baseline['app']['path'])
        with zipfile.ZipFile(baseline_apk) as old:
            manifest=old.read('AndroidManifest.xml');changed,delta=patch_manifest(manifest)
            assert manifest==(PROJECT/'tools/tests/fixtures/duration-baseline-manifest.axml').read_bytes()
            (out/'baseline-AndroidManifest.axml').write_bytes(manifest);(out/'new-AndroidManifest.axml').write_bytes(changed)
            # Preserve every ZIP entry. Existing APK v2/v3 signing blocks are outside the ZIP entries.
            with zipfile.ZipFile(out/'unsigned.apk','w') as new:
                for info in old.infolist():
                    assert not re.fullmatch(r'META-INF/(?:[^/]+\.(?:SF|RSA|DSA|EC)|MANIFEST\.MF)',info.filename), 'unexpected v1 signature'
                    new.writestr(info,changed if info.filename=='AndroidManifest.xml' else old.read(info.filename))
        run('zipalign.log',[str(SDK/'zipalign'),'-P','16','-f','4',str(out/'unsigned.apk'),str(out/'aligned.apk')])
        run('signing.log',[str(SDK/'apksigner'),'sign','--ks',str(Path.home()/'.android/debug.keystore'),
            '--ks-key-alias','androiddebugkey','--ks-pass','pass:android','--key-pass','pass:android',
            '--v1-signing-enabled','false','--v2-signing-enabled','true','--v3-signing-enabled','true',
            '--v4-signing-enabled','false','--out',str(out/'app.apk'),str(out/'aligned.apk')])
        shutil.copy2(baseline['test']['path'],out/'test.apk')
        for label,path in [('baseline-app',baseline_apk),('new-app',out/'app.apk'),('test',out/'test.apk')]:
            run(label+'-signature.txt',[str(SDK/'apksigner'),'verify','--verbose','--print-certs',str(path)])
        def certificate(label):
            return re.search(r'Signer #1 certificate SHA-256 digest: ([0-9a-f]+)',(out/(label+'-signature.txt')).read_text()).group(1)
        assert certificate('baseline-app')==certificate('new-app')==certificate('test')
        for label,path in [('baseline',baseline_apk),('new',out/'app.apk')]:
            run(label+'-platform-manifest.txt',[str(SDK/'aapt2'),'dump','xmltree','--file','AndroidManifest.xml',str(path)])
        entries=[]
        with zipfile.ZipFile(baseline_apk) as old,zipfile.ZipFile(out/'app.apk') as new:
            assert old.namelist()==new.namelist(),'ZIP entry set/order changed'
            assert new.read('AndroidManifest.xml')==changed
            for name in old.namelist():
                a=old.read(name);b=new.read(name)
                assert name=='AndroidManifest.xml' or a==b,name
                entries.append({'name':name,'bytesBefore':len(a),'bytesAfter':len(b),'sha256Before':hashlib.sha256(a).hexdigest(),
                    'sha256After':hashlib.sha256(b).hexdigest(),'unchanged':a==b})
        native=[e for e in entries if e['name'].startswith('lib/') and e['name'].endswith('.so')]
        dex=[e for e in entries if e['name'].endswith('.dex')]
        assert len(native)==9 and all(e['unchanged'] for e in native) and all(e['unchanged'] for e in dex)
        run('trusted-runtime.log',['python3','tools/verify_apk_runtime.py','--apk',str(out/'app.apk'),'--output',str(out/'trusted-runtime.json')])
        assert all(digest(Path(baseline[k]['path']))==baseline[k]['sha256'] for k in ('app','test'))
        save('source-proof.json',{'baseSource':BASE,'overlaySource':source,'overlayPath':OVERLAY,'effectiveAppSrcTree':app_src,
            'effectiveManifestGitBlob':blob,'onlyChangedSourcePath':manifest_path,'buildMethod':'reuse frozen APK payload; patch only binary manifest declaration; zipalign and re-sign with same debug certificate',
            'inputs':{p:digest(PROJECT/p) for p in INPUTS},'platformTools':{n:digest(SDK/n) for n in ('aapt2','zipalign','apksigner')},
            'sourceWorktreeNotReplaced':True,'javaKotlinCppOrModelCompilation':False})
        save('manifest-semantic-delta.json',delta);save('entry-proof.json',entries)
        save('host-checks.json',{'onlyChangedZipPayload':'AndroidManifest.xml','allDexResourcesNativeAndOtherEntriesUnchanged':True,
            'nativeEntries':len(native),'dexEntries':len(dex),'sameSigningCertificateSha256':certificate('new-app'),
            'testApkReusedExactly':digest(out/'test.apk')==baseline['test']['sha256'],'nativeVerifier':'passed',
            'apkSignatureVerification':'passed','binaryManifestPlatformParser':'passed','packagingChanges':'manifest string pool/node insertion; ZIP compression/alignment metadata and APK v2/v3 signatures recomputed',
            'adbUsed':False,'inferenceRequested':False})
        result=deepcopy(baseline)
        result.update(sourceCommit=source,sourceDirty=False,baseSourceCommit=BASE,effectiveAppSrcTree=app_src,
            sourceMode='frozen3fd75c0 APK/code + sole reviewed manifest declaration overlay; NOT current polished app',
            manifestLibrary={'name':LIBRARY,'required':False,'absencePolicy':'installation allowed; diagnostic reports failure; CPU fallback remains disabled'},
            baselineCandidateSha256=PIN,hostGuardSha256=host_identity()['sha256'],phoneAuthorized=False,
            status='host-validated-manifest-only-derivative-awaiting-independent-review-and-phone-slot')
        for kind in ('app','test'):
            p=out/(kind+'.apk');result[kind]={'path':str(p),'bytes':p.stat().st_size,'sha256':digest(p)}
        result['evidenceBindings']={p.name:{'sha256':digest(p),'bytes':p.stat().st_size} for p in sorted(out.iterdir()) if p.is_file() and p.suffix!='.apk'}
        save('candidate.json',result)
        print(json.dumps({'output':str(out),'sourceCommit':source,'effectiveAppSrcTree':app_src,
            'appSha256':result['app']['sha256'],'testSha256':result['test']['sha256'],'candidateSha256':digest(out/'candidate.json'),
            'hostGuardSha256':result['hostGuardSha256']},indent=2))
    except BaseException as error:
        save('build-failure.json',{'error':repr(error),'adbUsed':False});raise


if __name__=='__main__':main()
