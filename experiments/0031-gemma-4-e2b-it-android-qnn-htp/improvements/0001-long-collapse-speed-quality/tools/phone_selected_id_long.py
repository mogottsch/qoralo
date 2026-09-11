#!/usr/bin/env python3
"""Plan-only selected-ID diagnostic over the preserved full-lock lifecycle."""
import hashlib
from pathlib import Path
import sys
import types
import phone_value_precision_long as base
import phone_value_precision_long_health as health
from phone_return_long import replace_exact

TOOLS=Path(__file__).resolve().parent
BASE_SHA='ba3a1e324d16e7f73075f4ca3e816efd3e130679beb5cd0bfdb9b7a3de626abd'
HEALTH_SHA='c0443517f18c30436a5b4bacea1b16492ffff4fb07c9b10109f676abb4acb9e6'
STAGE_NAME='selected-id-long-20260911T143756Z-01'
STAGE_DIGEST='07e5b1b5f1e75c20022e6f9356262fe969eadbead6f91b8017f01429c20fc2f2'
LIB_SHA='43b9bf47d82aaf375582c0b5631f8b032f65aeeebc5a7758cb8ea7cae5af022a'


def digest(data):return hashlib.sha256(data).hexdigest()


def materialize_sources():
    if digest(Path(base.__file__).read_bytes())!=BASE_SHA:raise RuntimeError('completed long adapter changed')
    source,shell,_,launch=base.materialize_sources()
    changes=[(base.STAGE_NAME,STAGE_NAME,1),(base.STAGE_DIGEST,STAGE_DIGEST,1),
        ("'.local/value-precision-phone-long-runs'","'.local/selected-id-phone-long-runs'",1),
        ("'/data/local/tmp/vibevoice-0031-value-'","'/data/local/tmp/vibevoice-0031-trace-'",1),
        ('single engineering exact-long/max2048 process','single selected-ID-trace exact-long/max2048 process',1),
        ('precision-path candidate: one fresh-dialog exact-long/max2048 diagnostic only',
         'same precision-path candidate: one fresh-dialog exact-long/max2048 selected-ID observation only',1),
        ('precision-path exact-long engineering max2048 only','selected-ID trace exact-long max2048 only',1)]
    original=source
    for old,new,count in changes:source=replace_exact(source,old,new,count)
    reverse=source
    for old,new,count in reversed(changes):reverse=replace_exact(reverse,new,old,count)
    assert reverse==original
    return source,shell,changes,launch


def load_lifecycle():
    if digest(Path(health.__file__).read_bytes())!=HEALTH_SHA:raise RuntimeError('read-only RPC health adapter changed')
    # Existing actual context + physical-short prerequisite, not a claim that
    # this source-built runtime has already loaded or executed on Android.
    _,prior_receipt=base.load_lifecycle()
    source,shell_source,changes,launch=materialize_sources()
    receipt={'scope':'one actual selected-ID trace of the same1929-input/max2048 candidate, not phone permission',
        'stage_digest':STAGE_DIGEST,'libGenie_sha256':LIB_SHA,'base_adapter_sha256':BASE_SHA,
        'materialized_controller_sha256':digest(source.encode()),'materialized_shell_sha256':digest(shell_source.encode()),
        'adapter_sha256':digest(Path(__file__).read_bytes()),'base_prerequisite':prior_receipt,
        'source_changes':[{'old':a,'new':b,'count':c} for a,b,c in changes],
        'runtime_binary_equivalence_assumed':False,'actual_trace_or_android_compatibility_observed':False,
        'selected_id_boundary':'Sampler return before filtering; EOS membership is not an internal stop decision.',
        'additional_tokenization':'After unchanged query/profile only; no additional neural request.',
        'signal_guard_atomic':False,'original_sources_or_stages_modified':False}
    shell=types.ModuleType('gemma_selected_id_long_shell');shell.__file__=str(TOOLS/'phone_return_shell.py')
    sys.modules[shell.__name__]=shell;exec(compile(shell_source,shell.__file__,'exec'),shell.__dict__)
    module=types.ModuleType('gemma_selected_id_long_controller');module.__file__=str(TOOLS/'phone_return_controller.py')
    sys.modules[module.__name__]=module;module._VALUE_DETACHED_LAUNCH=launch;module._VALUE_SCOPE_RECEIPT=receipt
    exec(compile(source,module.__file__,'exec'),module.__dict__)
    module.common,module.scripts=shell.common,shell.scripts
    parent=module.Controller
    class TraceHealthController(parent):
        def _launch_and_wait(self):
            reply=self._shell('preflight.rpc_readiness',health.PROBE,10)
            observed=health.classify(reply.stdout)
            self.result['rpc_preflight']=observed
            self.result['rpc_health_adapter']={'sha256':digest(Path(health.__file__).read_bytes()),'probe_sha256':digest(health.PROBE.encode())}
            if observed['explicit_resource_blockers']:
                raise module.GuardError('RPC_RESOURCE_NOT_READY: '+'; '.join(observed['explicit_resource_blockers']))
            return super()._launch_and_wait()
    module.Controller=TraceHealthController
    return module,receipt


if __name__=='__main__':
    lifecycle,_=load_lifecycle()
    raise SystemExit(lifecycle.main())
