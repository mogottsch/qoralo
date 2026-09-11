#!/usr/bin/env python3
"""Fresh full HTP stage using proven three-way TEXT network-depth partition."""
import argparse
import json
from pathlib import Path
import shutil
from materialize import sha
ROOT=Path(__file__).resolve().parents[1]
COMPONENTS=('duration','text3_a','text3_b','text3_c','vector','vocoder')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--stage',type=Path,required=True);a=p.parse_args()
    if not a.stage.resolve().is_relative_to((ROOT/'.local').resolve()):raise ValueError('private stage required')
    footprint=json.loads((ROOT/'.local/context-metadata-three-01/footprints.json').read_text())
    if not footprint['all_pass'] or tuple(x['component'] for x in footprint['components'])!=COMPONENTS:raise ValueError('allocation planning gate failed')
    proof=json.loads((ROOT/'.local/text-depth-three-cpu-proof-01/result.json').read_text())
    if proof['status']!='passed' or not proof['bitwise_equal'] or not proof['all_outputs_private_not_used_for_HTP']:raise ValueError('source-equivalence gate failed')
    old=ROOT/'.local/stage-attempt-01';old_manifest=json.loads((old/'stage-provenance.json').read_text())
    a.stage.mkdir(parents=True,exist_ok=False)
    for sub in ('lib','bundle','contexts'):(a.stage/sub).mkdir()
    for name,record in old_manifest['files'].items():
        if not name.startswith(('lib/','bundle/')):continue
        if sha(old/name)!=record['sha256'] or (old/name).stat().st_size!=record['bytes']:raise ValueError('frozen runtime/input differs')
        shutil.copy2(old/name,a.stage/name)
    for c in COMPONENTS:
        path=ROOT/'.local'/f'compile-{c}-attempt-01/data';result=json.loads((path/'result.json').read_text())
        if result['status']!='constructor_export_passed_not_execution_proof':raise ValueError('context export failed')
        for name,record in result['artifacts'].items():
            if sha(path/name)!=record['sha256'] or (path/name).stat().st_size!=record['bytes']:raise ValueError('context changed')
            shutil.copy2(path/name,a.stage/'contexts'/name)
    shutil.copy2(ROOT/'.local/bin/depth-runner',a.stage/'runner');shutil.copy2(ROOT/'phone/run_remote.sh',a.stage/'run_remote.sh')
    files={str(p.relative_to(a.stage)):{'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(a.stage.rglob('*')) if p.is_file()}
    if any('CPU-validation' in name or name=='contexts/text-context.onnx' for name in files):raise ValueError('forbidden baseline/test artifact')
    (a.stage/'stage-manifest.sha256').write_text(''.join(f'{r["sha256"]}  {name}\n' for name,r in files.items()))
    result={'text_extent':3200,'latent_extent':512,'logical_stages':4,'text_depth_parts':3,'actual_neural_Run_calls':{'duration':1,'text3_a':1,'text3_b':1,'text3_c':1,'vector':5,'vocoder':1},'files':files,'bytes':sum(r['bytes'] for r in files.values()),'source_ONNX_staged':False,'CPU_validation_outputs_staged':False,'profile':False,'cpu_fallback_allowed':False,'allocation_plan':footprint['components'],'manifest_sha256':sha(a.stage/'stage-manifest.sha256')}
    (a.stage/'stage-provenance.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('files','allocation_plan')},indent=2))


if __name__=='__main__':main()
