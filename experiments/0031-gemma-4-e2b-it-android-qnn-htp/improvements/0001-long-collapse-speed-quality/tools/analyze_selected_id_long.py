#!/usr/bin/env python3
"""Retain ONE saved source-runtime trace, then correlate genuine generation IDs.

No ADB, model inference, replay, policy edits or retrospective commercial IDs.
Run with the existing QAIRT Python environment for the frozen text metric.
"""
import argparse
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import struct
import types

import analyze_value_precision_long as previous
import analyze_selected_id_trace as trace_parser
import correlate_selected_id_trace as correlate
import phone_selected_id_long as scope

TRACK=Path(__file__).resolve().parents[1]
STAGE=TRACK/'.local/frozen-stages'/scope.STAGE_NAME
REFERENCE=TRACK/'results/value-precision-path-phone-long-attempt-01'
REFERENCE_SHA='35be64d08024f6029deec15e97b8b1d71cf9c94e1e425d8a53c90424e6671207'
REFERENCE_OUTPUT='5e3c8bff8006912eabc16b86783d59f387d9239042d55a3f3f312914610cc5c0'
sha=previous.sha


def signal_review(commands, command_root):
    result=[]
    for command in commands:
        if not command['operation'].startswith('signal.'):continue
        response=(command_root/Path(command['stdout']).name).read_text().strip()
        result.append({'operation':command['operation'],'response':response,'command_exit':command['code'],
                       'delivered_signal_observed':True if response=='SIGNALLED' else (False if response=='ABSENT' else None)})
    return result


def basic_scope(collection, observations, manifest, stdout, ordered_graphs):
    expected=['script exact-long.script']+(STAGE/'exact-long.script').read_text().splitlines()
    actual=[line[2:] for line in stdout.splitlines() if line.startswith('> ')]
    config=json.loads((STAGE/'gemma4-e2b-htp-cl4096-greedy.json').read_text())
    settings=config['dialog']
    checks={
      'reviewed_manifest':sha(STAGE/'frozen-manifest.json')==scope.STAGE_DIGEST==collection['reviewed_stage_digest'],
      'actual_inputs_verified':collection['input_hashes_verified'],
      'bound_new_runtime':collection['scope_adapter']['libGenie_sha256']==scope.LIB_SHA==manifest['files']['lib/libGenie.so']['sha256'],
      'one_exact_script_no_grammar_proposal_resume_calls':actual==expected,
      'basic_single_engine_lut_and_perlayer':settings['type']=='basic' and isinstance(settings['engine'],dict) and settings['embedding']['type']=='lut' and settings['perlayer-embedding']['type']=='lut',
      'unchanged_policy':settings['context']['bos-token']==-1 and settings['context']['eos-token']==[1,106] and settings['max-num-tokens']==2048 and settings['sampler']['greedy'] is True,
      'actual_one_query_completed':observations['query_completion_observed_beyond_exit_code'],
      'actual_prompt_count':observations['prompt']['profile_prompt_tokens']==1929,
      'rendered_input_exact':observations['prompt']['rendered_bytes_exact_in_runtime_stdout'],
      'primary_prefill_then_decode_order':ordered_graphs==['ar128']*16+['ar1']*max(0,(observations['actual_generated_tokens'] or 0)-1),
    }
    return {'confirmed':all(checks.values()),'checks':checks,
      'basis':'Actual stage/script/config/profile and graph order bound to the new BasicDialog source. No grammar/speculative/batch/resume operation is present. First selection follows COMPLETE prefill; intermediate prefill logits are not selected-ID records.',
      'source_original_basic_sha256':correlate.BASIC_SOURCE_SHA256,
      'runtime_equivalence_assumed':False}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run-dir',type=Path,required=True)
    p.add_argument('--result-dir',type=Path,required=True)
    args=p.parse_args();run=args.run_dir.resolve();result=args.result_dir.resolve()
    if run.parent!=TRACK/'.local/selected-id-phone-long-runs':p.error('saved trace root only')
    if result.parent!=TRACK/'results' or not result.name.startswith('selected-id-phone-long-'):p.error('fresh trace result only')
    # Raw retention is first and uses the already pinned privacy-aware helper.
    template,_,_,_=previous.adapted_functions()
    retain=types.FunctionType(previous.old_long.retain.__code__,dict(previous.old_long.retain.__globals__,RESULT=result))
    raw,private,compressed=retain(run)
    device=raw/'raw/device';commands_root=raw/'raw/commands'
    observe=types.FunctionType(template.__code__,dict(template.__globals__,FROZEN=STAGE))
    obs=observe(run,run/'raw/commands')
    obs['raw_genie_profile']['scope']='One instrumented-source-runtime engineering observation; logging/build differences preclude accepted speed comparison.'
    obs['stop']['missing_reason']='The accepted selected-ID trace and normal return/ceiling are observed. No independent internal terminal-branch enum is exposed; leave it null.'
    collection=json.loads((raw/'collection.json').read_text())
    commands=[json.loads(f.read_text()) for f in sorted(commands_root.glob('*.json')) if not f.name.endswith('.host-pid.json')]
    names=[c['operation'] for c in commands]
    issues=[]
    ordered=[];rpc_markers=[]
    with (run/'raw/device/genie-verbose.log').open(errors='replace') as src:
        for number,line in enumerate(src,1):
            match=re.search(r'Graph (ar128|ar1)_cl4096_1_of_1 execution finished with result (\S+)',line)
            if match and match[2]=='0':ordered.append(match[1])
            if re.search(r'connection.*reset|SSR.*dead',line,re.I):rpc_markers.append({'line':number,'text':line.rstrip()})
    manifest=json.loads((STAGE/'frozen-manifest.json').read_text())
    confirmed=basic_scope(collection,obs,manifest,(device/'runner.stdout').read_text(),ordered)
    if not confirmed['confirmed']:issues.append('actual primary BasicDialog generation scope not fully confirmed')
    traced=trace_parser.summarize((device/'runner.stderr').read_text(errors='replace'),obs['actual_generated_tokens'])
    counts=obs['execution_markers']
    correlated=correlate.correlate(traced,input_count=obs['prompt']['profile_prompt_tokens'],
        accepted_generated_count=obs['actual_generated_tokens'],basic_scope_confirmed=confirmed['confirmed'],
        ar128_status0_count=counts['ar128_completed_status0'],ar1_status0_count=counts['ar1_completed_status0'])
    parity=trace_parser.input_parity((device/'input-token-ids.txt').read_text(),(STAGE/'token-ids/long.int32le').read_bytes())
    if not parity['exact_frozen_input_ids_equal']:issues.append('same-runtime full input-ID parity failed')
    for key in ('graph_execute_nonzero_status','cpu_backend_markers','runtime_fallback_markers','cache_quantization_error'):
        if counts[key]:issues.append('observed route/execution marker: '+key)
    if rpc_markers:issues.append('current-run RPC reset/SSR-dead marker')
    cleanup={'adb_calls':len(commands),'all_calls_locked_noninheritable':all(c['lock_held'] and not c['lock_fd_inheritable'] for c in commands),
       'raw_pull_before_root_removal':names.index('raw.pull')<names.index('cleanup.remove') if 'raw.pull' in names and 'cleanup.remove' in names else False,
       'all_scoped_roles_absent':collection.get('process_cleanup',{}).get('all_absent'),
       'remote_root_absent':collection['cleanup']=='verified_absent','phone_lock_released':collection['phone_lock_released'],
       'signal_guard_events':signal_review(commands,commands_root),'signal_guard_atomic':False}
    if not all(cleanup[k] for k in ('all_calls_locked_noninheritable','raw_pull_before_root_removal','all_scoped_roles_absent','remote_root_absent','phone_lock_released')):
        issues.append('guarded retention/cleanup incomplete')
    # Decode the retained gzip independently; no rewriting of the original log.
    dig=hashlib.sha256();nbytes=0
    with gzip.open(result/compressed['compressed_path'],'rb') as f:
        for block in iter(lambda:f.read(4*1024*1024),b''):dig.update(block);nbytes+=len(block)
    if dig.hexdigest()!=compressed['original_sha256'] or nbytes!=compressed['original_bytes']:
        issues.append('provider compression failed lossless identity check')
    reference=json.loads((REFERENCE/'result.json').read_text())
    if sha(REFERENCE/'result.json')!=REFERENCE_SHA:raise RuntimeError('f11df93 reference changed; raw trace already retained')
    old_output=REFERENCE/reference['observations']['output']['path']
    if sha(old_output)!=REFERENCE_OUTPUT:raise RuntimeError('f11df93 output changed')
    output=device/'long-output.txt'
    equal=output.read_bytes()==old_output.read_bytes()
    comparison={'reference_commit':'f11df93','reference_result_sha256':REFERENCE_SHA,'reference_output_sha256':REFERENCE_OUTPUT,
        'visible_bytes_equal':equal,'runtime_equivalence_established':False,
        'caveat':'Equal visible bytes do not prove binary/numerical equivalence and cannot backfill old commercial selected IDs.'}
    # Optional frozen descriptive metrics: failures retain the request and nulls.
    metric_error=None;metrics=None;direct_metrics=None;retokenized_ids_equal=None
    ids=[r['token'] for r in correlated['accepted_generation_records']]
    try:
        metrics=previous.compare(output)
        from tokenizers import Tokenizer
        tokenizer=Tokenizer.from_file(str(STAGE/'tokenizer.json'))
        text=output.read_text();retokenized=tokenizer.encode(text,add_special_tokens=False).ids
        retokenized_ids_equal=ids==retokenized
        if correlated['accepted_generation_coverage_complete']:
            spec=importlib.util.spec_from_file_location('frozen_direct_trace_metric',previous.old_long.METRIC_TOOL)
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            direct_metrics=module.trajectory_metrics(ids,text)
    except Exception as error:metric_error=f'{type(error).__name__}: {error}'
    packed=struct.pack('<'+'i'*len(ids),*ids)
    (result/'accepted-selected-ids.int32le').write_bytes(packed)
    for name,value in [('trace-observations.json',traced),('accepted-generation-correlation.json',correlated),('basic-scope-binding.json',confirmed)]:
        (result/name).write_text(json.dumps(value,indent=2)+'\n')
    thermal={}
    for phase in ('before','after'):
        paths=list(commands_root.glob(f'*-telemetry.{phase}.thermalservice.stdout'))
        thermal[phase]=previous.old_short.thermal_extract(paths[0].read_text()) if paths else None
    sanity=reference['output_sanity'] if equal else {'looks_sensible':None,'issue_notes':None}
    report={'classification':'physical_source_runtime_trace_captured','analysis_issues':issues,'run_id':run.name,
      'readiness_commit':'c7abf0cd','correlation_commit':'0e47bc18','stage_digest':scope.STAGE_DIGEST,
      'context_sha256':manifest['context_sha256'],'runtime_sha256':scope.LIB_SHA,
      'source_runtime_build_limitations':'New source-built Genie and NDK libc++; completed Android source recipe and252 added dependency versions. No equivalence to commercial runtime assumed.',
      'collection':collection,'observations':obs,'input_parity':parity,
      'accepted_generation_trace':{'records':len(ids),'int32le_sha256':hashlib.sha256(packed).hexdigest(),
        'coverage_complete':correlated['accepted_generation_coverage_complete'],'selected_id50_observed':correlated['accepted_id50_observed'],
        'configured_eos_selected_ids':[r for r in correlated['accepted_generation_records'] if r['configured_eos']],
        'continuation_at_id50':correlated['id50_continuation_observations'],
        'internal_stop_decision':None,'retokenized_visible_ids_equal':retokenized_ids_equal,
        'direct_selected_id_metrics':direct_metrics,
        'scope':'Actual correlated accepted-generation IDs for this one source-runtime request only; no prefill/proposal-only records promoted.'},
      'visible_comparison_to_f11df93':comparison,'frozen_text_metric_comparison':metrics,'optional_metric_error':metric_error,
      'output_sanity':sanity,'sanity_basis':'Same exact output bytes as the already reviewed f11df93 negative.' if equal else 'Unchecked changed output.',
      'cleanup':cleanup,'provider_log':compressed,'rpc_current_run_markers':rpc_markers,
      'private_battery_originals':private,'operating_context':{'thermal':thermal,'battery':{
          phase:json.loads((result/f'derived/battery-{phase}.json').read_text()) if (result/f'derived/battery-{phase}.json').exists() else None for phase in ('before','after')}},
      'memory':{'pss':None,'vmhwm':None,'htp_private':None,'reason':'Not measured by this scoped controller.'},
      'conclusion_boundary':'An observed absence of50 applies only to the complete bound source-runtime generation. Same repeating visible outcome without selected50 is not retrospective evidence of the old commercial stream, a fix or a root-cause verdict. Internal stopping decisions remain unavailable.',
      'registry_eligible':False,'speed_acceptance':False,'new_requests_authorized':False,
      'source_sha256':sha(Path(__file__))}
    (result/'result.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    sums=result/'SHA256SUMS';sums.write_text(''.join(f'{sha(f)}  {f.relative_to(result)}\n' for f in sorted(result.rglob('*')) if f.is_file() and f!=sums))
    print(json.dumps({'result':str(result),'sha256':sha(result/'result.json'),'analysis_issues':issues,
      'actual_selected50':correlated['accepted_id50_observed'],'complete':correlated['accepted_generation_coverage_complete'],
      'visible_equal_f11df93':equal,'metric_error':metric_error,'cleanup':cleanup},indent=2))


if __name__=='__main__':main()
