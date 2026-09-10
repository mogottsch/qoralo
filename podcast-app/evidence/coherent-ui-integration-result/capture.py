import subprocess, json, tarfile, io, hashlib
from pathlib import Path
OUT=Path(__file__).resolve().parent
ADB='/home/moritz/Android/Sdk/platform-tools/adb'
APP='dev.vibevoice.podcast.internal'
def run(args, timeout=30, binary=False):
    cmd=[ADB,'-s','emulator-5556',*args]
    p=subprocess.run(cmd,capture_output=True,timeout=timeout)
    with (OUT/'capture-commands.jsonl').open('a') as log:
        log.write(json.dumps({'argv':cmd,'code':p.returncode,'stderr':p.stderr.decode(errors='replace')})+'\n')
    if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace'))
    return p.stdout if binary else p.stdout.decode(errors='replace')
def capture(run_id, frame='all', ime=False):
    folder=OUT/run_id;folder.mkdir(exist_ok=False)
    command=f'am instrument -w -r -e class dev.vibevoice.podcast.gallery.SyntheticGalleryCaptureTest -e galleryApproved synthetic-only -e galleryRunId {run_id} -e galleryFrame {frame}'
    if ime:command+=' -e galleryIme true'
    command+=f' {APP}.test/androidx.test.runner.AndroidJUnitRunner'
    budget=600 if frame=='all' else (40*len(frame.split(',')) if ',' in frame else 100)
    text=run(['shell',command],budget)
    (folder/'instrumentation.stdout').write_text(text)
    data=run(['exec-out','run-as',APP,'tar','-cf','-',f'files/ui-gallery/{run_id}'],120,True)
    (folder/'raw-capture.tar').write_bytes(data)
    prefix=f'files/ui-gallery/{run_id}/';manifest=[]
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        for member in archive:
            if not member.isfile():continue
            assert member.name.startswith(prefix)
            name=member.name[len(prefix):];relative=Path(name)
            assert not relative.is_absolute() and '..' not in relative.parts and name not in ('','.')
            payload=archive.extractfile(member).read();destination=folder/relative
            destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(payload)
            manifest.append({'name':name,'bytes':len(payload),'sha256':hashlib.sha256(payload).hexdigest()})
    (folder/'manifest.json').write_text(json.dumps(manifest,indent=2))
    passed='OK (' in text and 'FAILURES!!!' not in text
    print(run_id,'PASS' if passed else 'FAIL','files',len(manifest),flush=True)
    if not passed:print(text[-3000:],flush=True)
    return passed
if __name__=='__main__':
    import sys
    ok=capture(sys.argv[1],sys.argv[2],len(sys.argv)>3 and sys.argv[3]=='ime')
    raise SystemExit(0 if ok else 1)
