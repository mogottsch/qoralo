#!/usr/bin/env python3
"""Offline QNN System metadata extraction for four app contexts; no context load, Run or phone access."""
import argparse,hashlib,json,os,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
SDK=Path('/home/moritz/opt/qairt/2.49.0.260730')
IMAGE='sha256:b170f55a61548cc3a78eb667837934e0f2f8659bf7cd0db7a71ec40e90d2f321'
MIB=1024**2

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    pack=ROOT/'podcast-app/.local/model-packs/supertonic-3-provider/current'
    manifest=json.loads((pack/'manifest.json').read_text());items=[]
    for component in ['duration','text','vector','vocoder']:
        file=pack/'contexts'/(component+'-context_qnn.bin')
        pin=next(x for x in manifest['files'] if x['path']=='contexts/'+file.name)
        if file.stat().st_size!=pin['bytes'] or hashlib.sha256(file.read_bytes()).hexdigest()!=pin['sha256']:raise ValueError('context drift')
        items += [component,'/input/contexts/'+file.name]
    command='set -eu; while [ "$#" -gt 0 ]; do label="$1"; binary="$2"; shift 2; /sdk/bin/x86_64-linux-clang/qnn-context-binary-utility --context_binary="$binary" --json_file="/output/$label.json"; done'
    args=['docker','create','--init','--pull=never','--network=none','--memory=1g','--memory-swap=1g','--cpus=1','--pids-limit=64','--user',f'{os.getuid()}:{os.getgid()}',
        '--mount',f'type=bind,src={SDK},dst=/sdk,readonly','--mount',f'type=bind,src={pack},dst=/input,readonly','--mount',f'type=bind,src={out},dst=/output',
        '--env','LD_LIBRARY_PATH=/sdk/lib/x86_64-linux-clang',IMAGE,'bash','-c',command,'metadata',*items]
    (out/'command.json').write_text(json.dumps(args,indent=2)+'\n')
    env={'HOME':str(Path.home()),'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'}
    cid=None;start=time.monotonic()
    try:
        cid=subprocess.check_output(args,text=True,timeout=15,env=env).strip()
        if len(cid)!=64 or any(c not in '0123456789abcdef' for c in cid):raise ValueError('invalid container identity')
        (out/'container-id.txt').write_text(cid+'\n')
        result=subprocess.run(['docker','start','-a',cid],capture_output=True,text=True,timeout=90,env=env)
        (out/'stdout.log').write_text(result.stdout);(out/'stderr.log').write_text(result.stderr);result.check_returncode()
    finally:
        if cid:
            remove=subprocess.run(['docker','rm','-f',cid],capture_output=True,text=True,timeout=15,env=env)
            absent=subprocess.run(['docker','container','inspect',cid],capture_output=True,text=True,timeout=10,env=env)
            (out/'cleanup.json').write_text(json.dumps({'cid':cid,'removed':remove.returncode==0,'absent':absent.returncode!=0 and 'No such' in absent.stderr})+'\n')
            if remove.returncode or absent.returncode==0:raise RuntimeError('owned metadata container cleanup failed')
    records=[]
    for component in ['duration','text','vector','vocoder']:
        graphs=json.loads((out/(component+'.json')).read_text())['info']['graphs']
        if len(graphs)!=1:raise ValueError('expected one graph')
        g=graphs[0]['info'];v=g['graphBlobInfoV2']
        declared={k:int(v[k]) for k in ['ioTensorSize','opDataSize','constSize','ddrTensorSize','sharedWeightsSize']}
        declared['spillFillBufferSize']=int(g['graphBlobInfo']['info']['spillFillBufferSize'])
        total=sum(declared.values());rounded=((total+128*MIB+64*MIB-1)//(64*MIB))*(64*MIB)
        binary=pack/'contexts'/(component+'-context_qnn.bin')
        records.append({'component':component,'binaryBytes':binary.stat().st_size,'binarySha256':hashlib.sha256(binary.read_bytes()).hexdigest(),
            'declared':declared,'summedDeclaredBytes':total,'planningAllowanceBytes':128*MIB,'roundedPlanningBytes':rounded})
    report={'scope':'offline QNN System metadata; no context loading/neural/phone calls','records':records,
        'declaredTotalBytes':sum(x['summedDeclaredBytes'] for x in records),'roundedPlanningTotalBytes':sum(x['roundedPlanningBytes'] for x in records),
        'binaryTotalBytes':sum(x['binaryBytes'] for x in records),'largestBinaryBytes':max(x['binaryBytes'] for x in records),
        'qualification':'Serialized storage fields may overlap or omit hidden allocations; planning sum + margins is not a proven allocator upper bound or measured total DSP memory.',
        'seconds':time.monotonic()-start,'phoneCalls':0,'neuralCalls':0}
    (out/'summary.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
