"""Source readiness only: tiny24-layer synthetic I/O, never PTE/PT2 execution."""
from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path
import signal
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

import torch

torch.set_num_threads(1)
EXP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXP / 'tools'))
import compare_qnn_trajectory as trajectory
from qwen_host_guard import supervise
from replay_saved_qdq import artifact, interruption_signals


def cfg():
    return SimpleNamespace(n_layers=24, layer_types=(['linear_attention'] * 3 + ['full_attention']) * 6,
                           linear_num_value_heads=1, linear_num_key_heads=1,
                           linear_key_head_dim=1, linear_value_head_dim=1,
                           linear_conv_kernel_dim=2, n_kv_heads=1, head_dim=1, vocab_size=7)


class FakeRuntime:
    def __init__(self, ids, callback=None):
        self.ids = ids
        self.calls = []
        self.callback = callback

    def forward(self, inputs):
        assert len(inputs) == 51
        token, mask, pos, *states = inputs
        p = int(pos.item()); self.calls.append(p)
        assert token.dtype == pos.dtype == torch.int32
        assert int(token.item()) == self.ids[p]
        expected = torch.full_like(mask, -65504.0)
        expected[..., :p] = 0; expected[..., -1] = 0
        torch.testing.assert_close(mask, expected, rtol=0, atol=0)
        out_a, out_b = [], []
        for layer, kind in enumerate(cfg().layer_types):
            a, b = states[layer], states[24 + layer]
            if kind == 'linear_attention':
                # QNN fake carries +2/+3, deliberately not a QDQ/golden state.
                assert bool((a == 2 * p).all())
                assert bool((b == 3 * p).all())
                out_a.append(a + 2); out_b.append(b + 3)
            else:
                for j in range(p):
                    assert bool((a[..., j] == 1000 + 100 * layer + j).all())
                    assert bool((b[:, :, j, :] == 2000 + 100 * layer + j).all())
                assert bool((a[..., p:] == 0).all())
                assert bool((b[:, :, p:, :] == 0).all())
                out_a.append(torch.full_like(a[..., :1], 1000 + 100 * layer + p))
                out_b.append(torch.full_like(b[:, :, :1, :], 2000 + 100 * layer + p))
        logits = torch.full((1, 1, 7), -10.0)
        logits[..., (self.ids[p] + p) % 7] = p + 5.0
        outputs = [logits, *out_a, *out_b, *[torch.tensor([[[-9999.0]]]) for _ in range(24)]]
        if self.callback:
            return self.callback(p, outputs)
        return outputs


class TrajectoryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.ids = list(struct.unpack('<174i', (EXP / 'protocol/token-ids/short.int32le').read_bytes()))
        self.args = SimpleNamespace(pte=self.root/'fake.pte', params=self.root/'params.json',
                                    token_ids=self.root/'short.int32le', output_dir=self.root/'run',
                                    artifact_manifest=self.root/'artifacts.json', reference_directory=self.root/'ref',
                                    reference_root=self.root, context=4096, max_positions=4, timeout_seconds=300.0,
                                    resume_checkpoint=None, resume_sha256=None)
        self.args.pte.write_bytes(b'synthetic PTE placeholder; never execute')
        self.args.params.write_text('{"synthetic_config":true}')
        self.args.token_ids.write_bytes((EXP / 'protocol/token-ids/short.int32le').read_bytes())
        self.manifest = {'files': {'histogram_pte': artifact(self.args.pte), 'params': artifact(self.args.params),
                                   'input_ids': artifact(self.args.token_ids), 'histogram_qdq': {'sha256': 'synthetic-reference-route', 'bytes': 1}}}
        self.args.artifact_manifest.write_text(json.dumps(self.manifest))
        self.ref_raw = self.args.reference_directory/'raw'; self.ref_raw.mkdir(parents=True)
        torch.save(torch.arange(7, dtype=torch.float32).reshape(1, 1, 7), self.root/'gold.pt')
        self.gold = artifact(self.root/'gold.pt')
        self.rows = [{'position': p, 'input_token': t, 'artifact': self.gold, 'logits': {'argmax': 6, 'finite': True}} for p, t in enumerate(self.ids)]
        self.entries = [{'position': p, 'raw_path': 'gold.pt', 'raw_sha256': self.gold['sha256'], 'raw_bytes': self.gold['bytes']} for p in range(174)]
        self.write_reference()
        self.forbid_runtime = mock.patch.object(trajectory, 'load_runtime', side_effect=AssertionError('Real QNN/model loading forbidden'))
        self.forbid_runtime.start(); self.addCleanup(self.forbid_runtime.stop)
        self.forbid_export = mock.patch.object(torch.export, 'load', side_effect=AssertionError('No model archive loads'))
        self.forbid_export.start(); self.addCleanup(self.forbid_export.stop)

    def write_reference(self):
        journal = self.ref_raw/'progress.jsonl'
        journal.write_text(''.join(json.dumps(row)+'\n' for row in self.rows))
        report = {'status': 'completed', 'evaluated_tokens': 174, 'state_updates_completed': 174,
                  'progress_artifact': artifact(journal), 'input_artifacts': {
                      'qdq_file': self.manifest['files']['histogram_qdq'], 'params': self.manifest['files']['params'],
                      'token_ids': self.manifest['files']['input_ids']}}
        (self.ref_raw/'result.json').write_text(json.dumps(report))
        (self.args.reference_directory/'compression-manifest.json').write_text(json.dumps({'files': self.entries}))

    def run_fake(self, runtime=None, **kwargs):
        runtime = runtime or FakeRuntime(self.ids)
        with contextlib.redirect_stdout(io.StringIO()):
            result = trajectory.run_trajectory(self.args, runtime_loader=lambda *unused: (runtime, cfg()), **kwargs)
        return result

    def result(self):
        return json.loads((self.args.output_dir/'result.json').read_text())

    def rows_at(self, out=None):
        return [json.loads(s) for s in ((out or self.args.output_dir)/'progress.jsonl').read_text().splitlines()]

    def resume(self, result, count):
        self.args.resume_checkpoint = Path(result['latest_checkpoint']['path'])
        self.args.resume_sha256 = result['latest_checkpoint']['sha256']
        self.args.output_dir = self.root/'resumed'
        self.args.max_positions = count

    def test_73_outputs_own_states_position_masks_and_four_position_cap(self):
        runtime = FakeRuntime(self.ids)
        r = self.run_fake(runtime)
        self.assertEqual([0,1,2,3], runtime.calls)
        self.assertEqual('bounded_segment_completed', r['status'])
        self.assertEqual(4, r['comparisons_completed'])
        self.assertFalse(r['full174_in_this_process'])
        self.assertEqual(8, len(self.rows_at()))
        compared = [x for x in self.rows_at() if x['event'] == 'compared']
        for p, row in enumerate(compared):
            self.assertEqual(p, row['position'])
            self.assertEqual(6, row['comparison']['qdq_argmax'])
            self.assertEqual((self.ids[p]+p)%7, row['comparison']['qnn_argmax'])
            outputs = torch.load(row['raw_outputs']['path'], weights_only=True)
            self.assertEqual(73, len(outputs))
            self.assertTrue(all(float(x.item()) == -9999 for x in outputs[49:]))
            h = json.loads(Path(row['checkpoint']['path']).read_text())
            states = torch.load(h['state_artifact']['path'], weights_only=True)
            self.assertEqual(48, len(states))
            self.assertEqual(2*(p+1), float(states[0].item()))
            self.assertTrue(bool((states[24] == 3*(p+1)).all()))
        self.assertIn('OWN evolved state', r['comparison_boundary'])
        self.assertIn('NOT same-state', r['comparison_boundary'])
        self.assertFalse(r['loaded_route_benchmark_reuse_claimed'])

    def test_explicit_resume_matches_uninterrupted_synthetic_state_and_logits(self):
        full = self.run_fake(); full_out = self.args.output_dir
        self.args.output_dir = self.root/'segment'; self.args.max_positions=2
        first = self.run_fake(); self.resume(first, 2)
        runtime = FakeRuntime(self.ids); second = self.run_fake(runtime)
        self.assertEqual([2,3], runtime.calls)
        self.assertEqual(2, second['start_position'])
        self.assertFalse(second['full174_in_this_process'])
        def state(r):
            h=json.loads(Path(r['latest_checkpoint']['path']).read_text())
            return torch.load(h['state_artifact']['path'],weights_only=True)
        for x,y in zip(state(full),state(second)):torch.testing.assert_close(x,y,rtol=0,atol=0)
        a=torch.load(full['latest_raw_outputs']['path'],weights_only=True)
        b=torch.load(second['latest_raw_outputs']['path'],weights_only=True)
        for x,y in zip(a,b):torch.testing.assert_close(x,y,rtol=0,atol=0)
        self.assertTrue((full_out/'result.json').exists())

    def test_existing_attempt_and_symlink_are_not_overwritten(self):
        self.args.output_dir.mkdir(); (self.args.output_dir/'old').write_text('keep')
        with self.assertRaises(FileExistsError):self.run_fake()
        self.assertEqual('keep',(self.args.output_dir/'old').read_text())
        self.args.output_dir=self.root/'link'; self.args.output_dir.symlink_to(self.root/'missing')
        with self.assertRaises(FileExistsError):self.run_fake()
        self.assertTrue(self.args.output_dir.is_symlink())

    def test_invalid_position_and_runtime_limits_rejected(self):
        for count,t in [(0,100),(175,100),(1,0),(1,float('nan')),(1,float('inf')),(1,7201)]:
            with self.subTest(count=count,timeout=t),self.assertRaises(ValueError):trajectory.budget_plan(count,t)
        plan=trajectory.budget_plan(174,7200)
        self.assertEqual(20940,plan['estimated_seconds'])
        self.assertTrue(plan['estimate_exceeds_budget'])

    def test_no_implicit_default_runtime_or_position_budget(self):
        with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):
            trajectory.parser().parse_args(['--pte','x','--params','p','--token-ids','t','--output-dir','o'])

    def test_wrong_pte_stops_before_runtime_loading(self):
        self.args.pte.write_bytes(b'wrong')
        with self.assertRaisesRegex(ValueError,'hash mismatch'):self.run_fake()
        self.assertEqual('preflight',self.result()['phase'])
        self.assertEqual(0,self.result()['graph_calls_returned'])

    def test_wrong_canonical_input_is_rejected(self):
        raw=bytearray(self.args.token_ids.read_bytes());raw[0]^=1;self.args.token_ids.write_bytes(raw)
        with self.assertRaisesRegex(ValueError,'SHA-256'):self.run_fake()

    def test_missing_local_reference_fails_before_expensive_load(self):
        (self.root/'gold.pt').unlink()
        with self.assertRaises(FileNotFoundError):self.run_fake()
        self.assertEqual(0,self.result()['graph_calls_returned'])

    def test_corrupt_local_reference_fails_before_load(self):
        (self.root/'gold.pt').write_bytes(b'bad')
        with self.assertRaisesRegex(ValueError,'hash mismatch'):self.run_fake()
        self.assertEqual('preflight',self.result()['phase'])

    def test_reference_route_and_position_are_not_substitutable(self):
        self.rows[1]['input_token']=-1;self.write_reference()
        with self.assertRaisesRegex(ValueError,'sequence'):self.run_fake()

    def test_different_qdq_reference_is_rejected(self):
        p=self.ref_raw/'result.json';r=json.loads(p.read_text());r['input_artifacts']['qdq_file']['sha256']='another-route';p.write_text(json.dumps(r))
        with self.assertRaisesRegex(ValueError,'different artifact'):self.run_fake()

    def test_resume_requires_exact_header_hash(self):
        self.args.max_positions=1;first=self.run_fake();self.resume(first,1)
        self.args.resume_checkpoint.write_text(self.args.resume_checkpoint.read_text()+' ')
        with self.assertRaisesRegex(ValueError,'Checkpoint metadata'):self.run_fake()

    def test_resume_rejects_wrong_backend_origin_or_consumed_prefix(self):
        self.args.max_positions=1;first=self.run_fake();self.resume(first,1)
        original=json.loads(self.args.resume_checkpoint.read_text())
        for field,value in [('backend_state','qdq_golden_state'),('consumed_prefix_sha256','wrong'),('next_position',-1)]:
            h=dict(original);h[field]=value;self.args.resume_checkpoint.write_text(json.dumps(h));self.args.resume_sha256=artifact(self.args.resume_checkpoint)['sha256']
            self.args.output_dir=self.root/('bad-'+field)
            with self.subTest(field=field),self.assertRaises(ValueError):self.run_fake()

    def test_resume_rejects_changed_pte_binding(self):
        self.args.max_positions=1;first=self.run_fake();self.resume(first,1)
        h=json.loads(self.args.resume_checkpoint.read_text());h['binding']['pte_sha256']='another-pte'
        self.args.resume_checkpoint.write_text(json.dumps(h));self.args.resume_sha256=artifact(self.args.resume_checkpoint)['sha256']
        with self.assertRaisesRegex(ValueError,'route/state-origin'):self.run_fake()

    def test_position_cap_cannot_silently_overrun_reference_after_resume(self):
        self.args.max_positions=1;first=self.run_fake();self.resume(first,174)
        with self.assertRaisesRegex(ValueError,'no silent truncation'):self.run_fake()
        self.assertEqual(0,self.result()['graph_calls_returned'])

    def test_resume_rejects_state_bytes_corruption(self):
        self.args.max_positions=1;first=self.run_fake();self.resume(first,1)
        h=json.loads(self.args.resume_checkpoint.read_text());Path(h['state_artifact']['path']).write_bytes(b'bad')
        with self.assertRaisesRegex(ValueError,'hash mismatch'):self.run_fake()

    def test_resume_rejects_state_geometry_even_with_consistent_hashes(self):
        self.args.max_positions=1;first=self.run_fake();self.resume(first,1)
        h=json.loads(self.args.resume_checkpoint.read_text());p=Path(h['state_artifact']['path'])
        states=torch.load(p,weights_only=True);states[0]=torch.ones(2);torch.save(states,p)
        h['state_artifact']=artifact(p);self.args.resume_checkpoint.write_text(json.dumps(h));self.args.resume_sha256=artifact(self.args.resume_checkpoint)['sha256']
        with self.assertRaisesRegex(ValueError,'shape/dtype'):self.run_fake()

    def test_graph_error_preserves_prior_state_checkpoint_no_retry(self):
        def fail(p,outputs):
            if p==2:raise RuntimeError('synthetic graph failure')
            return outputs
        runtime=FakeRuntime(self.ids,fail)
        with self.assertRaisesRegex(RuntimeError,'synthetic graph'):self.run_fake(runtime)
        r=self.result();self.assertEqual(2,r['comparisons_completed']);self.assertEqual([0,1,2],runtime.calls)
        self.assertIsNotNone(r['latest_checkpoint']);self.assertFalse(r['automatic_retry'])

    def test_invalid_output_count_retains_raw_without_state_claim(self):
        with self.assertRaisesRegex(ValueError,'73 outputs'):
            self.run_fake(FakeRuntime(self.ids,lambda p,x:x[:49]))
        r=self.result();self.assertEqual(1,r['graph_calls_returned']);self.assertEqual(0,r['state_updates_completed'])
        self.assertEqual(49,len(torch.load(r['latest_raw_outputs']['path'],weights_only=True)))

    def test_state_dtype_conversion_not_silently_allowed(self):
        def dtype(p,x):x[1]=x[1].double();return x
        with self.assertRaisesRegex(ValueError,'dtype'):self.run_fake(FakeRuntime(self.ids,dtype))
        self.assertEqual(0,self.result()['state_updates_completed'])

    def test_nonfinite_outputs_are_retained_without_success(self):
        def nonfinite(p,x):x[0][...,0]=float('nan');return x
        with self.assertRaisesRegex(ValueError,'Nonfinite'):self.run_fake(FakeRuntime(self.ids,nonfinite))
        r=self.result();self.assertEqual('error',r['status']);self.assertEqual(0,r['comparisons_completed'])
        self.assertTrue(bool(torch.isnan(torch.load(r['latest_raw_outputs']['path'],weights_only=True)[0]).any()))

    def test_reference_mutation_after_preflight_is_caught_with_work_retained(self):
        def change_gold(p,x):
            torch.save(torch.ones((1,1,7)),self.root/'gold.pt')
            return x
        with self.assertRaisesRegex(ValueError,'changed after preflight'):
            self.run_fake(FakeRuntime(self.ids,change_gold))
        r=self.result();self.assertEqual(1,r['state_updates_completed']);self.assertEqual(0,r['comparisons_completed'])
        self.assertIsNotNone(r['latest_checkpoint'])

    def test_comparison_error_keeps_new_qnn_state_checkpoint(self):
        with mock.patch.object(trajectory,'comparison',side_effect=RuntimeError('synthetic comparison failure')):
            with self.assertRaises(RuntimeError):self.run_fake()
        r=self.result();self.assertEqual(1,r['state_updates_completed']);self.assertEqual(0,r['comparisons_completed'])
        self.assertEqual('state_committed',self.rows_at()[0]['event'])
        self.assertIsNotNone(r['latest_checkpoint'])

    def test_cooperative_timeout_after_forward_preserves_work_and_stops_next_call(self):
        now=[0.0]
        def elapsed(p,x):now[0]=301;return x
        runtime=FakeRuntime(self.ids,elapsed)
        with self.assertRaises(trajectory.BudgetExpired):self.run_fake(runtime,clock=lambda:now[0])
        r=self.result();self.assertEqual('timeout',r['status']);self.assertEqual([0],runtime.calls)
        self.assertEqual(1,r['state_updates_completed']);self.assertEqual(0,r['comparisons_completed'])
        self.assertIsNotNone(r['latest_checkpoint'])

    def test_sigterm_checkpoint_retention_and_restoration(self):
        before=signal.getsignal(signal.SIGTERM)
        def term(p,x):
            if p==1:signal.raise_signal(signal.SIGTERM)
            return x
        with interruption_signals():
            with self.assertRaises(trajectory.ReplayInterrupted):self.run_fake(FakeRuntime(self.ids,term))
        self.assertEqual(before,signal.getsignal(signal.SIGTERM))
        self.assertEqual('interrupted',self.result()['status'])
        self.assertEqual(1,self.result()['state_updates_completed'])


class SupervisorTest(unittest.TestCase):
    def test_independent_deadline_terminates_and_reaps_tiny_child(self):
        with tempfile.TemporaryDirectory() as d:
            result=supervise([sys.executable,'-c','import time;time.sleep(30)'],Path(d),0.15,grace=0.2)
            self.assertEqual('host_timeout',result['reason'])
            self.assertTrue(result['child_reaped']);self.assertFalse(result['automatic_retry'])
            self.assertFalse(Path(f"/proc/{result['child_pid']}").exists())

    def test_ignoring_term_requires_kill_and_is_reaped(self):
        with tempfile.TemporaryDirectory() as d:
            command=[sys.executable,'-c',"import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);print('armed',flush=True);time.sleep(30)"]
            result=supervise(command,Path(d),1.0,grace=0.1)
            self.assertEqual(b'armed\n',(Path(d)/'stdout.log').read_bytes())
            self.assertEqual(-signal.SIGKILL,result['exit_code'])
            self.assertTrue(result['child_reaped'])
            self.assertFalse(Path(f"/proc/{result['child_pid']}").exists())

    def test_stop_file_releases_child_not_sigstop(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'STOP').touch()
            result=supervise([sys.executable,'-c','import time;time.sleep(30)'],p,5,grace=0.2)
            self.assertEqual('coordinator_requested_stop',result['reason'])
            self.assertTrue(result['child_reaped'])

    def test_supervisor_does_not_overwrite_existing_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'stdout.log').write_text('old')
            with self.assertRaises(FileExistsError):supervise(['/nonexistent-qwen-test-executable'],p,1)
            self.assertEqual('old',(p/'stdout.log').read_text())
            self.assertFalse((p/'supervisor.json').exists())

    def test_launch_error_is_recorded_not_success(self):
        with tempfile.TemporaryDirectory() as d:
            result=supervise(['/nonexistent-qwen-test-executable'],Path(d),1)
            self.assertEqual('supervisor_error',result['reason'])
            self.assertIsNone(result['child_pid']);self.assertIsNotNone(result['error'])


if __name__=='__main__':unittest.main()
