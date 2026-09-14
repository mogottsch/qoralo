import copy
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

TRACK=Path(__file__).resolve().parents[1]/'improvements/0001-long-collapse-speed-quality'
sys.path.insert(0,str(TRACK/'tools'))
p=importlib.import_module('phone_htp_power_discriminator')


class HTPPowerDiscriminatorTests(unittest.TestCase):
    def test_plan_is_three_tiny_graphs_no_permission_or_CPU_fallback(self):
        m,r=p.load_lifecycle({},False);plan=m.plan()
        self.assertFalse(plan['phone_permission_granted_by_plan']);self.assertEqual(plan['adb_calls'],0)
        self.assertEqual(plan['graph_count'],3);self.assertEqual(plan['process_deadline_seconds'],90)
        self.assertFalse(plan['long_script']);self.assertFalse(plan['CPU_fallback_available_in_bundle'])
        self.assertEqual(plan['phone_address_space_limit_bytes'],12884901888)
        self.assertIn('libQnnHtp_sha256',r);self.assertNotIn('libGenie_sha256',r)
        args=p.argv('/data/local/tmp/SYNTHETIC');self.assertEqual(len(args),18)
        self.assertIn('--shared_buffer',args);self.assertNotIn('--io_tensor_mem_handle_type',args);self.assertNotIn('dma_buf',args)

    def test_real_host_parser_rejects_old_mutual_flags_before_backend(self):
        root=TRACK/'.local/htp-power-argv/parse-01'
        if not (root/'result.json').exists():self.skipTest('retained parser fixture unavailable')
        r=json.loads((root/'result.json').read_text());old=r['cases']['old-mutually-exclusive'];new=r['cases']['corrected-DMA-only']
        self.assertTrue(old['mutual_exclusion_error']);self.assertEqual(old['argv_fields'],20)
        self.assertFalse(new['mutual_exclusion_error']);self.assertEqual(new['argv_fields'],19)
        self.assertIn('Unable to load backend',(root/'corrected-DMA-only.stdout').read_text())
        self.assertTrue(r['backend_context_inputs_deliberately_nonexistent']);self.assertFalse(r['model_or_phone_executed'])

    def test_legacy_shared_buffer_actual_runner_admission_without_graph(self):
        root=TRACK/'.local/htp-rpc-invocation/probe-01'
        if not (root/'result.json').exists():self.skipTest('retained source-bound runner probe unavailable')
        r=json.loads((root/'result.json').read_text());cmd=json.loads((root/'command.json').read_text())['argv']
        self.assertEqual(r['argv_fields'],18);self.assertIn('--shared_buffer',cmd);self.assertNotIn('--io_tensor_mem_handle_type',cmd)
        self.assertIn('Inferences will run in sync mode',(root/'stdout').read_text())
        self.assertIn('Failed to open input file',(root/'stdout').read_text())
        self.assertNotIn('does not support property',(root/'stderr').read_text());self.assertTrue(r['context_deliberately_missing']);self.assertFalse(r['full_model_or_phone_executed'])

    def test_frozen_payload_and_compiled_raw_IO_sizes(self):
        manifest=p.verify_stage(p.STAGE,p.DIGEST)
        self.assertEqual(len(manifest['files']),9);self.assertEqual(manifest['expected_output_bytes'],1180672)
        self.assertEqual([len(g['outputs']) for g in manifest['graphs']],[1,1,5])
        self.assertEqual(manifest['backend_id'],6);self.assertEqual(manifest['soc_model'],43)
        self.assertFalse(manifest['phone_permission_granted'])
        with self.assertRaises(ValueError):p.verify_stage(p.STAGE,'wrong')

    def test_expected_formulas_do_not_guess_pole_integer_outputs(self):
        prep=importlib.import_module('prepare_htp_power_discriminator');manifest=p.verify_stage(p.STAGE,p.DIGEST)
        cases=[prep.expected_cases(g['authored']) for g in manifest['graphs']]
        self.assertIsNone(cases[0]['rows'][0]['expected_native_code'])
        self.assertEqual(cases[0]['rows'][1]['finite_nearest_even_code'],62816)
        self.assertIsNone(cases[1]['rows'][0]['literal_normalized_code'])
        self.assertEqual(cases[1]['rows'][0]['contrasting_fused_RMS_formula_code'],31507)
        self.assertTrue(cases[2]['exposed_intermediates_change_fusion_opportunity'])

    def test_compiled_context_and_actual_DLC_operator_attribute_gate(self):
        prep=importlib.import_module('prepare_htp_power_discriminator');root=TRACK/'.local/htp-power-discriminator'
        if not (root/'post-inspection-02/graphs.json').exists():self.skipTest('private metadata unavailable')
        graphs=json.loads((root/'post-inspection-02/graphs.json').read_text());context=json.loads((root/'prepare-02/context-info.json').read_text())
        self.assertTrue(prep.verify_context_contract(context,graphs)['native_IO_grids_shapes_dtypes_preserved'])
        self.assertEqual(graphs[0]['operators'][0]['attrs'],{'operation':16})
        self.assertEqual([o['attrs'] for o in graphs[1]['operators']],[{'operation':13},{'axes':[2],'keep_dims':True,'reduce_type':'ReduceMean'},{'operation':0},{'operation':16},{'operation':13}])
        changed=copy.deepcopy(context);changed['info']['graphs'][0]['info']['graphOutputs'][0]['info']['quantizeParams']['scaleOffset']['scale']=1
        with self.assertRaises(ValueError):prep.verify_context_contract(changed,graphs)

    def test_shell_syntax_and_exact_NUL_argv_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);remote=str(root/'remote');proc=root/'proc/501';proc.mkdir(parents=True)
            for name,text in p.scripts(remote).items():
                path=root/name;path.write_text(text);self.assertEqual(subprocess.run(['/bin/sh','-n',str(path)],capture_output=True).returncode,0)
            fields=['R']+['0']*18+['10501']+['0']*5;(proc/'stat').write_text('501 (fake comm) '+' '.join(fields)+'\n')
            (proc/'exe').symlink_to(remote+'/bin/qnn-net-run');args=p.argv(remote)
            def check(argv):
                (proc/'cmdline').write_bytes(b'\0'.join(s.encode() for s in argv)+b'\0')
                text=p.common(remote).replace('/proc/',str(root/'proc')+'/')+'\nrole_matches model 501 10501\n'
                return subprocess.run(['/bin/sh','-c',text],capture_output=True).returncode
            self.assertEqual(check(args),0);self.assertNotEqual(check(args+['']),0)
            old=args.copy();old.remove('--shared_buffer');old.extend(['--io_tensor_mem_handle_type','dma_buf']);self.assertNotEqual(check(old),0)
            self.assertNotEqual(check(args+['--io_tensor_mem_handle_type','dma_buf']),0)
            bad=args.copy();bad[bad.index('--num_inferences')+1]='2';self.assertNotEqual(check(bad),0)

    def exercise(self,mode='normal',capture_failure=False,postflight_failure=False,bad_argv=False):
        import test_phone_return_controller as fakes
        expected={'dev.vibevoice.podcast.internal':'a'*64,'dev.vibevoice.podcast.internal.test':'b'*64};m,_=p.load_lifecycle(expected,True)
        app=('APK\tdev.vibevoice.podcast.internal\t'+'a'*64+'\nAPK\tdev.vibevoice.podcast.internal.test\t'+'b'*64+'\nPID\tdev.vibevoice.podcast.internal:generation\t\nPID\tdev.vibevoice.podcast.internal.test\t\n').encode();quiet=b'PID\tdev.vibevoice.podcast.internal:generation\t\nPID\tdev.vibevoice.podcast.internal.test\t\n'
        class Fake(fakes.FakeAdb):
            def reply(self,op):
                if op in ['preflight.current_APKs_and_generation','postflight.current_APKs_and_generation']:return m.Reply(0,app)
                if op=='preflight.current_job_quiescence':return m.Reply(0,quiet)
                if 'actual_user_job_playback_v2' in op:return m.Reply(0,b'PLAYBACK_GUARD_V2 main=absent verdict=quiescent\n')
                if op=='preflight.rpc_readiness':return m.Reply(0,b'')
                if op=='stage.manifest_hashes':return m.Reply(0,f'{m.DIGEST}  frozen-manifest.json\n{m.sha(self.controller.stage/"SHA256SUMS")}  SHA256SUMS\n'.encode())
                if op=='stage.payload_hashes':return m.Reply(0,b'bin/qnn-net-run: OK\nfrozen-manifest.json: OK\n')
                if op=='pid.model.probe' and not self.dead['model']:
                    pid=self.pids['model'];born=self.starts['model'];fields=['R']+['0']*18+[born]+['0']*5;exe=self.controller.remote+'/bin/qnn-net-run';args=p.argv(self.controller.remote)
                    if bad_argv:args.append('')
                    return m.Reply(0,(f'{pid} (fake) '+' '.join(fields)+'\n\nEXE\n'+exe+'\nCMD\n').encode()+b'\0'.join(s.encode() for s in args)+b'\0')
                return super().reply(op)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);stage=root/'stage';stage.mkdir();(stage/'SHA256SUMS').write_text('fake');fake=Fake();fake.mode=mode;clock=fakes.FakeClock();clock.fast=mode=='hold'
            if capture_failure:fake.fail['raw.pull']=m.Reply(1,stderr=b'fake raw pull failure')
            if postflight_failure:fake.fail['postflight.current_APKs_and_generation']=m.Reply(1,stderr=b'fake postflight failure')
            c=m.Controller(stage=stage,output_root=root/'runs',slot_root=root/'slots',lock_path=root/'phone.lock',transport=fake,clock=clock,stage_verifier=lambda *_:{'files':{'bin/qnn-net-run':{}}});fake.controller=clock.controller=c
            result=c.run(execute=True,reviewed_digest=m.DIGEST,pi_slot='fake-slot',run_id='fake-run');self.assertTrue(result['phone_lock_released']);return result,[op for op,_,_ in fake.calls]

    def test_actual_lifecycle_success_and_native_failure_have_postflight_raw_first_cleanup(self):
        for mode,code in [('normal',0),('exit7',7)]:
            x,ops=self.exercise(mode);self.assertEqual(x['process_exit_code'],code);self.assertTrue(x['postflight_app_identity']['verified'])
            self.assertEqual(x['cleanup'],'verified_absent');self.assertLess(ops.index('raw.pull'),ops.index('cleanup.remove'))
            self.assertLess(ops.index('cleanup.absence'),ops.index('postflight.current_APKs_and_generation'))

    def test_actual_lifecycle_partial_pull_and_postflight_failure_preserve_evidence(self):
        x,ops=self.exercise(capture_failure=True);self.assertFalse(x['raw_pull_completed']);self.assertNotIn('cleanup.remove',ops)
        self.assertIn('retained_remote_root',x);self.assertTrue(x['postflight_app_identity']['verified'])
        x,ops=self.exercise(postflight_failure=True);self.assertTrue(x['raw_pull_completed']);self.assertEqual(x['cleanup'],'verified_absent');self.assertFalse(x['postflight_app_identity']['verified'])

    def test_exact_live_native_argv_and_unknown_identity_signal_boundary(self):
        x,ops=self.exercise(mode='hold');self.assertTrue(x['native_process_observed']);self.assertEqual(x['process_timeout'],'host_90s_deadline')
        self.assertTrue(any(op.startswith('signal.model.') for op in ops))
        x,ops=self.exercise(mode='hold',bad_argv=True);self.assertEqual(x['cleanup'],'unknown_process_state_remote_root_retained')
        self.assertFalse(any(op.startswith('signal.') for op in ops))


if __name__=='__main__':unittest.main()
