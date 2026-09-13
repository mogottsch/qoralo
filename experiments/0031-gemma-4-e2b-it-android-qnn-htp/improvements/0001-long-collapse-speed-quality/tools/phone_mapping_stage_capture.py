#!/usr/bin/env python3
"""Plan-only LUT mapping discriminator using the corrected actual cleanup hook."""
import hashlib
from pathlib import Path
import sys
import types

TOOLS=Path(__file__).resolve().parent
BASE_SHA='09dc8a35409f282e1ee3048fc16d94102105f1cf63f34873aaeaf14b5b6049b4'
STAGE='paired-mapping-observer-stage-01'
DIGEST='807980c106a59584752ce52abece89dd50062c827505fb2136ae0c950ca7206e'
LIB='ee2b10d89d9fec2442bdf6cfd6a1e369eb525ec1c0d091acd2ee19bcb00ba099'


def load_adapter():
    path=TOOLS/'phone_paired_prefill_capture.py';original=path.read_text()
    if hashlib.sha256(path.read_bytes()).hexdigest()!=BASE_SHA:raise ValueError('corrected postflight base changed')
    changes=[('paired-prefill-capture-stage-01',STAGE),('b99056c1faa1e25823fd9bcda2a0968a0445cb93458dc1069e7d269eb9c54953',DIGEST),('3a61a7ea888e39b54999c25b0644ff068733c343cb693e5eafee9be4538dccc2',LIB),('.local/paired-prefill-phone-runs','.local/mapping-stage-phone-runs'),('/data/local/tmp/vibevoice-0031-paired-','/data/local/tmp/vibevoice-0031-mapping-')]
    source=original
    for before,after in changes:
        if source.count(before)!=1:raise ValueError('mapping adapter anchor changed')
        source=source.replace(before,after)
    inverse=source
    for before,after in reversed(changes):inverse=inverse.replace(after,before)
    if inverse!=original:raise ValueError('unexpected lifecycle mutation')
    module=types.ModuleType('mapping_stage_guarded_adapter');module.__file__=str(path);sys.modules[module.__name__]=module;exec(compile(source,str(path),'exec'),module.__dict__)
    return module,{'base_sha256':BASE_SHA,'adapter_sha256':hashlib.sha256(source.encode()).hexdigest(),'changes':changes,'AS_model_caps_cleanup_budgets_changed':False,'actual_finish_remote_postflight_hook':True,'phone_or_model_executed':False}


if __name__=='__main__':
    module,_=load_adapter()
    raise SystemExit(module.main())
