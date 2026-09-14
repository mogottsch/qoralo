#!/usr/bin/env python3
"""Saved-only named-IO/raw-code audit. File/ID bindings are not native-buffer identity."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shlex

import numpy as np
import yaml

TRACK=Path(__file__).resolve().parents[1]
STAGE=TRACK/'.local/frozen-stages/htp-power-edge-stage-01'
STAGE_SHA='51053482d9d0d198b43343830503d8c1c3d2ee3337c4ccb598e792248dffb993'
CASES=('normalization_chain','normalization_exposed')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def patterns(raw,shape):
    if len(shape)!=3 or shape[0]!=1 or shape[1]!=128:raise ValueError('exact authored128-row shape required')
    words=np.asarray(raw)
    if words.dtype!=np.uint16 or words.size!=int(np.prod(shape)):raise ValueError('native UINT16 size mismatch')
    values=words.reshape(shape);rows=[]
    for i in range(4):
        selected=values[:,i::4,:];unique=np.unique(selected)
        rows.append({'input_pattern_index':i,'rows':32,'values_checked':int(selected.size),'distinct_code_count':int(unique.size),'codes_bounded':unique[:16].astype(int).tolist(),'minimum':int(unique[0]),'maximum':int(unique[-1]),'codes_truncated':unique.size>16})
    return rows


def analyze(run_root,out):
    run_root=Path(run_root).resolve();out=Path(out).resolve()
    if not run_root.is_relative_to(TRACK/'.local/htp-chain-phone-runs') or not out.is_relative_to(TRACK/'.local/htp-chain-offline'):raise ValueError('owned saved roots required')
    if sha(STAGE/'frozen-manifest.json')!=STAGE_SHA:raise ValueError('frozen actual IO metadata changed')
    manifest=json.loads((STAGE/'frozen-manifest.json').read_text());expected={g['name']:g for g in manifest['graphs']};collection=json.loads((run_root/'collection.json').read_text())
    if collection.get('reviewed_stage_digest')!=STAGE_SHA or not collection.get('identity_verified') or not collection.get('input_hashes_verified') or collection.get('process_exit_code')!=0 or not collection.get('raw_pull_completed') or not collection.get('phone_lock_released') or collection.get('cleanup')!='verified_absent' or not collection.get('postflight_app_identity',{}).get('verified'):raise ValueError('successful released and postflight-verified saved window required')
    if [r['case'] for r in collection.get('case_results',[])]!=list(CASES) or any(r.get('process_exit_code')!=0 for r in collection['case_results']):raise ValueError('exact selected case results required')
    records=[];buffers={};total=0;limits={}
    for case in CASES:
        root=run_root/'raw/device'/case/'outputs';meta=yaml.safe_load((root/'execution_metadata.yaml').read_text());command=shlex.split(meta['command']);lists=command[command.index('--input_list')+1].split(',');index=list(expected).index(case)
        if meta['inferences_completed']!=1 or lists[0]!='__' or sum(x!='__' for x in lists)!=1 or lists[index]=='__' or command[command.index('--num_inferences')+1]!='1':raise ValueError('wrong graph selection or execution count')
        described={g['graph_name']:g for g in meta['graphs']};graph=described[case];expected_io=expected[case]['outputs'];actual_io={t['tensor_name']:t for t in graph['output_tensors']}
        if set(actual_io)!=set(expected_io) or len({t['id'] for t in actual_io.values()})!=len(actual_io):raise ValueError('ambiguous output names/IDs')
        for name,io in expected_io.items():
            actual=actual_io[name]
            if actual['id']!=io['id'] or actual['datatype']!=io['dataType'] or actual['dimensions']!=io['dimensions']:raise ValueError('execution-to-compiled output binding mismatch')
            path=root/case/'Result_0'/(name+'_native.raw');shape=io['dimensions'];size=int(np.prod(shape))*2
            if path.stat().st_size!=size:raise ValueError('incomplete raw output')
            data=path.read_bytes();words=np.frombuffer(data,dtype='<u2');groups=patterns(words,shape);sidecar=json.loads((root/case/(name+'_native.raw.json')).read_text())
            if sidecar['Datatype']!=io['dataType'] or sidecar['Dimensions']!=shape:raise ValueError('native-output sidecar binding mismatch')
            records.append({'case':case,'tensor':name,'tensor_id':actual['id'],'shape':shape,'datatype':actual['datatype'],'bytes':size,'sha256':hashlib.sha256(data).hexdigest(),'raw_path':str(path),'exact_grid_from_compiled_context':io['quantizeParams']['scaleOffset'],'rounded_sidecar_grid_not_used_as_exact_scale':sidecar.get('QuantaziationParams'),'patterns':groups});buffers[(case,name)]=data;total+=size
        if set(root.rglob('*.raw'))!={root/case/'Result_0'/(n+'_native.raw') for n in expected_io}:raise ValueError('extra/unselected raw outputs present')
        text=(run_root/'raw/device'/(case+'.limits-pre-exec.txt')).read_text();limits[case]={key:[int(v) for v in re.search(pattern,text,re.M).groups()] for key,pattern in [('AS',r'^Max address space\s+(\d+)\s+(\d+)'),('FSIZE',r'^Max file size\s+(\d+)\s+(\d+)')]}
    if total!=1180416:raise ValueError('exact six-output byte total required')
    if any(v!={'AS':[12884901888,12884901888],'FSIZE':[8388608,8388608]} for v in limits.values()):raise ValueError('actual per-phase limits differ')
    result={'classification':'valid_two_selected_HTP_chain_raw_outputs','run_id':collection['run_id'],'actual_selected_executions':{name:1 for name in CASES},'Power_repeated':False,'outputs':records,'total_raw_bytes':total,'normalized_final_bytes_identical':buffers[(CASES[0],'normalized')]==buffers[(CASES[1],'normalized')],'exposed_mean_denom_bytes_identical':buffers[(CASES[1],'mean')]==buffers[(CASES[1],'denom')],'compiled_to_execution_name_ID_shape_dtype_bindings_verified':True,'native_output_buffer_addresses_fds_or_alias_independence_captured':False,'distinct_tensor_IDs_are_not_buffer_independence_proof':True,'literal_reference_zero_mean_add_codes':[0,0],'actual_low_pattern_materialized_mean_denom_codes':{name:[int(v) for v in np.frombuffer(buffers[(CASES[1],name)],dtype='<u2')[:2]] for name in ['mean','denom']},'readout_is_not_first_internal_kernel_localization':True,'optimizer_fusion_or_materialization_mechanism_identified':False,'full_reference_policy_changed':False,'epsilon_mean_floor_or_NaN_repair_adopted':False,'limits_pre_exec_bytes':limits,'model_or_phone_executed_by_analysis':False}
    out.mkdir(parents=True,exist_ok=False);(out/'analysis.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'classification':result['classification'],'normalized_bytes_identical':result['normalized_final_bytes_identical'],'mean_denom_bytes_identical':result['exposed_mean_denom_bytes_identical'],'tensor_ID_bindings_verified':True,'native_buffer_independence_proven':False,'outputs':[{'case':r['case'],'tensor':r['tensor'],'sha256':r['sha256'],'patterns':[p['codes_bounded'] for p in r['patterns']]} for r in records]},indent=2));return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run-root',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args();analyze(a.run_root,a.output_dir)
