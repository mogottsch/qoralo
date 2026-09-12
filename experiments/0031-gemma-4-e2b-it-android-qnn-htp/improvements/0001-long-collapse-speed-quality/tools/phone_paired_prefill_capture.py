#!/usr/bin/env python3
"""Plan-only until a new Pi slot, full current APK hashes and quiescence grant."""
import argparse
import hashlib
from pathlib import Path
import re
import sys
import types

import phone_selected_id_long as base
import phone_selected_id_appguard as old_app
import phone_value_precision_long_health as health
import app_playback_quiescence as playback
from phone_return_long import replace_exact

TOOLS=Path(__file__).resolve().parent
STAGE_NAME='paired-prefill-capture-stage-01'
STAGE_DIGEST='b99056c1faa1e25823fd9bcda2a0968a0445cb93458dc1069e7d269eb9c54953'
LIB_SHA='3a61a7ea888e39b54999c25b0644ff068733c343cb693e5eafee9be4538dccc2'
QUIET=r'''
command -v pidof >/dev/null || exit 45
for process in dev.vibevoice.podcast.internal:generation dev.vibevoice.podcast.internal.test; do
  value=$(pidof "$process" 2>/dev/null)
  code=$?
  [ "$code" = 0 ] || [ "$code" = 1 ] || exit 46
  printf 'PID\t%s\t%s\n' "$process" "$value"
done
'''


def digest(data):return hashlib.sha256(data).hexdigest()


def validate_app(data,expected,identity=True):
    rows=[x.split('\t') for x in data.decode(errors='replace').splitlines()]
    apks={x[1]:x[2] for x in rows if len(x)==3 and x[0]=='APK'}
    pids={x[1]:x[2] for x in rows if len(x)==3 and x[0]=='PID'}
    if identity and apks!=expected:raise ValueError('current full APK identity mismatch/unavailable; no restore/install')
    names={'dev.vibevoice.podcast.internal:generation','dev.vibevoice.podcast.internal.test'}
    if set(pids)!=names or any(pids.values()):raise ValueError('generation/test process active or unknown; no force-stop')
    return {'current_apks':apks if identity else None,'generation_and_test_absent':True,'idle_main_process_not_a_generation_claim':True,'actual_user_job_quiescence_requires_separate_Pi_attestation':True}


def materialize_sources():
    source,shell,_,launch=base.materialize_sources();original=source;original_shell=shell
    changes=[(base.STAGE_NAME,STAGE_NAME,1),(base.STAGE_DIGEST,STAGE_DIGEST,1),
      ("'.local/selected-id-phone-long-runs'","'.local/paired-prefill-phone-runs'",1),
      ("'/data/local/tmp/vibevoice-0031-trace-'","'/data/local/tmp/vibevoice-0031-paired-'",1),
      ('single selected-ID-trace exact-long/max2048 process','single paired-prefill exact1929/max1 capture process',1),
      ('same precision-path candidate: one fresh-dialog exact-long/max2048 selected-ID observation only','same precision-path candidate: one fresh-dialog exact1929/max1 input/logit capture only',1),
      ('selected-ID trace exact-long max2048 only','paired-prefill capture only; no AR continuation',1)]
    for a,b,n in changes:source=replace_exact(source,a,b,n)
    count=source.count('1800');source=replace_exact(source,'1800','300',count);changes.append(('1800','300',count))
    env='export LD_LIBRARY_PATH="$REMOTE/lib" ADSP_LIBRARY_PATH="$REMOTE/lib" QNN_LOG_LEVEL=verbose'
    new=env+'\nexport GEMMA_PREFILL_CAPTURE_DIR="$REMOTE/evidence/prefill-capture"\nmkdir -m 700 "$GEMMA_PREFILL_CAPTURE_DIR" || exit 71\nulimit -v 8388608 || exit 72'
    shell=replace_exact(shell,env,new,1);shell_count=shell.count('1800');shell=replace_exact(shell,'1800','300',shell_count)
    restored=source
    for a,b,n in reversed(changes):restored=replace_exact(restored,b,a,n)
    if restored!=original:raise ValueError('unbounded lifecycle delta')
    if shell.replace('300','1800').replace(new,env)!=original_shell:raise ValueError('unbounded shell delta')
    return source,shell,launch,changes


def load_lifecycle(expected_apks,job_quiet):
    _,prior=base.load_lifecycle();source,shell_source,launch,changes=materialize_sources()
    receipt={'scope':'one actual frozen-Genie prefilling capture; no current execution grant','stage_digest':STAGE_DIGEST,'libGenie_sha256':LIB_SHA,'source_changes':changes,'controller_sha256':digest(source.encode()),'shell_sha256':digest(shell_source.encode()),'prior_lifecycle_binding':prior,'phone_process_seconds':300,'address_space_limit_bytes':8*1024**3,'address_space_not_RSS_or_HTP_private_memory':True,'capture_payload_cap_bytes':80*1024**2,'actual_user_job_quiescence_attested':job_quiet,'current_expected_APK_hashes':expected_apks,'host_memory_lock_admission':False,'phone_lock_required':True}
    shell=types.ModuleType('paired_prefill_shell');shell.__file__=str(TOOLS/'phone_return_shell.py');sys.modules[shell.__name__]=shell;exec(compile(shell_source,shell.__file__,'exec'),shell.__dict__)
    module=types.ModuleType('paired_prefill_controller');module.__file__=str(TOOLS/'phone_return_controller.py');sys.modules[module.__name__]=module;module._VALUE_DETACHED_LAUNCH=launch;module._VALUE_SCOPE_RECEIPT=receipt;exec(compile(source,module.__file__,'exec'),module.__dict__);module.common,module.scripts=shell.common,shell.scripts
    receipt['actual_job_probe_sha256']=digest(playback.probe_script().encode())
    receipt['playback_guard_version']=2
    parent=module.Controller
    class CaptureController(parent):
        def _actual_playback(self,label):
            reply=self._shell(label,playback.probe_script(),30)
            self.result[label]=playback.validate(reply.stdout)
        def _identity(self):
            if not job_quiet or len(expected_apks)!=2 or any(not re.fullmatch('[0-9a-f]{64}',v) for v in expected_apks.values()):raise module.GuardError('fresh full APK identities and Pi actual-job-quiescence grant required')
            super()._identity()
            reply=self._shell('preflight.current_APKs_and_generation',old_app.IDENTITY+QUIET,45);self.result['current_app_preflight']=validate_app(reply.stdout,expected_apks)
            self._actual_playback('preflight.actual_user_job_playback_v2')
        def _launch_and_wait(self):
            reply=self._shell('preflight.current_job_quiescence',QUIET,10);validate_app(reply.stdout,expected_apks,False)
            self._actual_playback('prelaunch.actual_user_job_playback_v2')
            reply=self._shell('preflight.rpc_readiness',health.PROBE,10);observed=health.classify(reply.stdout);self.result['rpc_preflight']=observed
            if observed['explicit_resource_blockers']:raise module.GuardError('RPC_RESOURCE_NOT_READY')
            return super()._launch_and_wait()
        def _cleanup_root(self):
            super()._cleanup_root()
            if self.launch_attempted:
                reply=self._shell('postflight.current_APKs_and_generation',old_app.IDENTITY+QUIET,45);self.result['postflight_app_identity']=validate_app(reply.stdout,expected_apks)
    module.Controller=CaptureController
    prior_plan=module.plan
    def capture_plan():
        value=prior_plan();value['requires']+=['--expected-app-sha256 (fresh full hash)','--expected-test-sha256 (fresh full hash)','--pi-user-job-quiescent (actual job/playback idle, not inferred from idle main)']
        value.update(playback_guard='streaming UID-only v2; upstream exit and parse status required',capture_noncache_inputs_only=True,host_reference_uses_own_caches=True,capture_payload_cap_bytes=80*1024**2,phone_address_space_limit_bytes=8*1024**3,phone_RSS_and_HTP_private_hard_cap_available=False)
        return value
    module.plan=capture_plan
    return module,receipt


def main():
    p=argparse.ArgumentParser(add_help=False);p.add_argument('--expected-app-sha256');p.add_argument('--expected-test-sha256');p.add_argument('--pi-user-job-quiescent',action='store_true');args,rest=p.parse_known_args()
    expected={'dev.vibevoice.podcast.internal':args.expected_app_sha256,'dev.vibevoice.podcast.internal.test':args.expected_test_sha256}
    expected={k:v for k,v in expected.items() if v}
    if '--execute' in rest and (len(expected)!=2 or not args.pi_user_job_quiescent):p.error('new full APK hashes and actual-user-job quiescence attestation required before execution')
    module,_=load_lifecycle(expected,args.pi_user_job_quiescent);sys.argv=[sys.argv[0],*rest];return module.main()


if __name__=='__main__':raise SystemExit(main())
