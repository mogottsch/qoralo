#!/usr/bin/env python3
"""Package completed full conversions/metadata gates, excluding model binaries."""
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil

os.umask(0o077)
HERE=Path(__file__).resolve().parent
TRACK=HERE.parents[2]
OUT=TRACK/'results/value-precision-path-full-conversion-attempt-01'
OUT.mkdir(parents=True,exist_ok=False)
retained=[]

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def keep(src,dst,compress=False):
    b=src.read_bytes();p=OUT/dst;p.parent.mkdir(parents=True,exist_ok=True)
    p.write_bytes(gzip.compress(b,mtime=0) if compress else b)
    retained.append({'source':str(src),'original_sha256':hashlib.sha256(b).hexdigest(),'original_bytes':len(b),'retained':dst,'lossless_gzip':compress})

rows=[]
for ar,name in [(128,'full-ar128-20260911T103001Z-01'),(1,'full-ar1-20260911T105448Z-01')]:
    root=TRACK/'.local/value-precision-full-runs'/name
    conversion=json.loads((root/'work/result.json').read_text())
    guard=json.loads((root/'guard-result.json').read_text())
    validation=json.loads((root/'combined-precision-validation.json').read_text())
    assert guard['exit_code']==0 and guard['stop_reason'] is None and validation['passed']
    for path in sorted(root.iterdir()):
        if path.is_file():
            compress=path.suffix in ('.stdout','.stderr','.jsonl')
            keep(path,f'raw/ar{ar}/{path.name}'+('.gz' if compress else ''),compress)
    keep(root/'work/result.json',f'raw/ar{ar}/conversion-result.json')
    for path in sorted((root/'source-snapshots').iterdir()):
        keep(path,f'raw/ar{ar}/source-snapshots/{path.name}')
    for path in sorted((root/'inspection-01').iterdir()):
        if path.is_file():
            compress=path.name.endswith(('.csv','.log'))
            keep(path,f'raw/ar{ar}/inspection/{path.name}'+('.gz' if compress else ''),compress)
    samples=[json.loads(x) for x in (root/'resources.jsonl').read_text().splitlines()]
    def peak(key):return max(int(x[key]) for x in samples if x.get(key) is not None)
    def same_time_peak():return max(int(x['memory.current'])+int(x['memory.swap.current']) for x in samples)
    rows.append({'ar':ar,'run_id':name,'dlc':conversion['dlc'],
                 'conversion_result_sha256':sha(root/'work/result.json'),'precision_validation_sha256':sha(root/'combined-precision-validation.json'),
                 'guard_elapsed_seconds':guard['elapsed_seconds'],'converter_elapsed_seconds':conversion['elapsed_seconds'],
                 'converter_ru_maxrss_kib':conversion['ru_maxrss_kib'],
                 'cgroup_memory_peak_bytes':peak('memory.peak'),'sampled_cgroup_swap_peak_bytes':peak('memory.swap.current'),
                 'sampled_same_time_memory_plus_swap_peak_bytes':same_time_peak(),
                 'measurement_boundary':'cgroup charges and per-process RSS are different; shared file mappings may be charged outside a later inspection cgroup',
                 'guard_exit_code':0,'guard_stop_reason':None,'final_memory_events':guard['final_sample']['memory.events'],
                 'operator_count':validation['operator_count'],'previous_operator_count':validation['previous_operator_count'],
                 'value_matmuls':sum(len(l['matmuls']) for l in validation['core_gate']['layers']),
                 'head_reassembly_groups':validation['coupled_exit_gate']['head_group_count'],
                 'precision_gate_passed':True,'compiled_full_context_proven':False,'inference':False,'phone_access':False})
for name in ('value_precision_path.py','value_precision_exits.py','validate_value_precision_full.py','compile_value_precision_context.py'):
    keep(TRACK/'tools'/name,'raw/gate-snapshots/'+name)
keep(HERE/'source-ar1-01/preparation.json','raw/ar1/source-preparation.json')
keep(HERE/'source-ar128-01/preparation.json','raw/ar128/source-preparation.json')
result={'classification':'positive_paired_full_dlc_post_projection_precision_island',
        'scope':'both full Gemma DLCs, internal tensor edges and active interfaces; not compiled-kernel precision or inference',
        'models':rows,'retained':retained,
        'precision_scope':['Post-quantized-V-projection normalization and cache export/import remain floating.',
                           'All56 selected value MatMuls per AR have Float16 operands/output; original quantized probability converts at boundary.',
                           'Seven coupled Float16 head Concats per AR return to the original fixed-point grids before unchanged output-projection signatures.'],
        'unchanged_boundaries':['Original ONNX graph bytes reused.','Parameter encodings preserved.','Original V-projection and probability tensor signatures/grids retained.','All active external IO signatures retained.'],
        'inactive_float_metadata':'Six selected Float16 IO annotations per AR changed to zero placeholders; raw annotations retained, not treated as integer encoding grids.',
        'limitations':['No generated output, latency/throughput or quality result.','Op-count changes are not a performance measure.',
                       'Neither a wholly FP16 model nor a cache-only numerical intervention: coupled MatMul and head reassembly are included.',
                       'FP16 may round differently; no numerical-state equality or repetition cause established.',
                       'Post-GC systemd default Result/ExecMainStatus fields are not standalone exit proof; conversions use actual child exit receipts. AR128 bare inspection exit remains unexposed, AR1 wrapper records actual exit0.'],
        'prior_exact_long_negative_unchanged':True,'canonical_campaign_unchanged':True,
        'next_stage':'Paired context compile/metadata is a separate run; not claimed by this result.',
        'phone_access':False,'inference':False,'registry_update':False}
(OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(OUT)
