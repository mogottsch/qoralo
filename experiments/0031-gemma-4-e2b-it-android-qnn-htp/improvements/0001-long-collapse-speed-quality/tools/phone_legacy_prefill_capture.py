#!/usr/bin/env python3
"""Plan-only actual-PLE-logit observer stage, retaining the explicit AS12 control."""
import hashlib
from pathlib import Path
import sys
import types

TOOLS=Path(__file__).resolve().parent
BASE_AS12_SHA='2ab2535a204ca489bb54a661917a785077aa34ebcc6bc5710b98f1f2b4017961'
STAGE='paired-legacy-logits-stage-01'
DIGEST='7b61cf0a03ad93292127a7ad59e1b74ae9b61ac4e660691a0cff5a947b40486c'
LIB='e2b554ca4e216f1df77c3c331b3f1295584cf030c7120cccc3b15bbce3a1e1ed'


def load_adapter():
    if hashlib.sha256((TOOLS/'phone_mapping_as12_capture.py').read_bytes()).hexdigest()!=BASE_AS12_SHA:raise ValueError('frozen AS12 base changed')
    import phone_mapping_as12_capture as as12
    _,prior=as12.load_adapter();path=TOOLS/'phone_paired_prefill_capture.py';source=path.read_text()
    for before,after in prior['baseline_adapter']['changes']+prior['changes']:
        if source.count(before)!=1:raise ValueError('AS12 reconstruction anchor changed')
        source=source.replace(before,after)
    if hashlib.sha256(source.encode()).hexdigest()!=prior['adapter_sha256']:raise ValueError('AS12 adapter reconstruction mismatch')
    original=source
    changes=[('paired-mapping-observer-stage-01',STAGE),('807980c106a59584752ce52abece89dd50062c827505fb2136ae0c950ca7206e',DIGEST),('ee2b10d89d9fec2442bdf6cfd6a1e369eb525ec1c0d091acd2ee19bcb00ba099',LIB),('.local/mapping-as12-phone-runs','.local/legacy-logits-phone-runs'),('/data/local/tmp/vibevoice-0031-mapping-as12-','/data/local/tmp/vibevoice-0031-legacy-logits-')]
    for before,after in changes:
        if source.count(before)!=1:raise ValueError('legacy observer adapter anchor changed')
        source=source.replace(before,after)
    inverse=source
    for before,after in reversed(changes):inverse=inverse.replace(after,before)
    if inverse!=original:raise ValueError('unexpected controller mutation')
    module=types.ModuleType('PLE_legacy_prefill_guarded_adapter');module.__file__=str(path);sys.modules[module.__name__]=module;exec(compile(source,str(path),'exec'),module.__dict__)
    return module,{'base_AS12_controller_sha256':BASE_AS12_SHA,'prior_adapter':prior,'adapter_sha256':hashlib.sha256(source.encode()).hexdigest(),'changes':changes,'AS12_model_LUT_input_caps_time_capture_cleanup_changed':False,'actual_AS_soft_hard_readback_required':12884901888,'new_phone_or_model_permission_granted':False}


if __name__=='__main__':
    module,_=load_adapter()
    raise SystemExit(module.main())
