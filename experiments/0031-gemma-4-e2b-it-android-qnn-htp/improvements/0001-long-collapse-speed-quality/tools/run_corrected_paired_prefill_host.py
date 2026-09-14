#!/usr/bin/env python3
"""ONE separately granted storage-corrected host run; same complete phone capture."""
import hashlib
import json
from pathlib import Path
import sys
import types

TOOLS=Path(__file__).resolve().parent
BASE_HOST_SHA='fb32816a41f9a9246df79c807b67da7f88fd06c8b94ff8921eb02e2a0e19d77c'
CORRECTED_REFERENCE_SHA='3ececc8f93c6535a728bfa38eac64c471eafb72fdf13df57d0b25ae625c57582'
CORRECTED_GRANT='pi-gemma-corrected-fp16-20260914-01'
ROOT=TOOLS.parent/'.local/corrected-legacy-prefill-host-runs'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_adapter():
    path=TOOLS/'run_legacy_prefill_host.py';ref_path=TOOLS/'declared_dlc_reference_fp16.py'
    if sha(path)!=BASE_HOST_SHA or sha(ref_path)!=CORRECTED_REFERENCE_SHA:raise ValueError('frozen V1 host or corrected reference adapter changed')
    source=path.read_text();original=source
    changes=[("ROOT=TRACK/'.local/legacy-prefill-host-runs'","ROOT=TRACK/'.local/corrected-legacy-prefill-host-runs'",1),('results/paired-legacy-host-binding-01/implementation-bindings.json','results/corrected-reference-storage-readiness-01/implementation-bindings.json',1),("spec['host_grant_id']",'CORRECTED_GRANT',2)]
    for before,after,count in changes:
        if source.count(before)!=count:raise ValueError('corrected host adapter anchor changed')
        source=source.replace(before,after)
    inverse=source
    for before,after,count in reversed(changes):
        if inverse.count(after)!=count:raise ValueError('inverse host binding anchor changed')
        inverse=inverse.replace(after,before)
    if inverse!=original:raise ValueError('host limit/computation mutation outside declared correction')
    adapter=types.ModuleType('storage_corrected_host_adapter');adapter.__file__=str(Path(__file__).resolve());adapter.CORRECTED_GRANT=CORRECTED_GRANT
    exec(compile(source,adapter.__file__,'exec'),adapter.__dict__);module,prior=adapter.load_adapter()
    import declared_dlc_reference_fp16 as corrected
    _,reference_receipt=corrected.materialize_source()
    parent_sources=module.assert_host_sources
    def sources():
        values=parent_sources()
        if sha(path)!=BASE_HOST_SHA or sha(ref_path)!=CORRECTED_REFERENCE_SHA:raise ValueError('corrected source changed during run')
        return dict(sorted({**values,str(path):BASE_HOST_SHA,str(ref_path):CORRECTED_REFERENCE_SHA}.items()))
    module.assert_host_sources=sources
    parent_internal=module.internal
    def internal(root,compute=False):
        root=Path(root).resolve()
        if not root.is_relative_to(ROOT):raise ValueError('fresh corrected owned root required')
        grant=json.loads((root/'grant.json').read_text());expected_unit='gemma-paired-host-'+root.name
        if grant.get('grant_id')!=CORRECTED_GRANT or grant.get('unit')!=expected_unit or expected_unit not in Path('/proc/self/cgroup').read_text():raise PermissionError('corrected one-use grant and actual bounded unit required')
        if compute:
            # The original input/cache runner imports this module at its execution boundary.
            # Original files remain immutable; only this separately scoped child uses V2.
            sources()
            runtime,_=corrected.load_runtime(root/'native/nonfinite-first.json')
            sys.modules['declared_dlc_reference']=runtime
        return parent_internal(root,compute)
    module.internal=internal
    return module,{'classification':'one_storage_corrected_declared_reference_host_adapter','baseline_host_sha256':BASE_HOST_SHA,'corrected_reference_sha256':CORRECTED_REFERENCE_SHA,'corrected_grant':CORRECTED_GRANT,'same_phone_capture_binding_sha256':prior['capture_binding_sha256'],'source_changes':changes,'reference_patch':reference_receipt,'same_model_policy_actual_inputs_own30caches_and_limits':True,'first_unexpected_nonfinite_recorded_then_stop':True,'no_NaN_integer_cast_or_arithmetic_repair':True,'phone_access':False,'automatic_retry':False,'prior_failed_reference_preserved':True}


if __name__=='__main__':
    module,_=load_adapter()
    raise SystemExit(module.main())
