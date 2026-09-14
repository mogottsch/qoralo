#!/usr/bin/env python3
"""Two remaining named graphs, separate one-execution processes, ONE continuous lease."""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import sys
import types

TOOLS=Path(__file__).resolve().parent
TRACK=TOOLS.parent
BASE_SHA='e92a637841cf69515eaa30ebdbc3217838b2ec0a7757091655e223f002d7a383'
CASES=('normalization_chain','normalization_exposed')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def base_module():
    if sha(TOOLS/'phone_htp_power_discriminator.py')!=BASE_SHA:raise ValueError('frozen shared-buffer lifecycle base changed')
    import phone_htp_power_discriminator as base
    return base


def case_argv(remote,case):
    if case not in CASES:raise ValueError('ONLY the two unexecuted chain cases are allowed')
    base=base_module();args=base.argv(remote);lists=['__','__','__'];lists[base.GRAPHS.index(case)]=remote+'/evidence/'+case+'.inputlist'
    args[args.index('--input_list')+1]=','.join(lists);args[args.index('--output_dir')+1]=remote+'/evidence/'+case+'/outputs'
    return args


def phase_common(remote,case):
    base=base_module();source=base.common(remote);original=source
    a="expected=$(printf '%s\\n' "+' '.join(shlex.quote(v) for v in base.argv(remote))+')'
    b="expected=$(printf '%s\\n' "+' '.join(shlex.quote(v) for v in case_argv(remote,case))+')'
    changes=[(a,b,1),('"$REMOTE/evidence/$1.pid"','"$REMOTE/evidence/'+case+'.$1.pid"',1),('"$REMOTE/evidence/$1.start"','"$REMOTE/evidence/'+case+'.$1.start"',1),('model-entry.sh',case+'-model-entry.sh',1),('script=launch.sh; else script=watchdog.sh','script='+case+'-launch.sh; else script='+case+'-watchdog.sh',1)]
    for before,after,count in changes:
        if source.count(before)!=count:raise ValueError('phase common anchor changed')
        source=source.replace(before,after)
    restored=source
    for before,after,count in reversed(changes):restored=restored.replace(after,before)
    if restored!=original:raise ValueError('unbounded phase identity delta')
    return source


def phase_scripts(remote,case):
    base=base_module();original=base.scripts(remote);result={}
    for name,text in original.items():
        if name=='control.sh':result[case+'-'+name]=phase_common(remote,case);continue
        text=text.replace(remote+'/control.sh',remote+'/'+case+'-control.sh')
        if name=='model-entry.sh':
            text=text.replace('exec '+' '.join(shlex.quote(v) for v in base.argv(remote)),'exec '+' '.join(shlex.quote(v) for v in case_argv(remote,case)))
            text='\n'.join(line for line in text.splitlines() if not (line.startswith('printf ') and '.inputlist' in line and case+'.inputlist' not in line))+'\n'
        for leaf in ['limits-pre-exec.txt','start.uptime','runner.stdout','runner.stderr','watchdog.stdout','watchdog.stderr','exit-code.tmp','exit-code.txt','watchdog-timeout.txt','model.pid','model.start']:
            text=text.replace('evidence/'+leaf,'evidence/'+case+'.'+leaf)
        for leaf in ['model-entry.sh','watchdog.sh']:text=text.replace('"$REMOTE/'+leaf+'"','"$REMOTE/'+case+'-'+leaf+'"')
        result[case+'-'+name]=text
    return result


def all_scripts(remote):
    return {name:text for case in CASES for name,text in phase_scripts(remote,case).items()}


def reconstruct_controller(expected,quiet):
    base=base_module();main,receipt=base.load_lifecycle(expected,quiet)
    import phone_legacy_prefill_capture as legacy
    parent,_=legacy.load_adapter();parent.STAGE_NAME=base.STAGE_NAME;parent.STAGE_DIGEST=base.DIGEST;parent.LIB_SHA=base.LIB_SHA
    source,_,_,prefix=parent.materialize_sources()
    if receipt['source_changes'][:len(prefix)]!=prefix:raise ValueError('base reconstruction prefix changed')
    for before,after,count in receipt['source_changes'][len(prefix):]:
        if source.count(before)!=count:raise ValueError('base controller reconstruction anchor changed')
        source=source.replace(before,after)
    if hashlib.sha256(source.encode()).hexdigest()!=receipt['controller_sha256']:raise ValueError('base controller reconstruction digest mismatch')
    return main,receipt,source


def phase_core(source,case,scope):
    original=source
    cmd_line=next(line for line in source.splitlines() if line.strip().startswith('expected_native_cmd ='))
    changes=[("root = shlex.quote(self.remote + '/evidence/' + role)","root = shlex.quote(self.remote + '/evidence/' + CASE + '.' + role)",1),(cmd_line,"        expected_native_cmd = b'\\0'.join(v.encode() for v in _CASE_ARGV(self.remote)) + b'\\0'",1),("script = {'model': 'model-entry.sh', 'wrapper': 'launch.sh', 'watchdog': 'watchdog.sh'}[role]","script = CASE + '-' + {'model': 'model-entry.sh', 'wrapper': 'launch.sh', 'watchdog': 'watchdog.sh'}[role]",1),('/watchdog-timeout.txt','/{CASE}.watchdog-timeout.txt',1),('/exit-code.txt','/{CASE}.exit-code.txt',2)]
    for before,after,count in changes:
        if source.count(before)!=count:raise ValueError('phase controller anchor changed '+before)
        source=source.replace(before,after)
    restored=source
    for before,after,count in reversed(changes):restored=restored.replace(after,before)
    if restored!=original:raise ValueError('unbounded phase controller delta')
    import phone_return_long as detached
    def launch(remote):
        return detached.detached_launch_command(remote).replace(remote+'/launch.sh',remote+'/'+case+'-launch.sh').replace(remote+'/evidence/launcher.',remote+'/evidence/'+case+'.launcher.')
    module=types.ModuleType('isolated_chain_phase_'+case);module.__file__=str(TOOLS/'phone_return_controller.py');module.CASE=case;module._CASE_ARGV=lambda remote:case_argv(remote,case);module._VALUE_DETACHED_LAUNCH=launch;module._VALUE_SCOPE_RECEIPT=scope
    exec(compile(source,module.__file__,'exec'),module.__dict__);module.common=lambda remote:phase_common(remote,case)
    return module,{'case':case,'source_sha256':hashlib.sha256(source.encode()).hexdigest(),'source_changes':changes,'process_seconds':90,'separate_PID_records':True}


def load_lifecycle(expected,quiet):
    main,receipt,source=reconstruct_controller(expected,quiet);phase_modules={};bindings=[]
    for case in CASES:
        phase_modules[case],binding=phase_core(source,case,receipt);bindings.append(binding)
    main.scripts=all_scripts
    receipt.update(scope='ONLY two remaining normalization graphs; separate named one-execution invocations, one continuous phone lease',selected_cases=list(CASES),Power_execution_requested=False,phase_source_bindings=bindings,phase_process_seconds=90,maximum_native_seconds_sum=180,expected_raw_output_bytes=1180416,chain_adapter_sha256=sha(Path(__file__)))
    parent=main.Controller
    import phone_paired_prefill_capture as checks
    import phone_value_precision_long_health as health
    class ChainsController(parent):
        def __init__(self,**kwargs):
            kwargs.setdefault('output_root',TRACK/'.local/htp-chain-phone-runs');super().__init__(**kwargs);self.phases=[];self.expected_apks=expected
        def _identity(self):
            self.remote='/data/local/tmp/vibevoice-0031-htp-chain-'+self.result['run_id'];self.result['remote_root']=self.remote;self.result['scope']=receipt['scope']
            return super()._identity()
        def _phase_admission(self,case):
            reply=self._shell('case.'+case+'.current_job_quiescence',checks.QUIET,10);checks.validate_app(reply.stdout,expected,False)
            self._actual_playback('case.'+case+'.actual_user_job_playback_v2')
            reply=self._shell('case.'+case+'.rpc_readiness',health.PROBE,10);observed=health.classify(reply.stdout);self.result.setdefault('case_rpc_preflight',{})[case]=observed
            if observed['explicit_resource_blockers']:raise main.GuardError('RPC_RESOURCE_NOT_READY')
        def _launch_and_wait(self):
            self._telemetry('before');self.result['case_results']=[]
            for case in CASES:
                self._phase_admission(case);module=phase_modules[case];owner=self
                class Phase(module.Controller):
                    def _adb(child,op,args,timeout=15,**kwargs):
                        child._assert_adb_gate();return owner._adb('case.'+child.result['case']+'.'+op,args,timeout,**kwargs)
                    def _telemetry(child,label):return None  # once before/after the whole leased window
                child=Phase(stage=self.stage,transport=self.transport,clock=self.clock);child.lease=self.lease;child.authorized=child.stage_verified=child.slot_claimed=True;child.remote=self.remote;child.out=self.out;child.result={'case':case,'requested_graph_executions':1};self.phases.append(child);self.result['case_results'].append(child.result)
                self.launch_attempted=True
                try:child._launch_and_wait()
                except Exception as error:
                    child.result['error']={'type':type(error).__name__,'message':str(error)};raise
                finally:
                    child.cleaning_up=True
                    try:child.result['process_cleanup']=child._stop_owned()
                    except Exception as error:
                        child.result['process_cleanup']={'all_absent':False,'error':str(error)}
                if not child.result['process_cleanup']['all_absent']:raise main.GuardError('phase process ownership/cleanup unresolved; no next invocation')
                if child.result.get('process_timeout') or child.result.get('process_exit_code')!=0:
                    self.result['process_exit_code']=child.result.get('process_exit_code');self.result['phase_stopped']=case;return
            self.result['process_exit_code']=0
        def _stop_owned(self):
            reports=[]
            for child in self.phases:
                child.cleaning_up=True;report=child._stop_owned();reports.append({'case':child.result['case'],**report})
            return {'all_absent':all(x['all_absent'] for x in reports),'phases':reports,'basis':'independent PID/starttime/executable/NUL probes for separately named phase roles; no lease gap'}
    main.Controller=ChainsController
    old_plan=main.plan
    def plan():
        p=old_plan();p.update(scope=receipt['scope'],graph_count=2,loaded_context_graphs=3,selected_cases=list(CASES),Power_execution_requested=False,separate_invocations=True,continuous_single_phone_lease=True,process_deadline_seconds_each=90,maximum_native_seconds_sum=180,expected_raw_output_bytes=1180416);p.pop('process_deadline_seconds',None);return p
    main.plan=plan
    return main,receipt


def main():
    p=argparse.ArgumentParser(add_help=False);p.add_argument('--expected-app-sha256');p.add_argument('--expected-test-sha256');p.add_argument('--pi-user-job-quiescent',action='store_true');a,rest=p.parse_known_args();expected={k:v for k,v in {'dev.vibevoice.podcast.internal':a.expected_app_sha256,'dev.vibevoice.podcast.internal.test':a.expected_test_sha256}.items() if v}
    if '--execute' in rest and (len(expected)!=2 or not a.pi_user_job_quiescent):p.error('fresh APK/job attestation and Pi slot required')
    module,_=load_lifecycle(expected,a.pi_user_job_quiescent);sys.argv=[sys.argv[0],*rest];return module.main()


if __name__=='__main__':raise SystemExit(main())
