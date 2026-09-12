#!/usr/bin/env python3
"""Raw-first saved-only analysis of the ONE aligned GPU reference."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import struct

import phone_aligned_litert_reference as scope
from prepare_aligned_litert_stage import TRACK,INPUT_SHA
from build_aligned_litert_reference import sha
from analyze_phone_return_short import battery_extract,thermal_extract
from analyze_selected_id_long import signal_review

STAGE=TRACK/'.local/frozen-stages'/scope.STAGE_NAME
TRACE=TRACK/'results/selected-id-phone-long-attempt-01'
TRACE_IDS_SHA='8a78560be15953ec6e41bb3f20606c4572d18cc30ebe233309d344cee6d150bc'
METRIC_SHA='6084bb73d60f7e68ac3f516fad6df3463fdc8adb6213ea9a9a36190099b4fb70'


def packed(ids):
    if not isinstance(ids,list) or any(type(x) is not int or not 0<=x<262144 for x in ids):raise ValueError('invalid token-ID array')
    return struct.pack('<'+'i'*len(ids),*ids)


def input_alignment(record,expected):
    actual=record.get('actual_effective_token_ids');p=packed(actual)
    return {'actual_count':len(actual),'actual_int32le_sha256':hashlib.sha256(p).hexdigest(),
      'exact_frozen_ids_equal':p==expected,'runtime_reported_match':record.get('all_ids_equal'),
      'expected_record_equal':packed(record.get('expected_effective_token_ids'))==expected,
      'recorded_before_prefill':record.get('prefill_not_yet_started') is True,
      'basis':'Actual session preprocessing immediately before the sole RunPrefill; not a direct executor tensor dump.'}


def prefix_comparison(reference,qnn):
    common=0
    for a,b in zip(reference,qnn):
        if a!=b:break
        common+=1
    mismatch=common<len(reference) and common<len(qnn)
    return {'common_prefix_tokens':common,'first_differing_index':common if mismatch else None,
      'reference_id_at_difference':reference[common] if mismatch else None,'qnn_id_at_difference':qnn[common] if mismatch else None,
      'one_stream_ended_after_common_prefix':not mismatch and len(reference)!=len(qnn),
      'boundary':'Reference callback IDs are stop-filtered; QNN trace is unfiltered accepted selection. A prefix mismatch is trajectory divergence, not causal localization or numerical equivalence. Filtered terminal IDs are not reconstructed.'}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run-dir',type=Path,required=True);ap.add_argument('--result-dir',type=Path,required=True);a=ap.parse_args()
    run=a.run_dir.resolve();out=a.result_dir.resolve()
    if run.parent!=TRACK/'.local/aligned-reference-phone-runs' or out.parent!=TRACK/'results' or not out.name.startswith('aligned-reference-phone-'):ap.error('owned saved run and fresh outcome path required')
    out.mkdir(parents=True,exist_ok=False);raw=out/'raw/controller';private=[]
    # Verify actual collection hashes before copying. Preserve originals as-is.
    original_hashes=0
    for line in (run/'SHA256SUMS').read_text().splitlines():
        h,n=line.split('  ',1);f=run/n
        if not f.resolve().is_relative_to(run) or sha(f)!=h:raise ValueError('private collection integrity failed')
        original_hashes+=1
    for f in sorted(run.rglob('*')):
        if not f.is_file():continue
        rel=f.relative_to(run)
        match=re.fullmatch(r'raw/commands/\d+-telemetry\.(before|after)\.battery\.stdout',str(rel))
        if match:
            private.append({'path':str(f),'bytes':f.stat().st_size,'sha256':sha(f),'reason':'Unrelated learned battery history; original remains private unchanged'})
            d=out/'derived'/('battery-'+match[1]+'.json');d.parent.mkdir(exist_ok=True);d.write_text(json.dumps(battery_extract(f.read_text()),indent=2)+'\n')
            continue
        dest=raw/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(f,dest)
    collection=json.loads((raw/'collection.json').read_text());device=raw/'raw/device';cr=raw/'raw/commands'
    commands=[json.loads(f.read_text()) for f in sorted(cr.glob('*.json')) if not f.name.endswith('.host-pid.json')];names=[x['operation'] for x in commands]
    report={'classification':'saved_aligned_reference_outcome','run_id':run.name,'collection':collection,'private_original_hashes_verified':original_hashes,'private_battery_originals':private,'analysis_issues':[],
      'output_sanity':{'looks_sensible':None,'issue_notes':None},'registry_eligible':False,'speed_acceptance':False,'internal_terminal_id':None,
      'terminal_boundary':'The runner eos label for a below-cap done request does not expose the filtered terminal ID. No selected1/50/106 absence claim can be made from LiteRT callback IDs.',
      'runtime_equivalence_proven':False,'new_inference_authorized':False,'analyzer_sha256':sha(Path(__file__))}
    issues=report['analysis_issues']
    try:
        expected=(STAGE/'expected-input-ids.int32le').read_bytes()
        if hashlib.sha256(expected).hexdigest()!=INPUT_SHA:raise ValueError('frozen expected IDs changed')
        alignment=json.loads((device/'input-alignment-before-prefill.json').read_text());parity=input_alignment(alignment,expected);report['input_alignment']=parity
        if not all(parity[k] for k in ('exact_frozen_ids_equal','runtime_reported_match','expected_record_equal','recorded_before_prefill')):issues.append('actual full effective input parity not confirmed')
        runner=json.loads((device/'runner-result.json').read_text());report['runner']=runner
        checks={'bound_stage':collection['reviewed_stage_digest']==scope.STAGE_DIGEST and collection['input_hashes_verified'],
          'native_process_observed':collection['native_process_observed'],'single_request':len(runner['runs'])==1,
          'gpu_only_provider':runner['backend']=='gpu' and runner['gpu_provider_binding']['binding_proven'],
          'reference_context_cap':runner['route']['max_num_tokens']==8192 and runner['route']['max_output_tokens']==2048,
          'exact_rendered_body':(device/'rendered/long.txt').read_bytes()==(STAGE/'expected-rendered-long.txt').read_bytes()}
        request=runner['runs'][0]
        checks['fresh_completed_request']=request['runtime_task_state']=='done' and request['runtime_error'] is None and request['session_step_before_reset']==0 and request['rewind_called'] is False
        checks['aligned_request_identity']=request['id']=='aligned-reference-long-01' and request['tier']=='long' and request['expected_input_tokens']==1929
        report['scope_checks']=checks
        if not all(checks.values()):issues.append('request/provider/scope not fully confirmed')
        output=device/request['output_relative_path']
        if not output.resolve().is_relative_to(device.resolve()):raise ValueError('unsafe output path')
        text=output.read_text();ids=request['emitted_token_ids'];data=packed(ids)
        (out/'reference-callback-ids.int32le').write_bytes(data)
        report['output']={'path':str(output.relative_to(out)),'sha256':sha(output),'bytes':output.stat().st_size,'callback_tokens':len(ids),'callback_ids_sha256':hashlib.sha256(data).hexdigest(),'callback_ids_stop_filtered':True}
        if len(ids)!=request['output_tokens']:issues.append('callback count inconsistent with retained IDs')
        q=(TRACE/'accepted-selected-ids.int32le').read_bytes()
        if hashlib.sha256(q).hexdigest()!=TRACE_IDS_SHA:raise ValueError('bound QNN trace changed')
        report['trajectory_comparison']=prefix_comparison(ids,list(struct.unpack('<'+'i'*(len(q)//4),q)))
        try:
            tool=TRACK/'tools/analyze_long_collapse.py'
            if sha(tool)!=METRIC_SHA:raise ValueError('frozen metric changed')
            spec=importlib.util.spec_from_file_location('aligned_frozen_metric',tool);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            report['frozen_callback_trajectory_metrics']=module.trajectory_metrics(ids,text);report['optional_metric_error']=None
        except Exception as error:report.update(frozen_callback_trajectory_metrics=None,optional_metric_error=repr(error))
    except Exception as error:issues.append('retained evidence analysis: '+repr(error))
    report['cleanup']={'all_calls_locked_noninheritable':all(x['lock_held'] and not x['lock_fd_inheritable'] for x in commands),
      'adb_calls':len(commands),'raw_pull_before_root_removal':names.index('raw.pull')<names.index('cleanup.remove') if 'raw.pull' in names and 'cleanup.remove' in names else False,
      'all_roles_absent':collection.get('process_cleanup',{}).get('all_absent'),'root_absent':collection.get('cleanup')=='verified_absent','lock_released':collection['phone_lock_released'],
      'signal_guard_events':signal_review(commands,cr),'signal_guard_atomic':False}
    if not all(report['cleanup'][k] for k in ('all_calls_locked_noninheritable','raw_pull_before_root_removal','all_roles_absent','root_absent','lock_released')):issues.append('capture/cleanup incomplete')
    report['thermal']={}
    for phase in ('before','after'):
        fs=list(cr.glob('*-telemetry.'+phase+'.thermalservice.stdout'));report['thermal'][phase]=thermal_extract(fs[0].read_text()) if fs else None
    (out/'result.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    sums=out/'SHA256SUMS';sums.write_text(''.join(f'{sha(f)}  {f.relative_to(out)}\n' for f in sorted(out.rglob('*')) if f.is_file() and f!=sums))
    print(json.dumps({'result':str(out),'analysis_issues':issues,'output':report.get('output'),'comparison':report.get('trajectory_comparison')},indent=2))


if __name__=='__main__':main()
