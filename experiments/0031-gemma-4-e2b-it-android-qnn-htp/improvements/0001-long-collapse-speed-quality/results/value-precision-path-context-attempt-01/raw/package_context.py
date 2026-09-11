#!/usr/bin/env python3
import gzip,hashlib,json,os
from pathlib import Path
os.umask(0o077)
P=Path(__file__).resolve().parent;T=P.parents[2]
OUT=T/'results/value-precision-path-context-attempt-01';OUT.mkdir(parents=True,exist_ok=False)
first=T/'.local/value-precision-context-runs/context-20260911T111220Z-01'
run=T/'.local/value-precision-context-runs/context-20260911T111531Z-02'
identities=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def keep(src,relative):
 b=src.read_bytes();packed=src.suffix in ('.stdout','.stderr','.jsonl','.log');dest=OUT/(relative+('.gz' if packed else ''));dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(gzip.compress(b,mtime=0) if packed else b);identities.append({'source':str(src),'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b),'retained':str(dest.relative_to(OUT)),'lossless_gzip':packed})
for root,label in ((first,'precompile-01'),(run,'compile-02')):
 for f in root.iterdir():
  if f.is_file():keep(f,f'raw/{label}/{f.name}')
 keep(root/'work/result.json',f'raw/{label}/work-result.json')
 for f in (root/'source-snapshots').iterdir():keep(f,f'raw/{label}/source-snapshots/{f.name}')
 if (root/'metadata-inspection').exists():
  for f in (root/'metadata-inspection').iterdir():
   if f.is_file():keep(f,f'raw/{label}/metadata-inspection/{f.name}')
compiled=json.loads((run/'work/result.json').read_text());guard=json.loads((run/'guard-result.json').read_text());metadata=json.loads((run/'context-validation.json').read_text())
assert compiled['compile_calls']==1 and guard['exit_code']==0 and guard['stop_reason'] is None and metadata['metadata_gate_passed']
result={'classification':'positive_full_precision_path_htp_context_compile_and_interface_metadata',
        'context':compiled['context'],'metadata_validation':metadata,'compiler_config':compiled['compiler_config'],
        'paired_cache_contract':compiled['pair_contract'],'inputs':compiled['inputs'],
        'compile_calls':1,'guard_result':guard,'compiler_elapsed_seconds':compiled['elapsed_seconds'],
        'compiler_ru_maxrss_kib':compiled['ru_maxrss_kib'],
        'first_attempt':json.loads((first/'precompile-failure.json').read_text()),
        'source_postcheck':json.loads((run/'source-postcheck.json').read_text()),
        'retained':identities,'claim_boundary':'One full paired HTP compilation with the unchanged accepted recipe and passing backend6/soc43/aliases/active30cache/120FLAT_BUFFER metadata. The full DLC precision island passed separately. No physical query or internal finalized-kernel precision/numerical/quality/speed claim.',
        'physical_execution':False,'inference':False,'phone_access':False,'registry_update':False,
        'prior_exact_long_negative_unchanged':True}
(OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(OUT,sha(OUT/'result.json'))
