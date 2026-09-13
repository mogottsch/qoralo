#!/usr/bin/env python3
"""ONE captured-input declared-policy reference; strict new-observer binding only."""
import hashlib
import json
from pathlib import Path
import sys
import types

TOOLS=Path(__file__).resolve().parent
BASE_SHA='8cf6112cbb948bec4ab5fe1fd9ce16564efa6e8102d76a7f21a44c5904dfb496'
VALIDATOR_SHA='5896074000e806339e3925d0391b11b9879aef77c925d36ca0a2a65acb6db19c'
STAGE='7b61cf0a03ad93292127a7ad59e1b74ae9b61ac4e660691a0cff5a947b40486c'
REFERENCE_ARTIFACTS={
    str(TOOLS.parent/'.local/matched-prefill-reference/policy-01/policy.json'):'7fffebe9208bc5e2b92d80ed6ed01b7b57263e8f23d188188588682754c18b59',
    str(TOOLS.parent/'.local/matched-prefill-reference/inputs-01/ledger.json'):'db3e696fecec12ab35b8fda9b020a15537a59620cc624d3875dd87d6f25fd3cf',
}


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_adapter():
    path=TOOLS/'run_paired_prefill_host.py';validator=TOOLS/'validate_legacy_prefill_capture.py'
    if sha(path)!=BASE_SHA or sha(validator)!=VALIDATOR_SHA:raise ValueError('frozen original host or corrected-capture validator changed')
    source=path.read_text();original=types.ModuleType('original_paired_prefill_host');original.__file__=str(path);exec(compile(source,str(path),'exec'),original.__dict__)
    original.assert_host_sources()  # Preserve the original readiness bindings for BOTH math helpers and old guard.
    prior=source
    changes=[("ROOT=TRACK/'.local/paired-prefill-host-runs'","ROOT=TRACK/'.local/legacy-prefill-host-runs'"),("STAGE_SHA='b99056c1faa1e25823fd9bcda2a0968a0445cb93458dc1069e7d269eb9c54953'","STAGE_SHA='"+STAGE+"'"),('results/matched-prefill-reference-readiness-01/implementation-bindings.json','results/paired-legacy-host-binding-01/implementation-bindings.json')]
    for before,after in changes:
        if source.count(before)!=1:raise ValueError('host binding anchor changed')
        source=source.replace(before,after)
    inverse=source
    for before,after in reversed(changes):inverse=inverse.replace(after,before)
    if inverse!=prior:raise ValueError('host computation/limit change')
    module=types.ModuleType('legacy_prefill_host_bound');module.__file__=str(Path(__file__).resolve());exec(compile(source,module.__file__,'exec'),module.__dict__)
    import validate_legacy_prefill_capture as capture
    spec=capture.specification()
    parent_sources=module.assert_host_sources
    def sources():
        old=original.assert_host_sources();new=parent_sources()
        if sha(validator)!=VALIDATOR_SHA or sha(capture.BINDING)!=capture.BINDING_SHA:raise ValueError('new strict binding changed')
        for artifact,expected in REFERENCE_ARTIFACTS.items():
            if sha(artifact)!=expected:raise ValueError('frozen final-DLC policy or own-cache/input ledger changed')
        return dict(sorted({**old,**new,**REFERENCE_ARTIFACTS,str(validator):VALIDATOR_SHA,str(capture.BINDING):capture.BINDING_SHA}.items()))
    module.assert_host_sources=sources
    parent_validate=module.validate_phone
    def validate(path):
        cap=parent_validate(path)  # Original IDs/exact16 AR128/zeroAR1/success/release gates, with the explicit new stage.
        report=capture.validate(path)
        if cap.resolve()!=Path(report['capture_dir']).resolve():raise ValueError('capture path disagreement')
        return cap
    module.validate_phone=validate
    parent_internal=module.internal
    def internal(root,compute=False):
        root=Path(root).resolve()
        if not root.is_relative_to(module.ROOT):raise ValueError('owned host root required')
        grant=json.loads((root/'grant.json').read_text())
        if grant['grant_id']!=spec['host_grant_id'] or grant['phone_collection']!=spec['phone_collection']:raise ValueError('only the one authorized exact-capture host grant is accepted')
        if grant['unit'] not in Path('/proc/self/cgroup').read_text():raise PermissionError('same bounded systemd unit required')
        validate(grant['phone_collection'])
        return parent_internal(root,compute)
    module.internal=internal
    parent_main=module.main
    def main():
        if '--execute' in sys.argv:
            try:value=sys.argv[sys.argv.index('--pi-grant')+1]
            except (ValueError,IndexError):raise PermissionError('explicit one-use host grant required')
            if value!=spec['host_grant_id']:raise PermissionError('wrong host grant; no replay/sweep')
        return parent_main()
    module.main=main
    return module,{'original_host_sha256':BASE_SHA,'validator_sha256':VALIDATOR_SHA,'capture_binding_sha256':capture.BINDING_SHA,'materialized_source_sha256':hashlib.sha256(source.encode()).hexdigest(),'source_changes':changes,'added_validation':'exact same-run payload hashes, actual corrected observer/AS12/row8-before-dequant provenance and independent postflight; repeated inside bounded worker','original_computation_cache_flow_and_limits_unchanged':True,'own30caches':True,'HTP_caches_imported':False,'model_executed_by_loading':False,'DSP_bit_exact_claim':False}


if __name__=='__main__':
    module,_=load_adapter()
    raise SystemExit(module.main())
