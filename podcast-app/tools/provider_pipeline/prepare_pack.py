#!/usr/bin/env python3
"""Assemble a NEW data-only reusable provider pack; never overwrite the installed/legacy pack."""
import hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
APP=ROOT/'podcast-app'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    old=APP/'.local/model-packs/supertonic-3/current'
    original=json.loads((old/'manifest.json').read_text())
    out=APP/'.local/model-packs/supertonic-3-provider/current';out.mkdir(parents=True,exist_ok=False)
    contexts={'duration':APP/'.local/provider-integration/qnn-duration-01/data',
        'text':APP/'.local/provider-integration/qnn-text-01/data',
        'vector':ROOT/'experiments/0037-supertonic-provider-pipeline/htp/.local/compile-vector-boundary-01/data',
        'vocoder':ROOT/'experiments/0037-supertonic-provider-pipeline/htp/.local/contexts-01/compile-vocoder/data'}
    approved=json.loads((ROOT/'experiments/0037-supertonic-provider-pipeline/htp/results/context-export-01.json').read_text())
    ledger={x['component']:x for x in approved['contexts'] if x['component'] in ('vector','vocoder')}
    for component,folder in contexts.items():
        receipt=json.loads((folder/'result.json').read_text())
        if receipt['status']!='constructor_export_passed_not_execution_proof' or receipt['session_Run_calls']!=0:raise ValueError('Unverified context')
        for name,binding in receipt['artifacts'].items():
            p=folder/name
            if p.stat().st_size!=binding['bytes'] or sha(p)!=binding['sha256']:raise ValueError('Context drift')
            if component in ledger and binding!=ledger[component]['artifacts'][name]:raise ValueError('Accepted shared context changed')
    files=[]
    for entry in original['files']:
        rel=entry['path']
        if rel.startswith('contexts/'):
            component=Path(rel).name.split('-')[0];source=contexts[component]/Path(rel).name
        else:
            source=old/rel
            if sha(source)!=entry['sha256']:raise ValueError('Original asset drift')
        destination=out/rel;destination.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,destination)
        files.append({'role':entry['role'],'path':rel,'bytes':destination.stat().st_size,'sha256':sha(destination)})
    provider={'frontendVersion':'supertonic-py-1.3.1-en-v1','segmentTarget':300,'speedHundredths':105,'gapFrames':13230,
        'language':'en','randomSeed':20260911,'rng':'NUMPY_LEGACY_MT19937','waveExtent':'FULL_NATIVE_VOCODER',
        'nativeTextEdges':True,'nativeLatentEdges':True,'durationSentencePrefix':1}
    contract=dict(original['contract'],textLength=320,latentLength=512,diffusionSteps=8,providerPipeline=provider)
    value=dict(original,id='supertonic-3-provider',version='py131-t320-l512-gather-v1',contract=contract,files=files)
    (out/'manifest.json').write_text(json.dumps(value,indent=2)+'\n')
    binding={'id':value['id'],'version':value['version'],'manifestSha256':sha(out/'manifest.json'),'files':files,
        'providerPipeline':provider,'genericTextRange':[1,320],'genericNativeLatentRange':[1,512],
        'normalizerUnicodeTableSha256':'e77ed73ff2a4dfb12e7273ce959adf554b8d5aff559d77a2a81aaf3be127a456',
        'legacyVectorStrictGateRemainsFailed':True,'newPhysicalValidation':False,'newWaveListening':'not_reviewed'}
    (APP/'config/trusted-supertonic-provider.json').write_text(json.dumps(binding,indent=2)+'\n')
    print(json.dumps({'manifestSha256':binding['manifestSha256'],'files':len(files),'bytes':sum(x['bytes'] for x in files),'physicalValidated':False}))
if __name__=='__main__':main()
