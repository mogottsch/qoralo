#!/usr/bin/env python3
"""Preserve the completed FP32 worker, no tensor deserialization or model calls."""
from pathlib import Path
import hashlib,json,shutil,subprocess

OUT=Path(__file__).resolve().parent
EXP=OUT.parents[1]
WORK=EXP/'.local/fp32-controlled-position1-20260911/attempt-01/run'

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(name,value):(OUT/name).write_text(json.dumps(value,indent=2)+'\n')

def main():
    for p in WORK.rglob('*'):
        if not p.is_file():continue
        dst=OUT/'raw'/p.relative_to(WORK);dst.parent.mkdir(parents=True,exist_ok=True)
        if p.name=='outputs.pt':
            dst=Path(str(dst)+'.zst')
            with dst.open('xb') as f:subprocess.run(['zstd','-q','-3','-c',str(p)],stdout=f,check=True,timeout=30)
            recovered=subprocess.run(['zstd','-q','-dc',str(dst)],stdout=subprocess.PIPE,check=True,timeout=30).stdout
            assert len(recovered)==p.stat().st_size and hashlib.sha256(recovered).hexdigest()==digest(p)
            save('compression.json',{'original':str(p),'bytes':p.stat().st_size,'sha256':digest(p),'zstd':str(dst.relative_to(OUT)),'compressed_bytes':dst.stat().st_size,'compressed_sha256':digest(dst),'complete_recovery_verified':True,'original_preserved':True})
        else:assert not dst.exists();shutil.copy2(p,dst)
    r=json.loads((WORK/'data/result.json').read_text());c=json.loads((WORK/'data/comparison.json').read_text())
    summary={'status':r['status'],'worker_forward_seconds':r['forward_seconds'],'guard':json.loads((WORK/'supervisor.json').read_text()),'raw_outputs':r['raw_outputs'],
      'input_values_sha256':r['input_values_sha256'],'all73_finite':r['all_outputs_finite'],'input_mutated':r['input_mutation_observed'],'logits':{n:c[n]['outputs'][0] for n in c},
      'argmax':{'FP32':r['FP32_logits_argmax'],**{n:c[n]['logits_argmax'] for n in c}},'hidden_layers':[
       {'layer':i,'qdq':c['qdq']['outputs'][49+i],'qnn':c['qnn']['outputs'][49+i]} for i in range(24)],
      'limits':r['claim_limits'],'no_production_change':True,'fidelity_objective_complete':False}
    save('summary.json',summary)
    print('Packaged existing output; model calls0; compressed bytes',json.loads((OUT/'compression.json').read_text())['compressed_bytes'])

if __name__=='__main__':main()
