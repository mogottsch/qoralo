#!/usr/bin/env python3
"""Assemble the ignored direct-QNN Android stage without ORT/EPContext."""
from __future__ import annotations

import argparse, hashlib, json, os, shutil
from pathlib import Path


def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(8*1024*1024),b''): h.update(chunk)
    return h.hexdigest()


def link(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True,exist_ok=True)
    if destination.exists(): destination.unlink()
    os.link(source,destination)


def main() -> None:
    p=argparse.ArgumentParser()
    p.add_argument('--aot-dir',type=Path,required=True)
    p.add_argument('--prior-stage',type=Path,required=True)
    p.add_argument('--android-deps',type=Path,required=True)
    p.add_argument('--runner',type=Path,required=True)
    p.add_argument('--libcxx',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True)
    a=p.parse_args();stage=a.output_dir
    if stage.exists():shutil.rmtree(stage)
    stage.mkdir(parents=True)
    summary=json.loads((a.aot_dir/'summary.json').read_text())
    for part in summary['parts']:
        name=part['name'];link(a.aot_dir/name/'context_qnn.bin',stage/'contexts'/name/'context_qnn.bin')
    for name in ('embedding-quant.u8','embedding-scales.f32le','embedding-zp.u8','short.int32le'):
        link(a.prior_stage/name,stage/name)
    link(a.runner,stage/'direct_lfm2_qnn_runner')
    libs={
      a.android_deps/'qnnruntime/jni/arm64-v8a/libQnnHtp.so':'libQnnHtp.so',
      a.android_deps/'qnnruntime/jni/arm64-v8a/libQnnSystem.so':'libQnnSystem.so',
      a.android_deps/'qnnruntime/jni/arm64-v8a/libQnnHtpV73Stub.so':'libQnnHtpV73Stub.so',
      a.android_deps/'qnnruntime/jni/arm64-v8a/libQnnHtpV73Skel.so':'libQnnHtpV73Skel.so',
    }
    libs[a.libcxx]='libc++_shared.so'
    for source,name in libs.items():link(source,stage/name)
    files=sorted(x for x in stage.rglob('*') if x.is_file())
    entries=[]
    with (stage/'SHA256SUMS').open('w') as out:
      for path in files:
        rel=path.relative_to(stage).as_posix();digest=sha256(path);out.write(f'{digest}  {rel}\n');entries.append({'path':rel,'bytes':path.stat().st_size,'sha256':digest})
    meta={'schema_version':1,'classification':'ignored_license_controlled_direct_qnn_android_stage','experiment':'0034-lfm2.5-2.6b-android-qnn-htp','route':'direct QNN contextCreateFromBinary/graphRetrieve/graphExecute; no ONNX Runtime or EPContext','bounded_request':{'tier':'short','prompt_tokens':171,'max_new_tokens':16},'context_count':263,'files':entries,'total_bytes_excluding_manifests':sum(x['bytes'] for x in entries),'retained_outside_git':True}
    (stage/'stage.json').write_text(json.dumps(meta,indent=2,sort_keys=True)+'\n')
    with (stage/'SHA256SUMS').open('a') as out:out.write(f"{sha256(stage/'stage.json')}  stage.json\n")
    print(json.dumps({'stage':str(stage),'payload_files':len(entries),'payload_bytes':meta['total_bytes_excluding_manifests']},indent=2))

if __name__=='__main__':main()
