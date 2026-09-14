import importlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

TRACK=Path(__file__).resolve().parents[1]/'improvements/0001-long-collapse-speed-quality'
sys.path.insert(0,str(TRACK/'tools'))
c=importlib.import_module('phone_htp_chain_discriminator')


class HTPChainSelectionTests(unittest.TestCase):
    def test_named_selection_never_requests_power(self):
        m,r=c.load_lifecycle({},False);p=m.plan()
        self.assertFalse(p['phone_permission_granted_by_plan']);self.assertFalse(p['Power_execution_requested'])
        self.assertEqual(p['selected_cases'],list(c.CASES));self.assertTrue(p['continuous_single_phone_lease'])
        self.assertEqual(p['maximum_native_seconds_sum'],180);self.assertEqual(p['process_deadline_seconds_each'],90)
        for case in c.CASES:
            args=c.case_argv('/data/local/tmp/SYNTHETIC',case);lists=args[args.index('--input_list')+1].split(',')
            self.assertEqual(lists[0],'__');self.assertEqual(sum(s!='__' for s in lists),1)
            self.assertEqual(args[args.index('--num_inferences')+1],'1');self.assertIn('--shared_buffer',args)
        with self.assertRaises(ValueError):c.case_argv('/data/local/tmp/SYNTHETIC','power_edge')

    def test_actual_host_runner_selected_only_requested_tiny_graph(self):
        path=TRACK/'.local/htp-chain-selection/host-fixture-01/result.json'
        if not path.exists():self.skipTest('retained host fixture unavailable')
        r=json.loads(path.read_text());self.assertEqual(len(r['selected_graph_invocations']),2)
        for x in r['selected_graph_invocations']:
            self.assertEqual(x['runner_exit'],0);self.assertEqual(x['inferences_completed'],1);self.assertFalse(x['Power_executed'])
        self.assertFalse(r['actual_HTP_pole_or_memory_policy_tested'])

    def test_phase_shells_have_separate_records_and_single_selected_list(self):
        remote='/data/local/tmp/SYNTHETIC';scripts=c.all_scripts(remote);self.assertEqual(len(scripts),8)
        with tempfile.TemporaryDirectory() as tmp:
            for name,text in scripts.items():
                p=Path(tmp)/name;p.write_text(text);self.assertEqual(subprocess.run(['/bin/sh','-n',str(p)],capture_output=True).returncode,0)
        for case in c.CASES:
            entry=scripts[case+'-model-entry.sh'];self.assertNotIn('power_edge.inputlist',entry)
            self.assertEqual(sum(line.startswith('printf ') and '.inputlist' in line for line in entry.splitlines()),1)
            self.assertIn(case+'.limits-pre-exec.txt',entry);self.assertIn(case+'.$1.pid',scripts[case+'-control.sh'])

    def test_phase_shell_identity_rejects_other_case_and_extra_empty_arg(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);remote=str(root/'remote');proc=root/'proc/501';proc.mkdir(parents=True)
            (proc/'stat').write_text('501 (fake) '+' '.join(['R']+['0']*18+['10501']+['0']*5)+'\n');(proc/'exe').symlink_to(remote+'/bin/qnn-net-run')
            for case in c.CASES:
                for variant,expected in [(c.case_argv(remote,case),0),(c.case_argv(remote,case)+[''],1),(c.case_argv(remote,next(x for x in c.CASES if x!=case)),1)]:
                    (proc/'cmdline').write_bytes(b'\0'.join(x.encode() for x in variant)+b'\0')
                    text=c.phase_common(remote,case).replace('/proc/',str(root/'proc')+'/')+'\nrole_matches model 501 10501\n'
                    code=subprocess.run(['/bin/sh','-c',text],capture_output=True).returncode
                    self.assertEqual(code,expected)

    def exercise(self,first='normal',second='normal',second_busy=False,pull_failure=False,bad_second_argv=False,postflight_failure=False):
        import test_phone_return_controller as fakes
        expected={'dev.vibevoice.podcast.internal':'a'*64,'dev.vibevoice.podcast.internal.test':'b'*64};module,_=c.load_lifecycle(expected,True)
        app=('APK\tdev.vibevoice.podcast.internal\t'+'a'*64+'\nAPK\tdev.vibevoice.podcast.internal.test\t'+'b'*64+'\nPID\tdev.vibevoice.podcast.internal:generation\t\nPID\tdev.vibevoice.podcast.internal.test\t\n').encode();quiet=b'PID\tdev.vibevoice.podcast.internal:generation\t\nPID\tdev.vibevoice.podcast.internal.test\t\n'
        class PhaseFake(fakes.FakeAdb):
            def reply(self,op):
                if op=='pid.model.probe' and not self.dead['model']:
                    owner=self.controller;pid=self.pids['model'];born=self.starts['model'];fields=['R']+['0']*18+[born]+['0']*5;exe=owner.remote+'/bin/qnn-net-run';args=c.case_argv(owner.remote,owner.result['case'])
                    if bad_second_argv and owner.result['case']==c.CASES[1]:args.append('')
                    return module.Reply(0,(f'{pid} (fake) '+' '.join(fields)+'\n\nEXE\n'+exe+'\nCMD\n').encode()+b'\0'.join(x.encode() for x in args)+b'\0')
                return super().reply(op)
        class Transport(fakes.FakeAdb):
            def __init__(self):super().__init__();self.case_fakes={}
            def reply(self,op):
                if op in ['preflight.current_APKs_and_generation','postflight.current_APKs_and_generation']:return module.Reply(0,app)
                if op=='stage.manifest_hashes':return module.Reply(0,f'{module.DIGEST}  frozen-manifest.json\n{module.sha(self.controller.stage/"SHA256SUMS")}  SHA256SUMS\n'.encode())
                if op=='stage.payload_hashes':return module.Reply(0,b'bin/qnn-net-run: OK\nfrozen-manifest.json: OK\n')
                if 'actual_user_job_playback_v2' in op:return module.Reply(0,b'PLAYBACK_GUARD_V2 main=absent verdict=quiescent\n')
                if op.startswith('case.'):
                    _,case,inner=op.split('.',2)
                    if inner=='current_job_quiescence':
                        return module.Reply(0,quiet.replace(b':generation\t\n',b':generation\t123\n') if second_busy and case==c.CASES[1] else quiet)
                    if inner=='rpc_readiness':return module.Reply(0,b'')
                    child=next(p for p in self.controller.phases if p.result['case']==case)
                    if case not in self.case_fakes:
                        fake=PhaseFake();fake.mode=first if case==c.CASES[0] else second;shift=0 if case==c.CASES[0] else 10;fake.pids={k:v+shift for k,v in fake.pids.items()};fake.starts={k:str(int(v)+shift) for k,v in fake.starts.items()};self.case_fakes[case]=fake
                    fake=self.case_fakes[case];fake.controller=child;return fake.reply(inner)
                return super().reply(op)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);stage=root/'stage';stage.mkdir();(stage/'SHA256SUMS').write_text('fake');fake=Transport();clock=fakes.FakeClock();clock.fast=first=='hold' or second=='hold'
            if pull_failure:fake.fail['raw.pull']=module.Reply(1,stderr=b'fake partial capture')
            if postflight_failure:fake.fail['postflight.current_APKs_and_generation']=module.Reply(1,stderr=b'fake postflight unavailable')
            owner=module.Controller(stage=stage,output_root=root/'runs',slot_root=root/'slots',lock_path=root/'phone.lock',transport=fake,clock=clock,stage_verifier=lambda *_:{'files':{'bin/qnn-net-run':{}}});fake.controller=clock.controller=owner
            result=owner.run(execute=True,reviewed_digest=module.DIGEST,pi_slot='fake-window',run_id='fake-two-cases')
            self.assertTrue(result['phone_lock_released']);self.assertTrue(all(p.lease is owner.lease for p in owner.phases))
            self.assertEqual(len(list((root/'slots').glob('*.json'))),1)
            return result,[op for op,_,_ in fake.calls]

    def test_two_processes_one_lease_then_raw_pull_postflight_cleanup(self):
        r,ops=self.exercise();self.assertEqual(r['process_exit_code'],0);self.assertEqual(len(r['case_results']),2)
        self.assertTrue(r['postflight_app_identity']['verified']);self.assertEqual(r['cleanup'],'verified_absent')
        launches=[op for op in ops if op.endswith('.process.launch')];self.assertEqual(launches,['case.'+x+'.process.launch' for x in c.CASES])
        self.assertEqual(ops.count('raw.pull'),1);self.assertLess(ops.index('raw.pull'),ops.index('cleanup.remove'))
        self.assertLess(ops.index('cleanup.absence'),ops.index('postflight.current_APKs_and_generation'))
        first_last=max(i for i,op in enumerate(ops[:ops.index(launches[1])]) if op.startswith('case.'+c.CASES[0]+'.pid.'))
        self.assertLess(first_last,ops.index(launches[1]))

    def test_first_failure_or_between_case_job_blocks_second_without_retry(self):
        for kwargs in [{'first':'exit7'},{'second_busy':True}]:
            r,ops=self.exercise(**kwargs);self.assertEqual(sum(op.endswith('.process.launch') for op in ops),1)
            self.assertTrue(r['raw_pull_completed']);self.assertTrue(r['postflight_app_identity']['verified'])

    def test_partial_pull_retains_root_and_second_failure_preserves_first(self):
        r,ops=self.exercise(pull_failure=True);self.assertFalse(r['raw_pull_completed']);self.assertNotIn('cleanup.remove',ops)
        r,ops=self.exercise(second='exit7');self.assertEqual([x['process_exit_code'] for x in r['case_results']],[0,7]);self.assertEqual(r['process_exit_code'],7)

    def test_postflight_failure_retains_completed_cases_and_cleanup(self):
        r,ops=self.exercise(postflight_failure=True);self.assertEqual([x['process_exit_code'] for x in r['case_results']],[0,0])
        self.assertTrue(r['raw_pull_completed']);self.assertEqual(r['cleanup'],'verified_absent');self.assertFalse(r['postflight_app_identity']['verified'])
        self.assertEqual(ops.count('postflight.current_APKs_and_generation'),1)

    def test_phase_PID_and_argv_guards_never_signal_unknown_identity(self):
        r,ops=self.exercise(first='hold');self.assertEqual(len(r['case_results']),1);self.assertTrue(r['case_results'][0]['native_process_observed'])
        self.assertTrue(any(op.startswith('case.normalization_chain.signal.model.') for op in ops))
        r,ops=self.exercise(second='hold',bad_second_argv=True);self.assertEqual(r['cleanup'],'unknown_process_state_remote_root_retained')
        self.assertFalse(any(op.startswith('case.normalization_exposed.signal.') for op in ops))


if __name__=='__main__':unittest.main()
