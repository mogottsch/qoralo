#!/usr/bin/env python3
"""Prepare exact-text-context-only private diagnostic stage; no model execution."""
import argparse
import json
from pathlib import Path
import shutil
from materialize import sha
ROOT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--stage',type=Path,required=True);a=p.parse_args()
    if not a.stage.resolve().is_relative_to((ROOT/'.local').resolve()):raise ValueError('private stage required')
    full=ROOT/'.local/stage-attempt-01';pins=json.loads((full/'stage-provenance.json').read_text())['files']
    a.stage.mkdir(parents=True,exist_ok=False)
    for sub in ('lib','contexts'):(a.stage/sub).mkdir()
    for name,record in pins.items():
        if name.startswith('lib/') or name.startswith('contexts/text-'):
            source=full/name
            if source.stat().st_size!=record['bytes'] or sha(source)!=record['sha256']:raise ValueError('full-stage binding changed')
            shutil.copy2(source,a.stage/name)
    shutil.copy2(ROOT/'.local/bin/text-load-diagnostic',a.stage/'runner')
    shutil.copy2(ROOT/'phone/run_text_load_remote.sh',a.stage/'run_remote.sh')
    files={str(p.relative_to(a.stage)):{'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(a.stage.rglob('*')) if p.is_file()}
    assert not any('duration' in name or 'bundle' in name for name in files)
    (a.stage/'stage-manifest.sha256').write_text(''.join(f'{r["sha256"]}  {name}\n' for name,r in files.items()))
    result={'files':files,'bytes':sum(r['bytes'] for r in files.values()),'constructor_calls':1,'Run_calls':0,'profile':False,'native_alarm_seconds':180,'address_space_limit_bytes':5*1024**3,'DP_context_absent':True,'manifest_sha256':sha(a.stage/'stage-manifest.sha256')}
    (a.stage/'stage-provenance.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='files'},indent=2))


if __name__=='__main__':main()
