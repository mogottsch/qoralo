#!/usr/bin/env python3
"""One aligned GPU request over the pinned full-lock lifecycle; plan-only default."""
import hashlib
from pathlib import Path
import shlex
import sys
import types
from phone_return_long import (BASE_CONTROLLER_SHA,BASE_SHELL_SHA,OLD_LAUNCH,replace_exact,detached_launch_command)
from phone_selected_id_appguard import IDENTITY,QUIESCENCE,validate

TOOLS=Path(__file__).resolve().parent
STAGE_NAME='aligned-gpu-20260912T094856Z-01'
STAGE_DIGEST='247493005323235fac12203085f5d07599f179249bbbde908d4c17c288678e92'
FLAGS=['--backend=gpu','--model_path=models/gemma-4-E2B-it.litertlm','--workload_dir=workloads','--output_dir=evidence','--arm_id=0031-single-bos-aligned-gpu','--cache_dir=cache','--max_num_tokens=8192','--max_output_tokens=2048','--num_cpu_threads=4','--request_timeout_seconds=1800','--reset_mode=fresh_session']
APPGUARD_SHA='8602ab27affb039464aad00210d484196b2b32d499466a922251a2469d7b6933'


def sha(data):return hashlib.sha256(data).hexdigest()


def native_argv(remote):return [remote+'/bin/litert_lm_aligned_reference',*FLAGS]


def materialize_sources():
    cb=(TOOLS/'phone_return_controller.py').read_bytes();sb=(TOOLS/'phone_return_shell.py').read_bytes()
    if sha(cb)!=BASE_CONTROLLER_SHA or sha(sb)!=BASE_SHELL_SHA:raise ValueError('reviewed lifecycle source changed')
    source=cb.decode();shell=sb.decode();changes=[];shell_changes=[]
    def patch(text,before,after,count,records):
        records.append((before,after,count));return replace_exact(text,before,after,count)
    def c(before,after,count=1):
        nonlocal source
        source=patch(source,before,after,count,changes)
    def s(before,after,count=1):
        nonlocal shell
        shell=patch(shell,before,after,count,shell_changes)
    c('from prepare_frozen_genie_stage import verify as verify_stage','from prepare_aligned_litert_stage import verify as verify_stage')
    c('stage-freeze-20260910T105830Z-01',STAGE_NAME)
    c('584841604ecf97a1a916c9a7f765e49ff9f7a2ee751a61fda9e9e6588f02fe25',STAGE_DIGEST)
    c("'.local/phone-return-runs'","'.local/aligned-reference-phone-runs'")
    c("'/data/local/tmp/vibevoice-0031-fp16-'","'/data/local/tmp/vibevoice-0031-aligned-'")
    c('single engineering short/max16 process','single input-aligned GPU long/max2048 process')
    c('one fresh-dialog first-short engineering/noncanonical max16 only','one fresh-session aligned GPU long1929/max2048 diagnostic only')
    c('first-short engineering max16 only','aligned GPU long1929/max2048 engineering only')
    c('bin/genie-app','bin/litert_lm_aligned_reference',2)
    c("expected_native_cmd = b'\\0'.join([expected_native_exe, b'-s', b'first-short.script']) + b'\\0'",
      "expected_native_cmd = b'\\0'.join(x.encode() for x in _ALIGNED_ARGV(self.remote)) + b'\\0'")
    c(OLD_LAUNCH,'        command = _ALIGNED_DETACHED_LAUNCH(self.remote)')
    c("'classification': 'collection_not_inference_validation', 'run_id': run_id,",
      "'classification': 'collection_not_inference_validation', 'run_id': run_id,\n                       'aligned_scope_adapter': _ALIGNED_RECEIPT,")
    s('bin/genie-app','bin/litert_lm_aligned_reference',3)
    old='''        expected=$(printf '%s\\n-s\\nfirst-short.script' "$REMOTE/bin/litert_lm_aligned_reference")
        expected_fields=3'''
    new='''        expected=$(printf '%s'''+''.join('\\n'+f for f in FLAGS)+'''\' "$REMOTE/bin/litert_lm_aligned_reference")
        expected_fields=12'''
    s(old,new)
    s('export LD_LIBRARY_PATH="$REMOTE/lib" ADSP_LIBRARY_PATH="$REMOTE/lib" QNN_LOG_LEVEL=verbose','export LD_LIBRARY_PATH="$REMOTE/lib"')
    s('exec "$REMOTE/bin/litert_lm_aligned_reference" -s first-short.script',
      'exec "$REMOTE/bin/litert_lm_aligned_reference" '+' '.join(shlex.quote(x) for x in FLAGS))
    for text,original,records in ((source,cb.decode(),changes),(shell,sb.decode(),shell_changes)):
        for old,new,count in reversed(records):text=replace_exact(text,new,old,count)
        if text!=original:raise ValueError('inverse lifecycle reconstruction failed')
    return source,shell,changes,shell_changes


def load_lifecycle():
    if sha((TOOLS/'phone_selected_id_appguard.py').read_bytes())!=APPGUARD_SHA:raise ValueError('current-app guard changed')
    source,shell_source,changes,shell_changes=materialize_sources()
    receipt={'scope':'one aligned GPU reference only; actual Pi slot required','stage_digest':STAGE_DIGEST,
      'controller_sha256':sha(source.encode()),'shell_sha256':sha(shell_source.encode()),
      'adapter_sha256':sha(Path(__file__).read_bytes()),'stage_verifier_sha256':sha((TOOLS/'prepare_aligned_litert_stage.py').read_bytes()),
      'appguard_sha256':APPGUARD_SHA,'native_flags':FLAGS,'inverse_reconstruction_exact':True,
      'controller_changes':[{'before':a,'after':b,'count':c} for a,b,c in changes],
      'shell_changes':[{'before':a,'after':b,'count':c} for a,b,c in shell_changes],
      'signal_guard_atomic':False,'historical_gpu_binary_equivalence_proven':False}
    sm=types.ModuleType('aligned_reference_shell');sm.__file__=str(TOOLS/'phone_return_shell.py');sys.modules[sm.__name__]=sm
    exec(compile(shell_source,sm.__file__,'exec'),sm.__dict__)
    module=types.ModuleType('aligned_reference_controller');module.__file__=str(TOOLS/'phone_return_controller.py');sys.modules[module.__name__]=module
    module._ALIGNED_ARGV=native_argv;module._ALIGNED_DETACHED_LAUNCH=detached_launch_command;module._ALIGNED_RECEIPT=receipt
    exec(compile(source,module.__file__,'exec'),module.__dict__)
    module.common,module.scripts=sm.common,sm.scripts
    parent=module.Controller
    class AlignedController(parent):
        def _identity(self):
            super()._identity()
            reply=self._shell('preflight.current_app_identity_quiescence',IDENTITY+QUIESCENCE,45)
            self.result['current_app_preflight']=validate(reply.stdout,True)
        def _stage(self,manifest):
            super()._stage(manifest)
            self._shell('stage.fresh_real_cache','mkdir -m 700 '+shlex.quote(self.remote+'/cache'),10)
            self.result['fresh_owned_real_cache_created']=True
        def _launch_and_wait(self):
            reply=self._shell('preflight.app_quiescence_before_launch',QUIESCENCE,10)
            self.result['app_quiescence_before_launch']=validate(reply.stdout)
            return super()._launch_and_wait()
    module.Controller=AlignedController
    return module,receipt


if __name__=='__main__':
    lifecycle,_=load_lifecycle()
    raise SystemExit(lifecycle.main())
