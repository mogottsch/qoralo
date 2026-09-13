#!/usr/bin/env python3
"""Plan-only, one explicitly authorized 12 GiB AS control; not a RAM-budget change."""
import hashlib
from pathlib import Path
import sys
import types

TOOLS=Path(__file__).resolve().parent
BASE_MAPPING_SHA='3301a51d11e67c9ad1ae5173faacfbb7b2d4d3b1cbcf46f8d65fd6bdc71ef384'
AS_BEFORE=8589934592
AS_AFTER=12884901888


def load_adapter():
    mapping_path=TOOLS/'phone_mapping_stage_capture.py'
    if hashlib.sha256(mapping_path.read_bytes()).hexdigest()!=BASE_MAPPING_SHA:raise ValueError('frozen mapping controller changed')
    import phone_mapping_stage_capture as baseline
    _,base_binding=baseline.load_adapter()
    path=TOOLS/'phone_paired_prefill_capture.py';source=path.read_text()
    for before,after in base_binding['changes']:
        if source.count(before)!=1:raise ValueError('baseline source reconstruction changed')
        source=source.replace(before,after)
    if hashlib.sha256(source.encode()).hexdigest()!=base_binding['adapter_sha256']:raise ValueError('baseline adapter digest mismatch')
    original=source
    changes=[('ulimit -v 8388608','ulimit -v 12582912'),("'address_space_limit_bytes':8*1024**3","'address_space_limit_bytes':12*1024**3"),('phone_address_space_limit_bytes=8*1024**3','phone_address_space_limit_bytes=12*1024**3'),('.local/mapping-stage-phone-runs','.local/mapping-as12-phone-runs'),('/data/local/tmp/vibevoice-0031-mapping-','/data/local/tmp/vibevoice-0031-mapping-as12-')]
    for before,after in changes:
        if source.count(before)!=1:raise ValueError('AS-only control anchor changed')
        source=source.replace(before,after)
    inverse=source
    for before,after in reversed(changes):inverse=inverse.replace(after,before)
    if inverse!=original:raise ValueError('unbounded AS-control mutation')
    module=types.ModuleType('mapping_AS12_guarded_adapter');module.__file__=str(path);sys.modules[module.__name__]=module;exec(compile(source,str(path),'exec'),module.__dict__)
    return module,{'baseline_mapping_controller_sha256':BASE_MAPPING_SHA,'baseline_adapter':base_binding,'adapter_sha256':hashlib.sha256(source.encode()).hexdigest(),'changes':changes,'AS_limit_before_bytes':AS_BEFORE,'AS_limit_after_bytes':AS_AFTER,'RAM_budget_changed':False,'observer_model_LUT_input_token_time_capture_limits_changed':False,'actual_RLIMIT_readback_expected':{'AS_soft':AS_AFTER,'AS_hard':AS_AFTER,'rlimit_valid':1},'new_phone_or_model_execution_authorized_by_preparation':False,'sweep_or_automatic_retry':False}


def inspect_readbacks(texts):
    """Saved telemetry only. Missing readback is unknown, never fabricated as 12 GiB."""
    count=0;unknown=0;mismatches=[]
    for text in texts:
        for line in text.splitlines():
            if not line.startswith(('GEMMA_ALLOC_V1 ','GEMMA_MAPPING_V1 ')):continue
            try:
                row=dict(item.split('=',1) for item in line.split()[1:]);valid=int(row['rlimit_valid']);soft=int(row['AS_soft']);hard=int(row['AS_hard'])
            except (KeyError,ValueError):unknown+=1;continue
            if valid!=1:unknown+=1;continue
            count+=1
            if soft!=AS_AFTER or hard!=AS_AFTER:mismatches.append({'AS_soft':soft,'AS_hard':hard})
    return {'valid_readbacks':count,'unknown_readbacks':unknown,'mismatches':mismatches,'matches_expected':False if mismatches else (True if count and not unknown else None),'no_runtime_readback_from_plan_alone':True}


if __name__=='__main__':
    module,_=load_adapter()
    raise SystemExit(module.main())
