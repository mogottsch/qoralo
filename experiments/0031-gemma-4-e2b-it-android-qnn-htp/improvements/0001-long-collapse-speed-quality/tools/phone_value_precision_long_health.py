#!/usr/bin/env python3
"""Pi-requested read-only RPC readiness check before the one frozen long query.

No backend reset, reboot, extra model load or extra inference request. Unexposed
health telemetry is unknown, not proof of failure; the actual Genie backend
initialization remains the fresh functional check within this same request.
"""
import hashlib
from pathlib import Path
import phone_value_precision_long as base

BASE_SHA = 'ba3a1e324d16e7f73075f4ca3e816efd3e130679beb5cd0bfdb9b7a3de626abd'
PROBE = r'''
for key in init.svc.vendor.cdsprpcd init.svc.vendor.adsprpcd; do
  value=$(getprop "$key")
  printf 'SERVICE\t%s\t%s\n' "$key" "$value"
done
found=0
for dir in /sys/bus/msm_subsys/devices/*; do
  [ -r "$dir/name" ] || continue
  name=$(cat "$dir/name") || continue
  case "$name" in cdsp|CDSP)
    found=1
    state=$(cat "$dir/state" 2>/dev/null) || state=UNREADABLE
    printf 'SUBSYSTEM\t%s\t%s\n' "$name" "$state"
  esac
done
[ "$found" = 1 ] || printf 'SUBSYSTEM\tcdsp\tUNEXPOSED\n'
'''


def classify(data):
    rows, blockers = [], []
    for line in data.decode('utf-8', errors='replace').splitlines():
        fields = line.split('\t')
        if len(fields) != 3:
            continue
        kind, name, state = fields
        rows.append({'kind': kind, 'name': name, 'state': state or None})
        if kind == 'SUBSYSTEM' and name.lower() == 'cdsp' and state.lower() in ('offline','crashed','restarting','disabled'):
            blockers.append('CDSP state '+state)
        if kind == 'SERVICE' and name == 'init.svc.vendor.cdsprpcd' and state in ('stopped','restarting'):
            blockers.append('CDSP RPC service '+state)
    return {'observations': rows, 'explicit_resource_blockers': blockers,
            'functional_rpc_health_proven': False,
            'limitation': 'Read-only service/sysfs snapshot only; missing/unexposed fields remain unknown. Functional readiness is established only by this run\'s actual backend initialization/execution.'}


def load_lifecycle():
    if hashlib.sha256(Path(base.__file__).read_bytes()).hexdigest() != BASE_SHA:
        raise RuntimeError('frozen exact-long adapter changed')
    module, receipt = base.load_lifecycle()
    parent = module.Controller
    class HealthController(parent):
        def _launch_and_wait(self):
            # Called only after stage verification, slot claim, lock, identity and
            # staging. No SDK/library/model is loaded by this additional probe.
            reply = self._shell('preflight.rpc_readiness', PROBE, 10)
            observed = classify(reply.stdout)
            self.result['rpc_preflight'] = observed
            self.result['rpc_health_adapter'] = {
                'sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'base_adapter_sha256': BASE_SHA, 'probe_sha256': hashlib.sha256(PROBE.encode()).hexdigest()}
            if observed['explicit_resource_blockers']:
                raise module.GuardError('RPC_RESOURCE_NOT_READY: '+ '; '.join(observed['explicit_resource_blockers']))
            return super()._launch_and_wait()
    module.Controller = HealthController
    return module, receipt


if __name__ == '__main__':
    lifecycle, _ = load_lifecycle()
    raise SystemExit(lifecycle.main())
