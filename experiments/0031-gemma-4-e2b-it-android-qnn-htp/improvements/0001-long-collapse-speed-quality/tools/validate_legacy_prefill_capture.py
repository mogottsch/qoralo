#!/usr/bin/env python3
"""Saved-only exact binding of the ONE completed corrected-observer capture."""
import hashlib
import json
from pathlib import Path

TRACK=Path(__file__).resolve().parents[1]
BINDING=TRACK/'results/paired-legacy-host-binding-01/capture-binding.json'
BINDING_SHA='b0fcf4f660dafb4c88097edfc1517d34a1a015564b39a6d16b814418d78d616a'
NONCACHE={'inputs_embeds','per_layer_inputs','attention_mask','swa_attention_mask','position_ids_cos','position_ids_sin','swa_position_ids_cos','swa_position_ids_sin'}


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for data in iter(lambda:f.read(1024*1024),b''):h.update(data)
    return h.hexdigest()


def specification():
    if sha(BINDING)!=BINDING_SHA:raise ValueError('frozen exact-capture binding changed')
    return json.loads(BINDING.read_text())


def check_observations(x,spec):
    for field in ['run_id','pi_slot']:
        if x.get(field)!=spec[field]:raise ValueError('wrong captured run/slot')
    if x.get('reviewed_stage_digest')!=spec['stage_digest']:raise ValueError('wrong observer stage')
    if x.get('process_exit_code')!=0 or not x.get('raw_pull_completed') or not x.get('phone_lock_released') or x.get('cleanup')!='verified_absent' or not x.get('process_cleanup',{}).get('all_absent'):raise ValueError('successful raw-first released capture required')
    before=x.get('current_app_preflight',{});after=x.get('postflight_app_identity',{})
    if not after.get('verified') or before.get('current_apks')!=spec['expected_APKs'] or after.get('current_apks')!=spec['expected_APKs'] or not before.get('generation_and_test_absent') or not after.get('generation_and_test_absent'):raise ValueError('actual independent pre/post APK and job checks required')
    for label in ['preflight.actual_user_job_playback_v2','prelaunch.actual_user_job_playback_v2']:
        if not x.get(label,{}).get('playback_quiescence_observed'):raise ValueError('saved playback check missing')
    scope=x.get('scope_adapter',{})
    if any(scope.get(k)!=v for k,v in spec['scope_bound_fields'].items()) or not scope.get('actual_user_job_quiescence_attested'):raise ValueError('observer/runtime/AS/capture scope mismatch')


def check_journal(rows):
    begun=set();complete={}
    for row in rows:
        key=(row.get('phase'),row.get('step'),row.get('name'))
        if row.get('cache_tensor') is not False:raise ValueError('HTP cache or unknown tensor forbidden')
        if row.get('event')=='begin':
            if key in begun:raise ValueError('duplicate capture begin')
            begun.add(key)
        elif row.get('event')=='complete':
            if key not in begun or key in complete:raise ValueError('unbound/duplicate completion')
            complete[key]=row
        else:raise ValueError('unknown capture event')
    expected={('input',step,name) for step in range(16) for name in NONCACHE}|{('output',15,'logits')}
    if set(complete)!=expected or begun!=expected:raise ValueError('same-run128 inputs plus exactly one final logit payload required')
    row=complete[('output',15,'logits')]
    wanted={'variant':128,'context':4096,'n_past':1920,'n_process':9,'final_valid_row':8,'shape':[1,1,262144],'datatype':'QNN_DATATYPE_UFIXED_POINT_16','scale':0.0008891067700460553,'offset':-31869,'before_sampler_access':True,'before_original_dequantization':True,'row_view_already_offset':True,'source_path':'PLE_legacy_getDequantLogits','file':'15-output-logits.raw','bytes':524288,'completed_payloads':129,'total_payload_bytes':66060288}
    if any(row.get(k)!=v for k,v in wanted.items()):raise ValueError('raw row8 before-original-dequant contract mismatch')
    return row


def validate(path):
    spec=specification();path=Path(path).resolve()
    if path!=Path(spec['phone_collection']) or sha(path)!=spec['phone_collection_sha256']:raise ValueError('exact complete collection binding required; no cross-run stitching')
    x=json.loads(path.read_text());check_observations(x,spec)
    adapter_path=TRACK/'tools/phone_legacy_prefill_capture.py'
    if sha(adapter_path)!=spec['controller_source_sha256']:raise ValueError('frozen corrected phone adapter changed')
    import phone_legacy_prefill_capture as adapter
    from phone_mapping_as12_capture import inspect_readbacks
    module,_=adapter.load_adapter();controller,scope=module.load_lifecycle(spec['expected_APKs'],True)
    if any(scope[k]!=v for k,v in spec['scope_bound_fields'].items()):raise ValueError('reconstructed corrected observer scope mismatch')
    scripts={name:hashlib.sha256(text.encode()).hexdigest() for name,text in controller.scripts(x['remote_root']).items()}
    if scripts!=x['controller_script_hashes']:raise ValueError('actual bounded controller scripts changed')
    for record in spec['files']:
        relative=Path(record['path']);p=path.parent/relative
        if relative.is_absolute() or '..' in relative.parts or p.is_symlink() or not p.resolve().is_relative_to(path.parent) or p.stat().st_size!=record['bytes'] or sha(p)!=record['sha256']:raise ValueError('capture artifact changed '+record['path'])
    cap=path.parent/'raw/device/prefill-capture'
    if len(list(cap.glob('*.raw')))!=129:raise ValueError('exact129 payloads required; extra caches forbidden')
    row=check_journal([json.loads(line) for line in (cap/'capture.jsonl').read_text().splitlines()])
    observed=inspect_readbacks([(cap/n).read_text() for n in ['mapping-stages.log','allocation-stages.log']])
    if observed['matches_expected'] is not True:raise ValueError('actual AS12 soft/hard readback missing or different')
    return {'capture_dir':str(cap),'capture_binding_sha256':BINDING_SHA,'phone_collection_sha256':spec['phone_collection_sha256'],'actual_AS_readback':observed,'raw_payloads':129,'raw_payload_bytes':66060288,'full_QNN_row8_logits_sha256':spec['raw_QNN_logits_sha256'],'before_original_dequant_and_sampler':row['before_original_dequantization'] and row['before_sampler_access'],'phone_released':True,'model_executed_by_validation':False}
