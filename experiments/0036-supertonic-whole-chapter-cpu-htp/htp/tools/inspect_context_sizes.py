#!/usr/bin/env python3
"""QNN System metadata only; conservative signed-allocation planning gate.

128MiB extra allowance and64MiB rounding are conservative planning margins,
NOT a claim that the proprietary allocator always uses this alignment/formula.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time
from materialize import sha

ROOT=Path(__file__).resolve().parents[1]
SDK=Path('/home/moritz/opt/qairt/2.49.0.260730')
IMAGE='sha256:b170f55a61548cc3a78eb667837934e0f2f8659bf7cd0db7a71ec40e90d2f321'
COMPONENTS=('duration','text','text_a','text_b','text3_a','text3_b','text3_c','vector','vocoder')
MiB=1024**2


def footprint(graph):
    v2=graph['graphBlobInfoV2']
    fields=('ioTensorSize','opDataSize','constSize','ddrTensorSize','sharedWeightsSize')
    values={k:int(v2[k]) for k in fields}
    values['spillFillBufferSize']=int(graph['graphBlobInfo']['info']['spillFillBufferSize'])
    base=sum(values.values());aligned=((base+128*MiB+64*MiB-1)//(64*MiB))*(64*MiB)
    limit=2**31-1;margin=limit-aligned
    return {'declared_storage_bytes':values,'summed_declared_bytes':base,
            'extra_planning_allowance_bytes':128*MiB,'conservative_rounding_bytes':64*MiB,
            'aligned_planning_estimate_bytes':aligned,'signed_size_limit_bytes':limit,
            'remaining_signed_margin_bytes':margin,'passes_conservative_gate':margin>=64*MiB,
            'claim_boundary':'Serialized storage sum plus conservative headroom/rounding, not a guaranteed native allocation or measured peak.'}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--components',nargs='+',choices=COMPONENTS,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    out=a.output.resolve()
    if not out.is_relative_to((ROOT/'.local').resolve()):raise ValueError('private output required')
    out.mkdir(parents=True,exist_ok=False)
    pins={}
    for c in a.components:
        result=json.loads((ROOT/'.local'/f'compile-{c}-attempt-01/data/result.json').read_text())
        path=ROOT/'.local'/f'compile-{c}-attempt-01/data/{c}-context_qnn.bin';pin=result['artifacts'][path.name]
        if sha(path)!=pin['sha256'] or path.stat().st_size!=pin['bytes']:raise ValueError('context changed')
        pins[c]=pin
    script='set -e; for c in "$@"; do /sdk/bin/x86_64-linux-clang/qnn-context-binary-utility --context_binary=/input/.local/compile-$c-attempt-01/data/$c-context_qnn.bin --json_file=/output/$c.json; done'
    argv=['docker','create','--init','--pull=never','--network=none','--memory=1g','--memory-swap=1g','--cpus=1','--pids-limit=64','--user',f'{os.getuid()}:{os.getgid()}',
          '--mount',f'type=bind,src={SDK},dst=/sdk,readonly','--mount',f'type=bind,src={ROOT},dst=/input,readonly','--mount',f'type=bind,src={out},dst=/output','--env','LD_LIBRARY_PATH=/sdk/lib/x86_64-linux-clang',IMAGE,'bash','-c',script,'metadata',*a.components]
    (out/'command.json').write_text(json.dumps(argv,indent=2)+'\n')
    cid=subprocess.run(argv,capture_output=True,text=True,check=True,timeout=10).stdout.strip();started=time.monotonic()
    try:
        process=subprocess.run(['docker','start','-a',cid],capture_output=True,text=True,timeout=30)
        (out/'stdout.log').write_text(process.stdout);(out/'stderr.log').write_text(process.stderr);process.check_returncode()
    finally:
        subprocess.run(['docker','rm','-f',cid],capture_output=True,text=True,check=True,timeout=10)
        absent=subprocess.run(['docker','container','inspect',cid],capture_output=True,text=True,timeout=10)
        (out/'cleanup.json').write_text(json.dumps({'cid':cid,'exit':absent.returncode,'stderr':absent.stderr},indent=2)+'\n')
        if absent.returncode==0 or 'No such container' not in absent.stderr:raise RuntimeError('container cleanup unverified')
    rows=[]
    for c in a.components:
        metadata=json.loads((out/(c+'.json')).read_text())['info'];graphs=metadata['graphs']
        if len(graphs)!=1:raise ValueError('unexpected graph count')
        rows.append({'component':c,'context_binary':pins[c],**footprint(graphs[0]['info'])})
    result={'evidence_class':'offline_QNN_System_metadata_no_context_load_or_Run','components':rows,'all_pass':all(r['passes_conservative_gate'] for r in rows),'elapsed_seconds':time.monotonic()-started,'utility_sha256':sha(SDK/'bin/x86_64-linux-clang/qnn-context-binary-utility'),'container_absent':True}
    (out/'footprints.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
