"""Tiny saved tensors and injected backends only; no model/PTE/PT2 execution."""
from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import signal
import sys
from types import SimpleNamespace
import unittest
from unittest import mock

import torch

torch.set_num_threads(1)
EXP = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(EXP/'tools'), str(EXP/'tests')]
import controlled_position1 as control
import test_qnn_trajectory as fixtures
from diagnose_quantized_output import make_state_templates
from replay_saved_qdq import artifact, interruption_signals


class ControlledTest(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.TrajectoryTest()
        self.fixture.setUp(); self.addCleanup(self.fixture.doCleanups)
        self.root, self.ids = self.fixture.root, self.fixture.ids
        self.config = fixtures.cfg()
        self.fixture.args.params.write_text(json.dumps(vars(self.config)))
        qdq = self.root/'fake.pt2'; qdq.write_bytes(b'synthetic graph placeholder; NEVER load')
        states = make_state_templates(self.config,4096)
        mask = torch.full((1,1,1,4096),-65504.);mask[..., -1]=0
        outputs = fixtures.FakeRuntime(self.ids).forward([torch.tensor([[self.ids[0]]],dtype=torch.int32),mask,torch.tensor([[0]],dtype=torch.int32),*states])
        outputs[0] = torch.arange(7,dtype=torch.float32).reshape(1,1,7)
        self.source_outputs = outputs
        saved = self.root/'saved-p0.pt';torch.save(outputs,saved)
        def entry(p):
            value=artifact(p);value['path']=str(p.relative_to(self.root));return value
        m={'files':{'histogram_pte':entry(self.fixture.args.pte),'histogram_qdq':entry(qdq),
                    'params':entry(self.fixture.args.params),'input_ids':entry(self.fixture.args.token_ids),
                    'histogram_qdq_outputs':entry(saved)}}
        self.fixture.manifest=m;self.fixture.write_reference()
        source=self.root/'source';(source/'current/02-qdq').mkdir(parents=True)
        (source/'artifact-manifest.json').write_text(json.dumps(m))
        (source/'current/02-qdq/command.json').write_text(json.dumps(['python','localize_qnn_first_token.py','--phase','qdq','--diagnostic-hidden-states','--qdq-file',str(qdq),'--params',str(self.fixture.args.params),'--token-ids',str(self.fixture.args.token_ids)]))
        self.prep_args=SimpleNamespace(source_evidence=source,reference_directory=self.fixture.args.reference_directory,artifact_root=self.root,output_dir=self.root/'pack')
        self.forbid=mock.patch.object(control,'load_backend',side_effect=AssertionError('No real backend/model load allowed'))
        self.forbid.start();self.addCleanup(self.forbid.stop)

    def prepare(self):
        return control.prepare(self.prep_args)

    def call_args(self, prepared, backend='qdq', name='call'):
        return SimpleNamespace(backend=backend,pack_header=Path(prepared['header']['path']),
                               pack_header_sha256=prepared['header']['sha256'],artifact_root=self.root,
                               output_dir=self.root/name,timeout_seconds=300.,qdq_control_result=None,qdq_control_sha256=None)

    def fake_loader(self, args, logits=None, mutate=False, exception=None, after=None):
        calls=[]
        expected=torch.load(json.loads(args.pack_header.read_text())['input_pack']['path'],weights_only=True)
        def call(inputs):
            calls.append(int(inputs[2].item()))
            self.assertEqual(51,len(inputs));self.assertEqual(1,int(inputs[2].item()))
            self.assertEqual(self.ids[1],int(inputs[0].item()))
            for a,b in zip(expected,inputs):torch.testing.assert_close(a,b,rtol=0,atol=0)
            if exception:raise exception
            output=[x.clone() for x in self.source_outputs]
            output[0]=(torch.arange(7,dtype=torch.float32).reshape(1,1,7)+2 if logits is None else logits.clone())
            if mutate:inputs[3].add_(1)
            if after:after(output)
            return output
        class Runtime:
            def __call__(self,*inputs):return call(list(inputs))
            def forward(self,inputs):return call(inputs)
        return lambda *unused:(Runtime(),self.config),calls

    def run_fake(self,args,**kwargs):
        loader,calls=self.fake_loader(args,**kwargs)
        r=control.run_control(args,runtime_loader=loader)
        return r,calls

    def test_materialization_has_explicit_qdq_origin_not_resume(self):
        r=self.prepare();h=json.loads(Path(r['header']['path']).read_text())
        self.assertFalse(r['model_or_qnn_execution_performed'])
        self.assertEqual(control.KIND,h['kind'])
        self.assertEqual('qdq_after_position0_not_qnn_resume',h['state_origin'])
        self.assertNotIn('backend_state',h)
        x=torch.load(h['input_pack']['path'],weights_only=True)
        self.assertEqual(51,len(x));self.assertEqual(self.ids[1],int(x[0].item()));self.assertEqual(1,int(x[2].item()))
        self.assertEqual([0,4095],torch.where(x[1].reshape(-1)==0)[0].tolist())
        self.assertEqual(h['input_values_sha256'],control.values_digest(x))
        self.assertTrue(h['lineage']['position0_logits_bit_identical_to_full_replay'])
        self.assertFalse(h['lineage']['full_replay_state_bytes_retained'])
        for layer,kind in enumerate(self.config.layer_types):
            if kind=='linear_attention':
                torch.testing.assert_close(x[3+layer],self.source_outputs[1+layer],rtol=0,atol=0)
                torch.testing.assert_close(x[27+layer],self.source_outputs[25+layer],rtol=0,atol=0)
            else:
                torch.testing.assert_close(x[3+layer][...,0],self.source_outputs[1+layer][...,0],rtol=0,atol=0)
                self.assertEqual(0,int(x[3+layer][...,1:].count_nonzero()))

    def test_independent_materialization_verifier_checks_48_copied_states(self):
        r=self.prepare()
        v=control.verify_materialization(Path(r['header']['path']),r['header']['sha256'],self.root)
        self.assertEqual(48,v['state_tensors_checked']);self.assertEqual(51,v['input_tensors_checked'])
        self.assertTrue(v['state_materialization_matches_saved_outputs'])
        self.assertFalse(v['model_or_qnn_execution_performed'])
        self.assertFalse(v['full_replay_state_byte_equality_proved'])

    def test_materialization_verifier_rejects_wrong_state_even_if_rehashed(self):
        r=self.prepare();p=Path(r['header']['path']);h=json.loads(p.read_text());state_path=Path(h['input_pack']['path'])
        x=torch.load(state_path,weights_only=True);x[3].add_(0.25);torch.save(x,state_path)
        h['input_pack']=artifact(state_path);h['input_values_sha256']=control.values_digest(x);p.write_text(json.dumps(h))
        with self.assertRaisesRegex(ValueError,'differs from source'):
            control.verify_materialization(p,artifact(p)['sha256'],self.root)

    def test_prepare_no_overwrite(self):
        self.prepare()
        with self.assertRaises(FileExistsError):self.prepare()

    def test_prepare_detects_changed_source_output(self):
        (self.root/'saved-p0.pt').write_bytes(b'corrupt')
        with self.assertRaisesRegex(ValueError,'changed after preflight'):self.prepare()

    def test_prepare_requires_qdq_origin_command(self):
        p=self.prep_args.source_evidence/'current/02-qdq/command.json';c=json.loads(p.read_text());c[c.index('--phase')+1]='qnn';p.write_text(json.dumps(c))
        with self.assertRaisesRegex(ValueError,'position0 QDQ'):self.prepare()

    def test_one_qdq_validation_call_is_not_a_174_replay(self):
        args=self.call_args(self.prepare());r,calls=self.run_fake(args)
        self.assertEqual([1],calls);self.assertEqual(1,r['graph_calls_returned'])
        self.assertEqual('qdq',r['backend']);self.assertFalse(r['exact_same_pack_qdq_reference_used'])
        self.assertFalse(r['historical_qdq_logits_bit_identical'])
        self.assertFalse(r['resume']);self.assertFalse(r['automatic_follow_on'])
        self.assertFalse(r['physical_execution'])
        self.assertEqual(6,r['logits']['argmax'])

    def test_qnn_without_validation_retains_lineage_assumption(self):
        args=self.call_args(self.prepare(),'qnn');r,calls=self.run_fake(args)
        self.assertEqual([1],calls)
        self.assertFalse(r['exact_same_pack_qdq_reference_used'])
        self.assertIn('not established',r['interpretation'])

    def test_optional_qdq_then_separate_qnn_use_identical_pack(self):
        prepared=self.prepare();a=self.call_args(prepared,name='qdq')
        qdq,qdq_calls=self.run_fake(a)
        b=self.call_args(prepared,'qnn','qnn');b.qdq_control_result=a.output_dir/'result.json';b.qdq_control_sha256=artifact(b.qdq_control_result)['sha256']
        logits=torch.tensor([[[0.,1.,2.,30.,4.,5.,6.]]])
        qnn,qnn_calls=self.run_fake(b,logits=logits)
        self.assertEqual([1],qdq_calls);self.assertEqual([1],qnn_calls)
        self.assertTrue(qnn['exact_same_pack_qdq_reference_used'])
        self.assertEqual(qdq['submitted_input_values_sha256'],qnn['submitted_input_values_sha256'])
        self.assertEqual(3,qnn['same_pack_qdq_comparison']['actual_argmax'])
        self.assertEqual(6,qnn['same_pack_qdq_comparison']['reference_argmax'])
        self.assertFalse(qnn['input_mutation_observed'])

    def test_paired_result_must_have_reviewed_digest(self):
        prepared=self.prepare();a=self.call_args(prepared);self.run_fake(a)
        b=self.call_args(prepared,'qnn','second');b.qdq_control_result=a.output_dir/'result.json';b.qdq_control_sha256='bad'
        with self.assertRaisesRegex(ValueError,'digest/backend'):self.run_fake(b)

    def test_paired_result_cannot_substitute_another_pack(self):
        prepared=self.prepare();a=self.call_args(prepared);self.run_fake(a)
        p=a.output_dir/'result.json';r=json.loads(p.read_text());r['submitted_input_values_sha256']='another-pack';p.write_text(json.dumps(r))
        b=self.call_args(prepared,'qnn','second');b.qdq_control_result=p;b.qdq_control_sha256=artifact(p)['sha256']
        with self.assertRaisesRegex(ValueError,'identical pack'):self.run_fake(b)

    def test_own_qnn_checkpoint_cannot_masquerade_as_control_pack(self):
        args=self.call_args(self.prepare());h=json.loads(args.pack_header.read_text());h['state_origin']='qnn_x86_own_propagated_state';args.pack_header.write_text(json.dumps(h));args.pack_header_sha256=artifact(args.pack_header)['sha256']
        with self.assertRaisesRegex(ValueError,'QDQ-origin'):self.run_fake(args)

    def test_header_hash_and_pack_value_changes_rejected(self):
        args=self.call_args(self.prepare());args.pack_header_sha256='wrong'
        with self.assertRaisesRegex(ValueError,'pack-header'):self.run_fake(args)

    def test_wrong_position_and_mask_rejected_before_call(self):
        prepared=self.prepare();args=self.call_args(prepared);h=json.loads(args.pack_header.read_text());p=Path(h['input_pack']['path']);x=torch.load(p,weights_only=True);x[2][0,0]=2;torch.save(x,p);h['input_pack']=artifact(p);h['input_values_sha256']=control.values_digest(x);args.pack_header.write_text(json.dumps(h));args.pack_header_sha256=artifact(args.pack_header)['sha256']
        with self.assertRaisesRegex(ValueError,'only canonical input position1'):self.run_fake(args)

    def test_bad_mask_even_with_consistent_hashes_rejected(self):
        prepared=self.prepare();args=self.call_args(prepared);h=json.loads(args.pack_header.read_text());p=Path(h['input_pack']['path']);x=torch.load(p,weights_only=True);x[1][...,1]=0;torch.save(x,p);h['input_pack']=artifact(p);h['input_values_sha256']=control.values_digest(x);args.pack_header.write_text(json.dumps(h));args.pack_header_sha256=artifact(args.pack_header)['sha256']
        with self.assertRaisesRegex(ValueError,'mask'):self.run_fake(args)

    def test_model_identity_mismatch_prevents_call(self):
        args=self.call_args(self.prepare());(self.root/'fake.pt2').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'Artifact bytes/hash mismatch'):self.run_fake(args)
        self.assertEqual(0,json.loads((args.output_dir/'result.json').read_text())['graph_calls_returned'])

    def test_backend_error_retained_without_retry(self):
        args=self.call_args(self.prepare(),'qnn')
        loader,calls=self.fake_loader(args,exception=RuntimeError('synthetic backend failure'))
        with self.assertRaises(RuntimeError):control.run_control(args,runtime_loader=loader)
        self.assertEqual([1],calls)
        r=json.loads((args.output_dir/'result.json').read_text());self.assertEqual('error',r['status']);self.assertEqual(0,r['graph_calls_returned'])

    def test_input_mutation_is_detected_after_raw_capture(self):
        args=self.call_args(self.prepare(),'qnn')
        with self.assertRaisesRegex(ValueError,'mutated'):self.run_fake(args,mutate=True)
        r=json.loads((args.output_dir/'result.json').read_text())
        self.assertEqual(1,r['graph_calls_returned']);self.assertTrue(r['input_mutation_observed'])
        self.assertEqual(73,len(torch.load(r['raw_outputs']['path'],weights_only=True)))

    def test_nonfinite_raw_retained(self):
        args=self.call_args(self.prepare());logits=torch.zeros((1,1,7));logits[...,0]=float('nan')
        with self.assertRaisesRegex(ValueError,'Nonfinite'):self.run_fake(args,logits=logits)
        r=json.loads((args.output_dir/'result.json').read_text());self.assertIsNone(r['logits']['argmax'])
        self.assertTrue(bool(torch.isnan(torch.load(r['raw_outputs']['path'],weights_only=True)[0]).any()))

    def test_cooperative_timeout_preserves_returned_output(self):
        args=self.call_args(self.prepare());now=[0.]
        loader,calls=self.fake_loader(args,after=lambda outputs:now.__setitem__(0,301.))
        with self.assertRaises(control.BudgetExpired):control.run_control(args,runtime_loader=loader,clock=lambda:now[0])
        r=json.loads((args.output_dir/'result.json').read_text());self.assertEqual('timeout',r['status']);self.assertEqual(1,r['graph_calls_returned']);self.assertEqual([1],calls)

    def test_signal_records_interruption(self):
        args=self.call_args(self.prepare());loader,calls=self.fake_loader(args,after=lambda outputs:signal.raise_signal(signal.SIGTERM))
        with interruption_signals():
            with self.assertRaises(control.ReplayInterrupted):control.run_control(args,runtime_loader=loader)
        self.assertEqual('interrupted',json.loads((args.output_dir/'result.json').read_text())['status'])
        self.assertEqual([1],calls)

    def test_existing_call_directory_cannot_be_overwritten(self):
        args=self.call_args(self.prepare());self.run_fake(args);old=(args.output_dir/'result.json').read_bytes()
        with self.assertRaises(FileExistsError):self.run_fake(args)
        self.assertEqual(old,(args.output_dir/'result.json').read_bytes())

    def test_vector_decomposition_does_not_mutate_originals_or_add_cosines(self):
        values=[torch.tensor([float(i),float(i+1),float(2*i)]) for i in (2,4,7,9)]
        originals=[x.clone() for x in values];v=control.difference_vectors(*values)
        self.assertTrue(torch.equal(v['current_call']+v['qnn_state_effect']+v['historical_reference_shift'],v['observed_own_trajectory_difference']))
        self.assertEqual(0,int(v['rounding_residual'].count_nonzero()))
        self.assertTrue(all('cosine' not in key for key in v))
        for a,b in zip(values,originals):self.assertTrue(torch.equal(a,b))


if __name__=='__main__':unittest.main()
