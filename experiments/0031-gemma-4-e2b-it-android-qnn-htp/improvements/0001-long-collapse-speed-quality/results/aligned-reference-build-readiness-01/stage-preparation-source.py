#!/usr/bin/env python3
"""Freeze the one aligned GPU reference. No model load/build or device access."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
from build_aligned_litert_reference import TRACK,REF,sha,capacity,GiB,SOURCE_SHA,LIB_SHA

BUILD=TRACK/'.local/aligned-reference-builds/aligned-build-20260911T172520Z-03'
BINARY_SHA='de02e7b9cbf36f2b6c5fbcf6cee4ee5f9bb5b7a6f65897bd616213b9d3ceff09'
MODEL_SHA='181938105e0eefd105961417e8da75903eacda102c4fce9ce90f50b97139a63c'
INPUT_SHA='3b5c04febbc9d55c529ee7ece510607203dbdc8256a6abc05ba0498cf4e52b64'
OLDSTAGE=TRACK/'.local/frozen-stages/selected-id-long-20260911T143756Z-01'


def verify(stage,expected_digest):
    stage=Path(stage);mp=stage/'frozen-manifest.json'
    if mp.is_symlink() or sha(mp)!=expected_digest:raise ValueError('stage manifest identity mismatch')
    m=json.loads(mp.read_text())
    if m['scope']!={'backend':'gpu','requests':1,'effective_input_tokens':1929,'context':8192,'max_output_tokens':2048}:raise ValueError('stage scope changed')
    if m['files']['bin/litert_lm_aligned_reference']['sha256']!=BINARY_SHA or m['files']['models/gemma-4-E2B-it.litertlm']['sha256']!=MODEL_SHA:raise ValueError('runner/model identity changed')
    if m['files']['lib/libLiteRt.so']['sha256']!=LIB_SHA or m['files']['expected-input-ids.int32le']['sha256']!=INPUT_SHA:raise ValueError('library/input identity changed')
    actual={str(p.relative_to(stage)) for p in stage.rglob('*') if p.is_file() or p.is_symlink()}
    if actual!=set(m['files'])|{'frozen-manifest.json','SHA256SUMS'}:raise ValueError('unexpected/missing stage file')
    for name,row in m['files'].items():
        p=stage/name
        if p.is_symlink() or not p.is_file() or p.stat().st_nlink!=1:raise ValueError('stage payload must be independent regular file')
        if (p.stat().st_size,sha(p),stat.S_IMODE(p.stat().st_mode))!=(row['bytes'],row['sha256'],row['mode']):raise ValueError('stage payload changed: '+name)
    expected=''.join(f"{m['files'][n]['sha256']}  {n}\n" for n in sorted(m['files']))+f'{expected_digest}  frozen-manifest.json\n'
    if (stage/'SHA256SUMS').read_text()!=expected:raise ValueError('stage checksums changed')
    return m


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--stage-name',required=True);a=p.parse_args()
    if not a.stage_name.startswith('aligned-gpu-') or '/' in a.stage_name or '..' in a.stage_name:p.error('fresh aligned-gpu name required')
    out=TRACK/'.local/frozen-stages'/a.stage_name
    result=json.loads((BUILD/'build-result.json').read_text())
    if not result['actual_success'] or result['binary_sha256']!=BINARY_SHA or result['source_sha256']!=SOURCE_SHA:raise ValueError('native build receipt mismatch')
    for phase in ('compile','link'):
        if json.loads((BUILD/(phase+'-exit.json')).read_text())['actual_exit_code']!=0:raise ValueError('native build phase not successful')
    c=capacity(TRACK)
    if c['mem_available']<8*GiB or c['disk_free']<64*GiB:raise ValueError('stage headroom insufficient')
    out.mkdir(parents=True,exist_ok=False,mode=0o700);files={}
    expected={}
    for line in (REF/'results/android-gpu-campaign/raw/remote-sha256-before.txt').read_text().splitlines():
        h,n=line.split();expected[n]=h
    sources={'bin/litert_lm_aligned_reference':BUILD/'work/bin/litert_lm_aligned_reference','models/gemma-4-E2B-it.litertlm':REF/'.local/model/gemma-4-E2B-it.litertlm','workloads/long.json':REF/'protocol/workloads/long.json','expected-input-ids.int32le':OLDSTAGE/'token-ids/long.int32le'}
    # Workload location is repository canonical bytes, independently hash-bound.
    sources['workloads/long.json']=TRACK.parents[3]/'protocols/android-llm-benchmark/workloads/inference-v1/long.json'
    expected.update({'bin/litert_lm_aligned_reference':BINARY_SHA,'expected-input-ids.int32le':INPUT_SHA})
    for n in expected:
        if n.startswith('lib/'):
            sources[n]=BUILD/'work/lib/libLiteRt.so' if n=='lib/libLiteRt.so' else REF/'.local/android-stage'/n
    for name,source in sources.items():
        if sha(source)!=expected[name]:raise ValueError('source mismatch '+name)
        dest=out/name;dest.parent.mkdir(parents=True,exist_ok=True,mode=0o700);shutil.copyfile(source,dest)
        mode=0o555 if name.startswith('bin/') else 0o444;dest.chmod(mode)
        if sha(dest)!=expected[name] or dest.stat().st_ino==source.stat().st_ino:raise ValueError('non-independent stage copy')
        files[name]={'sha256':expected[name],'bytes':dest.stat().st_size,'mode':mode,'source':str(source)}
    rendered=(OLDSTAGE/'prompts/long.txt').read_bytes()
    if not rendered.startswith(b'<bos>'):raise ValueError('unexpected original renderer prefix')
    rendered=rendered[5:];name='expected-rendered-long.txt';(out/name).write_bytes(rendered);(out/name).chmod(0o444)
    files[name]={'sha256':hashlib.sha256(rendered).hexdigest(),'bytes':len(rendered),'mode':0o444,'source':'only remove caller BOS from the frozen original rendered bytes; metadata BOS remains'}
    m={'schema_version':1,'classification':'single_aligned_reference_diagnostic','scope':{'backend':'gpu','requests':1,'effective_input_tokens':1929,'context':8192,'max_output_tokens':2048},'source_sha256':SOURCE_SHA,'native_build_result_sha256':sha(BUILD/'build-result.json'),'files':files,'android_runtime_execution_proven':False,'historical_gpu_binary_equivalence_proven':False}
    (out/'frozen-manifest.json').write_text(json.dumps(m,indent=2,sort_keys=True)+'\n');digest=sha(out/'frozen-manifest.json')
    (out/'SHA256SUMS').write_text(''.join(f"{files[n]['sha256']}  {n}\n" for n in sorted(files))+f'{digest}  frozen-manifest.json\n')
    (out/'frozen-manifest.json').chmod(0o444);(out/'SHA256SUMS').chmod(0o444)
    verify(out,digest)
    print(json.dumps({'stage':str(out),'digest':digest,'files':len(files),'payload_bytes':sum(r['bytes'] for r in files.values()),'independent_readonly':True,'model_load_or_adb_execution':False},indent=2))


if __name__=='__main__':main()
