#!/usr/bin/env python3
"""Build a fresh private standalone HTP stage with exact shared tensor copies."""
import argparse
import json
from pathlib import Path
import shutil
from materialize import REPO, sha

ROOT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--latent-length',type=int,required=True)
    p.add_argument('--stage',type=Path,required=True)
    a=p.parse_args()
    if not a.stage.resolve().is_relative_to((ROOT/'.local').resolve()):raise ValueError('private stage required')
    common=ROOT.parent/'.local/common/input-bundle'
    expected={'text_ids.i64':3200*8,'text_mask.f32':3200*4,'style_dp.f32':128*4,
              'style_ttl.f32':12800*4,'noise.f32':144*a.latent_length*4,
              'current_step.f32':5*4,'total_step.f32':4}
    for name,size in expected.items():
        if (common/name).stat().st_size!=size:raise ValueError('common input extent mismatch: '+name)
    a.stage.mkdir(parents=True,exist_ok=False)
    for part in ('lib','contexts','bundle'):(a.stage/part).mkdir()
    shutil.copy2(ROOT/'.local/bin/runner',a.stage/'runner')
    shutil.copy2(ROOT/'phone/run_remote.sh',a.stage/'run_remote.sh')
    previous=REPO/'experiments/0023-supertonic-qnn-precompiled-context-startup/.local/phone-stage/lib'
    libraries=('libc++_shared.so','libonnxruntime.so','libQnnHtp.so','libQnnHtpV73Skel.so','libQnnHtpV73Stub.so','libQnnSystem.so')
    for name in libraries:shutil.copy2(previous/name,a.stage/'lib'/name)
    # Prepare library intentionally absent: only precompiled contexts are loaded.
    for component in ('duration','text','vector','vocoder'):
        compiled=ROOT/'.local'/('compile-'+component+'-attempt-01')/'data'
        result=json.loads((compiled/'result.json').read_text())
        if result['status']!='constructor_export_passed_not_execution_proof':raise ValueError('constructor unsuccessful')
        if component=='vector' and result['inputs'][0]['shape']!=[1,144,a.latent_length]:raise ValueError('vector ABI differs')
        if component=='vocoder' and result['inputs'][0]['shape']!=[1,144,a.latent_length]:raise ValueError('vocoder ABI differs')
        for name,record in result['artifacts'].items():
            path=compiled/name
            if path.stat().st_size!=record['bytes'] or sha(path)!=record['sha256']:raise ValueError('context bytes changed')
            shutil.copy2(path,a.stage/'contexts'/name)
    for name in (*expected,'manifest.json'):shutil.copy2(common/name,a.stage/'bundle'/name)
    files=[p for p in sorted(a.stage.rglob('*')) if p.is_file()]
    manifest={str(p.relative_to(a.stage)):{'bytes':p.stat().st_size,'sha256':sha(p)} for p in files}
    (a.stage/'stage-manifest.sha256').write_text(''.join(f'{r["sha256"]}  {name}\n' for name,r in manifest.items()))
    result={'text_extent':3200,'latent_extent':a.latent_length,'files':manifest,
            'bytes':sum(r['bytes'] for r in manifest.values()),'source_ONNX_staged':False,
            'profiling':False,'cpu_fallback_allowed':False,'manifest_sha256':sha(a.stage/'stage-manifest.sha256')}
    (a.stage/'stage-provenance.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='files'},indent=2))


if __name__=='__main__':main()
