#!/usr/bin/env python3
"""Saved-only complete raw-code audit of two isolated HTP operators, not a policy fix."""
import argparse
import hashlib
import json
from fractions import Fraction
from pathlib import Path
import re
import shlex

import numpy as np
import yaml

TRACK=Path(__file__).resolve().parents[1]
STAGE=TRACK/'.local/frozen-stages/htp-mean-add-stage-01'
DIGEST='f860ed18df22270801551be16499ecb9c2a3f10351f4b84d2da3c5bba7bc60b2'
CASES=('mean_edge','epsilon_add')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def compare_patterns(words,expected):
    words=np.asarray(words)
    if words.dtype!=np.uint16 or words.shape!=(128,) or len(expected)!=4:raise ValueError('exact128 UINT16 words/four frozen patterns required')
    full=np.resize(np.asarray(expected,dtype=np.uint16),128);difference=words.astype(np.int32)-full.astype(np.int32)
    return {'all_words_checked':128,'different_codes':int(np.count_nonzero(difference)),'maximum_absolute_code_error':int(np.max(np.abs(difference))),'expected_patterns':list(expected),'observed_codes_per_pattern':[np.unique(words[i::4]).astype(int).tolist() for i in range(4)],'generalized_rounding_floor_or_policy_inferred':False}


def exact_rescale_errors(input_words,output_words,graph):
    """Ideal real arithmetic using exact binary grid values, NOT DSP arithmetic."""
    inputs=np.asarray(input_words);outputs=np.asarray(output_words)
    if inputs.dtype!=np.uint16 or outputs.dtype!=np.uint16 or inputs.shape[0]!=128 or outputs.shape!=(128,):raise ValueError('128 native input/output rows required')
    ig=graph['inputs']['x']['quantizeParams']['scaleOffset'];og=graph['outputs']['y']['quantizeParams']['scaleOffset']
    si=Fraction(ig['scale']);so=Fraction(og['scale']);rows=[]
    for pattern in range(4):
        row=inputs[pattern].reshape(-1);n=row.size
        if graph['name']=='mean_edge':ideal=(int(row.sum(dtype=np.uint64))+ig['offset']*n)*si/n
        elif graph['name']=='epsilon_add':
            epsilon=graph['DLC_single_operator']['tensors']['epsilon'];eg=epsilon['grid'];ideal=(int(row[0])+ig['offset'])*si+(epsilon['raw_scalar'][0]+eg['offset'])*Fraction(eg['scale'])
        else:raise ValueError('only frozen isolated Mean/Add')
        coordinate=ideal/so-og['offset'];nearest=min(65535,max(0,round(coordinate)));observed=np.unique(outputs[pattern::4]).astype(int).tolist()
        if nearest!=graph['authored']['literal_float32_nearest_even_expected_codes'][pattern]:raise ValueError('exact rescale disagrees with frozen finite formula')
        errors=[(code+og['offset'])*so-ideal for code in observed]
        rows.append({'pattern':graph['authored']['row_patterns'][pattern],'ideal_real_exact':str(ideal),'ideal_real':float(ideal),'ideal_output_code_coordinate_exact':str(coordinate),'ideal_output_code_coordinate':float(coordinate),'nearest_even_code':nearest,'observed_codes':observed,'code_error_vs_nearest':[v-nearest for v in observed],'decoded_error_vs_ideal_exact':[str(v) for v in errors],'decoded_error_vs_ideal':[float(v) for v in errors],'error_in_output_steps':[float(v/so) for v in errors]})
    return {'arithmetic':'Exact rational use of compiled IEEE scale values; ties-to-even finite comparison, not hardware-law assertion','input_scale':float(si),'output_scale':float(so),'rescale_ratio_exact':str(si/so),'rescale_ratio':float(si/so),'patterns':rows}


def analyze(run_root,out):
    run_root=Path(run_root).resolve();out=Path(out).resolve()
    if not run_root.is_relative_to(TRACK/'.local/htp-mean-add-phone-runs') or not out.is_relative_to(TRACK/'.local/htp-mean-add-offline'):raise ValueError('owned saved paths required')
    if sha(STAGE/'frozen-manifest.json')!=DIGEST:raise ValueError('frozen control metadata changed')
    stage=json.loads((STAGE/'frozen-manifest.json').read_text());graphs={g['name']:g for g in stage['graphs']};c=json.loads((run_root/'collection.json').read_text())
    if c['reviewed_stage_digest']!=DIGEST or not c['identity_verified'] or not c['input_hashes_verified'] or c['process_exit_code']!=0 or not c['raw_pull_completed'] or not c['phone_lock_released'] or c['cleanup']!='verified_absent' or not c['postflight_app_identity']['verified']:raise ValueError('verified successful released window required')
    if [x['case'] for x in c['case_results']]!=list(CASES) or any(x['process_exit_code']!=0 for x in c['case_results']):raise ValueError('exact two successful selected cases required')
    from phone_htp_mean_add_discriminator import case_argv
    launch=TRACK/'.local/htp-mean-add-launches'/run_root.name;grant=json.loads((launch/'grant.json').read_text());exit_receipt=json.loads((launch/'controller-exit.json').read_text())
    if grant['source_freeze_commit']!='99ac077844abb733746f5c2183a785574f5ea013' or grant['pi_slot']!=c['pi_slot'] or grant['stage_digest']!=DIGEST or exit_receipt['actual_controller_exit']!=0:raise ValueError('grant/source/native-controller binding failed')
    cases=[];device=run_root/'raw/device'
    for index,name in enumerate(CASES):
        graph=graphs[name];root=device/name/'outputs';meta=yaml.safe_load((root/'execution_metadata.yaml').read_text());args=shlex.split(meta['command']);lists=args[args.index('--input_list')+1].split(',')
        if meta['inferences_completed']!=1 or len(lists)!=2 or sum(x!='__' for x in lists)!=1 or lists[index]=='__' or args!=case_argv(c['remote_root'],name):raise ValueError('one exact selected execution per process required')
        actual={x['graph_name']:x for x in meta['graphs']}[name]
        for role,items in [('inputs','input_tensors'),('outputs','output_tensors')]:
            expected=graph[role]
            if len(expected)!=1 or len(actual[items])!=1:raise ValueError('single input/output descriptor required')
            x=actual[items][0];old=expected[x['tensor_name']]
            if x['id']!=old['id'] or x['datatype']!=old['dataType'] or x['dimensions']!=old['dimensions']:raise ValueError('native descriptor binding mismatch')
        path=root/name/'Result_0/y_native.raw'
        if path.stat().st_size!=256 or set(root.rglob('*.raw'))!={path}:raise ValueError('exact one complete output and no other graph output required')
        words=np.fromfile(path,dtype='<u2');comparison=compare_patterns(words,graph['authored']['literal_float32_nearest_even_expected_codes']);limits=(device/(name+'.limits-pre-exec.txt')).read_text()
        for pattern,expected in [(r'^Max address space\s+(\d+)\s+(\d+)',[12884901888]*2),(r'^Max file size\s+(\d+)\s+(\d+)',[8388608]*2)]:
            if [int(v) for v in re.search(pattern,limits,re.M).groups()]!=expected:raise ValueError('actual process limits changed')
        input_path=STAGE/'inputs'/(name+'.uint16le')
        if sha(input_path)!=stage['files']['inputs/'+name+'.uint16le']['sha256']:raise ValueError('frozen native input changed')
        inputs=np.fromfile(input_path,dtype='<u2').reshape(128,-1);rescale=exact_rescale_errors(inputs,words,graph)
        cases.append({'case':name,'executions':1,'raw_bytes':256,'raw_sha256':sha(path),'raw_path':str(path),'input_sha256':sha(input_path),'execution_metadata_sha256':sha(root/'execution_metadata.yaml'),'limits_sha256':sha(device/(name+'.limits-pre-exec.txt')),'compiled_input_descriptor':graph['inputs'],'compiled_output_descriptor':graph['outputs'],'comparison':comparison,'exact_rescale_errors':rescale,'named_descriptor_bindings_verified':True,'single_output_graph':True})
    result={'classification':'valid_isolated_HTP_Mean_Add_controls','run_id':c['run_id'],'collection_sha256':sha(run_root/'collection.json'),'grant_sha256':sha(launch/'grant.json'),'stage_digest':DIGEST,'context_sha256':stage['context_sha256'],'cases':cases,'total_raw_bytes':512,'mean_low_code_one_observed_without_Add_Power_or_multi_output_chain':cases[0]['comparison']['observed_codes_per_pattern'][:2]==[[1],[1]],'epsilon_add_frozen_codes_unchanged':cases[1]['comparison']['different_codes']==0,'general_mean_floor_rounding_law_or_reference_patch_adopted':False,'QNN_model_defect_or_repetition_rootcause_claim':False,'model_or_phone_executed_by_analysis':False,'scope':'Only these operators/grids/shapes/inputs/runtime. Does not exclude all implementation or materialization mechanisms or justify a full-model policy.'}
    out.mkdir(parents=True,exist_ok=False);(out/'analysis.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run-root',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args();analyze(a.run_root,a.output_dir)
