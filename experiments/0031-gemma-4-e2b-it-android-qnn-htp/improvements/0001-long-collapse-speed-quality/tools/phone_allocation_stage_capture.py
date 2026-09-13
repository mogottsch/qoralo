#!/usr/bin/env python3
"""Plan-only allocation-stage discriminator over the corrected guarded lifecycle."""
import hashlib
from pathlib import Path
import sys
import types

TOOLS=Path(__file__).resolve().parent
BASE_SHA='09dc8a35409f282e1ee3048fc16d94102105f1cf63f34873aaeaf14b5b6049b4'
STAGE='paired-allocation-observer-stage-01'
DIGEST='6a36db9747f674dcf3410b8d226958898c03cce8f96c67d27b68fcddfe4fc71a'
LIB='87f8b9b624d9de6e08de372740e5814fc64eb352c68b2c73fd07c8190e41d9eb'


def load_adapter():
    path=TOOLS/'phone_paired_prefill_capture.py';original=path.read_text()
    if hashlib.sha256(path.read_bytes()).hexdigest()!=BASE_SHA:raise ValueError('corrected base controller changed')
    changes=[('paired-prefill-capture-stage-01',STAGE),('b99056c1faa1e25823fd9bcda2a0968a0445cb93458dc1069e7d269eb9c54953',DIGEST),('3a61a7ea888e39b54999c25b0644ff068733c343cb693e5eafee9be4538dccc2',LIB),('.local/paired-prefill-phone-runs','.local/allocation-stage-phone-runs'),('/data/local/tmp/vibevoice-0031-paired-','/data/local/tmp/vibevoice-0031-allocation-')]
    source=original
    for before,after in changes:
        if source.count(before)!=1:raise ValueError('allocation adapter anchor changed')
        source=source.replace(before,after)
    restored=source
    for before,after in reversed(changes):restored=restored.replace(after,before)
    if restored!=original:raise ValueError('unexpected lifecycle mutation')
    module=types.ModuleType('allocation_stage_guarded_adapter');module.__file__=str(path);sys.modules[module.__name__]=module;exec(compile(source,str(path),'exec'),module.__dict__)
    return module,{'base_sha256':BASE_SHA,'materialized_adapter_sha256':hashlib.sha256(source.encode()).hexdigest(),'changes':changes,'AS_limit_token_cap_and_cleanup_budgets_changed':False,'model_or_phone_executed':False}


if __name__=='__main__':
    module,_=load_adapter()
    raise SystemExit(module.main())
