#!/usr/bin/env python3
"""Freeze trace-runtime-only changes over the completed precision-path long stage."""
import argparse
import copy
import json
import os
from pathlib import Path
from prepare_frozen_genie_stage import copy_bound, write_input, sha256, verify

TRACK=Path(__file__).resolve().parents[1]
SOURCE=TRACK/'.local/frozen-stages/value-path-long-20260911T125353Z-01'
SOURCE_SHA='373ca1b67b3ce65920127eede27df84b2832a783aee14d934d328835bc9f0996'
BUILD=TRACK/'.local/selected-id-trace-runs/trace-build-20260911T142946Z-04'
BUILD_SHA='a7b9912463073ee9e74914e81f9b2cb049e84d87614f43139aa9fae3d6882581'
ELF_SHA='4eaa825b64870e3ca365db2d75491e2342ab92d3b9f49f6bee1b0bbee8ec1348'
LIB_SHA='43b9bf47d82aaf375582c0b5631f8b032f65aeeebc5a7758cb8ea7cae5af022a'
CPP_SHA='77a34d3f03b17709f3f6473f37cb7795314e51fa3e5e652b5c37d53cfd05c754'
POST_QUERY='dialog getTokenizer dialog1 tokenizer1\ntokenizer encodeFromFile tokenizer1 prompts/long.txt evidence/input-token-ids.txt\n'


def script_with_tokenizer_observation(original):
    anchor='profile save profile1 evidence/long-profile.json\n'
    if original.count(anchor)!=1 or original.count('dialog query ')!=1:
        raise ValueError('expected completed one-query script')
    result=original.replace(anchor,anchor+POST_QUERY)
    assert result.replace(POST_QUERY,'')==original
    return result


def prepare(stage):
    if stage.exists():raise FileExistsError('fresh independent stage required')
    if sha256(SOURCE/'frozen-manifest.json')!=SOURCE_SHA:raise RuntimeError('source stage changed')
    if sha256(BUILD/'build-result.json')!=BUILD_SHA or sha256(BUILD/'elf-validation.json')!=ELF_SHA:
        raise RuntimeError('actual build/ELF evidence changed')
    build=json.loads((BUILD/'build-result.json').read_text())
    elf=json.loads((BUILD/'elf-validation.json').read_text())
    if not build['success'] or build['actual_child_exit_code']!=0 or build['binary_sha256']!=LIB_SHA:
        raise RuntimeError('instrumented native build is not successful')
    if elf['unresolved_runner_genie_imports'] or not elf['selected_id_marker_present']:
        raise RuntimeError('required symbols/observer absent')
    source=json.loads((SOURCE/'frozen-manifest.json').read_text())
    stage.mkdir(parents=True,exist_ok=False,mode=0o700)
    files={}
    for name,identity in sorted(source['files'].items()):
        if name in ('lib/libGenie.so','exact-long.script'):continue
        files[name]=copy_bound(SOURCE/name,stage/name,identity)
    files['lib/libGenie.so']=copy_bound(Path(build['binary']),stage/'lib/libGenie.so',{'bytes':11622384,'sha256':LIB_SHA})
    files['lib/libc++_shared.so']=copy_bound(Path(elf['cpp_shared']['path']),stage/'lib/libc++_shared.so',{'bytes':9236352,'sha256':CPP_SHA})
    original=SOURCE/'exact-long.script'
    if sha256(original)!=source['files']['exact-long.script']['sha256']:raise RuntimeError('original query script changed')
    files['exact-long.script']=write_input(stage/'exact-long.script',script_with_tokenizer_observation(original.read_text()).encode())
    changed={k for k in source['files'] if files[k]!=source['files'][k]}
    assert changed=={'lib/libGenie.so','exact-long.script'}
    assert set(files)-set(source['files'])=={'lib/libc++_shared.so'}
    config=json.loads((stage/'gemma4-e2b-htp-cl4096-greedy.json').read_text())['dialog']
    if config['context']['bos-token']!=-1 or config['context']['eos-token']!=[1,106] or config['max-num-tokens']!=2048:
        raise RuntimeError('input/termination policy changed')
    manifest=copy.deepcopy(source)
    manifest.update({'classification':'frozen_host_selected_id_trace_stage_only','stage_id':stage.name,'files':files,
        'payload_bytes':sum(v['bytes'] for v in files.values()),'source_long_stage_digest':SOURCE_SHA,
        'copy_policy':'Independent read-only copies. Model, context, embeddings, config, input, tokenizer and runner unchanged. Replace Genie; add matching NDK C++ runtime; observe tokenizer only AFTER the unchanged query/profile.',
        'trace_runtime':{'build_result_sha256':BUILD_SHA,'elf_validation_sha256':ELF_SHA,'libGenie_sha256':LIB_SHA,'libcxx_sha256':CPP_SHA,
            'source_built_runtime_not_assumed_binary_equivalent':True,'dependency_lock_resolved_with_252_additions_no_prior_version_changes':True,
            'selected_ids':'stderr GEMMA_SELECTED_ID_V1: true sampler returns before text/stop filtering',
            'internal_stop_decision_exposed':False,
            'input_id_observation':'Post-query encodeFromFile using dialog tokenizer; full IDs, not direct prefill-tensor capture. Compare to1929 frozen IDs and actual query profile. Does not alter the preceding request.'},
        'runtime_loaded':False,'model_loaded':False,'adb_used':False,'phone_authorized':False,'registry_eligible':False})
    write_input(stage/'frozen-manifest.json',(json.dumps(manifest,indent=2,sort_keys=True)+'\n').encode())
    digest=sha256(stage/'frozen-manifest.json')
    sums=''.join(f'{v["sha256"]}  {k}\n' for k,v in sorted(files.items()))+f'{digest}  frozen-manifest.json\n'
    write_input(stage/'SHA256SUMS',sums.encode())
    verify(stage,digest)
    return {'stage':str(stage),'manifest_sha256':digest,'payload_bytes':manifest['payload_bytes'],'payload_files':len(files),'verified':True,'model_or_runtime_executed':False,'phone_access':False}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stage-dir',type=Path,required=True)
    p.add_argument('--result',type=Path,required=True)
    args=p.parse_args();stage=args.stage_dir.resolve()
    if not stage.is_relative_to((TRACK/'.local/frozen-stages').resolve()):p.error('fresh owned stage required')
    if args.result.exists():raise FileExistsError('result exists')
    os.umask(0o077)
    result=prepare(stage)
    args.result.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))
