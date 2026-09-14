#!/usr/bin/env python3
"""Plan-only tiny HTP Power/normalization bundle; no phone grant from preparation."""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import sys
import types

TOOLS=Path(__file__).resolve().parent
TRACK=TOOLS.parent
BASE_ADAPTER_SHA='73280bf1c684900a0925ec9cb1d8968a6f7479efbef6503e213f8968310d26a7'
BASE_SHELL_SHA='4ce478abf5b44ea0ae32cb9f490eb319f37fd54243fa91fb1433883c8be9b7bb'
STAGE_NAME='htp-power-edge-stage-01'
DIGEST='51053482d9d0d198b43343830503d8c1c3d2ee3337c4ccb598e792248dffb993'
STAGE=TRACK/'.local/frozen-stages'/STAGE_NAME
LIB_SHA='4f5b4d11b128d78433730a4f5e88841e51aec472c6bd28ffd858dba8ea1012fb'
GRAPHS=('power_edge','normalization_chain','normalization_exposed')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_stage(stage,digest):
    stage=Path(stage).resolve()
    if stage!=STAGE.resolve() or digest!=DIGEST or sha(stage/'frozen-manifest.json')!=DIGEST:raise ValueError('exact frozen tiny stage required')
    m=json.loads((stage/'frozen-manifest.json').read_text())
    if m['expected_graph_order']!=list(GRAPHS) or m['backend_id']!=6 or m['soc_model']!=43 or m['full_LLM_or_reference'] or m['learned_weights_or_actual_model_inputs']:raise ValueError('tiny-only HTP contract mismatch')
    expected=set(m['files'])|{'frozen-manifest.json','SHA256SUMS'}
    if {str(p.relative_to(stage)) for p in stage.rglob('*') if p.is_file()}!=expected:raise ValueError('unexpected stage files')
    total=0
    for name,v in m['files'].items():
        p=stage/name
        if p.is_symlink() or p.stat().st_size!=v['bytes'] or sha(p)!=v['sha256']:raise ValueError('tiny stage payload changed '+name)
        mode=0o555 if name=='bin/qnn-net-run' else 0o400
        if p.stat().st_mode&0o777!=mode:raise ValueError('tiny stage mode changed '+name)
        total+=v['bytes']
    if total!=m['payload_bytes'] or total>64*1024**2 or any('Cpu' in n or 'Genie' in n for n in m['files']):raise ValueError('payload size/route mismatch')
    expected_sums=''.join(f'{v["sha256"]}  {n}\n' for n,v in sorted(m['files'].items()))+f'{DIGEST}  frozen-manifest.json\n'
    if (stage/'SHA256SUMS').read_text()!=expected_sums:raise ValueError('frozen checksum manifest changed')
    return m


def argv(remote):
    return [remote+'/bin/qnn-net-run','--backend',remote+'/lib/libQnnHtp.so','--retrieve_context',remote+'/power-edge-context.bin','--input_list',','.join(remote+'/evidence/'+g+'.inputlist' for g in GRAPHS),'--output_dir',remote+'/evidence/outputs','--num_inferences','1','--use_native_input_files','--use_native_output_files','--shared_buffer','--profiling_level','basic','--log_level','info']


def common(remote):
    if sha(TOOLS/'phone_return_shell.py')!=BASE_SHELL_SHA:raise ValueError('bound common identity helper changed')
    import phone_return_shell as shell
    old=shell.common(remote)
    before='''if [ "$exe" = "$REMOTE/bin/genie-app" ]; then
        expected=$(printf '%s\\n-s\\nfirst-short.script' "$REMOTE/bin/genie-app")
        expected_fields=3'''
    after='''if [ "$exe" = "$REMOTE/bin/qnn-net-run" ]; then
        expected=$(printf '%s\\n' '''+' '.join(shlex.quote(v) for v in argv(remote))+''')
        expected_fields='''+str(len(argv(remote)))
    if old.count(before)!=1:raise ValueError('native identity block changed')
    new=old.replace(before,after)
    if new.replace(after,before)!=old:raise ValueError('unbounded identity helper mutation')
    return new


def scripts(remote):
    import phone_return_shell as shell
    result=shell.scripts(remote);result['control.sh']=common(remote);source='. '+shlex.quote(remote+'/control.sh')+'\n'
    lists=''.join("printf '%s\\n' "+shlex.quote(('base' if g=='power_edge' else 'x')+':='+remote+'/inputs/'+g+'.uint16le')+' > '+shlex.quote(remote+'/evidence/'+g+'.inputlist')+'\n' for g in GRAPHS)
    result['model-entry.sh']='#!/system/bin/sh\nset -eu\n'+source+r'''
record_self model
cd "$REMOTE"
export LD_LIBRARY_PATH="$REMOTE/lib" ADSP_LIBRARY_PATH="$REMOTE/lib" QNN_LOG_LEVEL=info
ulimit -v 12582912 || exit 72
# Conservative <=16MiB per file; actual byte limits are read back below.
ulimit -f 16384 || exit 73
cat "/proc/$$/limits" > "$REMOTE/evidence/limits-pre-exec.txt"
set -- $(awk '/^Max address space/ {print $4, $5}' "$REMOTE/evidence/limits-pre-exec.txt")
[ "$1" = 12884901888 ] && [ "$2" = 12884901888 ] || exit 74
set -- $(awk '/^Max file size/ {print $4, $5}' "$REMOTE/evidence/limits-pre-exec.txt")
[ "$1" -ge 393216 ] && [ "$1" -le 16777216 ] && [ "$2" -le 16777216 ] || exit 75
'''+lists+'exec '+' '.join(shlex.quote(v) for v in argv(remote))+'\n'
    watchdog=result['watchdog.sh'].replace('1800','90')
    before='''  if [ "$now" -ge "$deadline" ]; then
    printf 'deadline90\\n' > "$REMOTE/evidence/watchdog-timeout.txt"'''
    after='''  kb=$(du -sk "$REMOTE/evidence" | awk '{print $1}')
  case "$kb" in ''|*[!0-9]*) kb=16385;; esac
  if [ "$now" -ge "$deadline" ] || [ "$kb" -gt 16384 ]; then
    if [ "$kb" -gt 16384 ]; then reason=evidence_budget_or_unavailable; else reason=deadline90; fi
    printf '%s\\n' "$reason" > "$REMOTE/evidence/watchdog-timeout.txt"'''
    if watchdog.count(before)!=1:raise ValueError('watchdog limit anchor changed')
    result['watchdog.sh']=watchdog.replace(before,after)
    return result


def load_lifecycle(expected_apks,job_quiet):
    if sha(TOOLS/'phone_legacy_prefill_capture.py')!=BASE_ADAPTER_SHA:raise ValueError('corrected postflight/appguard base changed')
    import phone_legacy_prefill_capture as baseline
    m,prior=baseline.load_adapter();parent_materialize=m.materialize_sources
    m.STAGE_NAME=STAGE_NAME;m.STAGE_DIGEST=DIGEST;m.LIB_SHA=LIB_SHA
    def materialize():
        source,old_shell,launch,changes=parent_materialize();original=source
        args_expression='['+', '.join('(self.remote + '+repr(v.replace('@REMOTE@','',1))+').encode()' if v.startswith('@REMOTE@') else repr(v.encode()) for v in argv('@REMOTE@'))+']'
        # The comma-separated input-list argument needs each remote prefix expanded.
        comma=','.join('@REMOTE@/evidence/'+g+'.inputlist' for g in GRAPHS)
        wrong='(self.remote + '+repr(comma.replace('@REMOTE@','',1))+').encode()'
        right="','.join(self.remote + '/evidence/' + g + '.inputlist' for g in ('power_edge','normalization_chain','normalization_exposed')).encode()"
        args_expression=args_expression.replace(wrong,right)
        before="expected_native_cmd = b'\\0'.join([expected_native_exe, b'-s', b'exact-long.script']) + b'\\0'"
        extra=[("'.local/legacy-logits-phone-runs'","'.local/htp-power-phone-runs'",1),("'/data/local/tmp/vibevoice-0031-legacy-logits-'","'/data/local/tmp/vibevoice-0031-htp-power-'",1),('bin/genie-app','bin/qnn-net-run',2),(before,"expected_native_cmd = b'\\0'.join("+args_expression+") + b'\\0'",1),("'process_deadline_seconds': 300","'process_deadline_seconds': 90",1),('self.deadline = start + 300','self.deadline = start + 90',1),('host_300s_deadline','host_90s_deadline',1),('remote_300s_watchdog','remote_watchdog_limit',1),("'long_script': True","'long_script': False",2),('nohup sleep readlink tr awk wc;','nohup sleep readlink tr awk wc du;',1),('same precision-path candidate: one fresh-dialog exact1929/max1 input/logit capture only','three authored HTP scalar/normalization graphs only; no LLM/reference',1),('paired-prefill capture only; no AR continuation','three tiny HTP graphs; native raw codes; no model/reference/CPU fallback',1)]
        for a,b,count in extra:
            if source.count(a)!=count:raise ValueError('tiny controller anchor changed '+a)
            source=source.replace(a,b)
        inverse=source
        for a,b,count in reversed(extra):inverse=inverse.replace(b,a)
        if inverse!=original:raise ValueError('unbounded tiny lifecycle mutation')
        return source,'from phone_htp_power_discriminator import common, scripts\n',launch,changes+extra
    m.materialize_sources=materialize
    module,receipt=m.load_lifecycle(expected_apks,job_quiet)
    receipt['libQnnHtp_sha256']=receipt.pop('libGenie_sha256');receipt['scope']='one tiny three-graph HTP edge/fusion checkpoint; not device permission';receipt['phone_process_seconds']=90;receipt['capture_payload_cap_bytes']=16*1024**2;receipt['capture_budget_is_polled_with_possible_overshoot']=True;receipt['expected_raw_output_bytes']=1180672;receipt['tiny_adapter_sha256']=sha(Path(__file__));receipt['baseline_corrected_guard']=prior
    parent=module.Controller
    class TinyController(parent):
        def __init__(self,**kwargs):
            kwargs.setdefault('stage_verifier',verify_stage);super().__init__(**kwargs)
    module.Controller=TinyController
    old_plan=module.plan
    def plan():
        p=old_plan()
        for key in ['capture_noncache_inputs_only','host_reference_uses_own_caches']:p.pop(key,None)
        p.update(scope=receipt['scope'],stage=str(STAGE),reviewed_stage_digest=DIGEST,process_deadline_seconds=90,long_script=False,graph_count=3,requested_executions_per_graph=1,expected_raw_output_bytes=1180672,capture_payload_cap_bytes=16*1024**2,budget_polled_possible_overshoot=True,pre_exec_AS_and_file_limits_readback_required=True,CPU_fallback_available_in_bundle=False,phone_permission_granted_by_plan=False)
        return p
    module.plan=plan
    return module,receipt


def main():
    p=argparse.ArgumentParser(add_help=False);p.add_argument('--expected-app-sha256');p.add_argument('--expected-test-sha256');p.add_argument('--pi-user-job-quiescent',action='store_true');a,rest=p.parse_known_args()
    expected={k:v for k,v in {'dev.vibevoice.podcast.internal':a.expected_app_sha256,'dev.vibevoice.podcast.internal.test':a.expected_test_sha256}.items() if v}
    if '--execute' in rest and (len(expected)!=2 or not a.pi_user_job_quiescent):p.error('fresh full APK hashes, actual quiescence and Pi grant required')
    module,_=load_lifecycle(expected,a.pi_user_job_quiescent);sys.argv=[sys.argv[0],*rest];return module.main()


if __name__=='__main__':raise SystemExit(main())
