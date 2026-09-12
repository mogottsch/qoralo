import importlib
import json
import struct
from pathlib import Path
import sys
import unittest

TRACK=Path(__file__).resolve().parents[1]/'improvements/0001-long-collapse-speed-quality'
sys.path.insert(0,str(TRACK/'tools'))
a=importlib.import_module('analyze_native_qat_cost')


def begin(i,op,parent=None,depth=0,args=None,mono=0):
    return {'event':'begin','call':i,'operation':op,'parent':parent,'depth':depth,'thread':1,'args':args or [],'monotonic_ns':mono}


def end(i,op,wall,cpu,exclusive_wall,exclusive_cpu,parent=None):
    return {'event':'end','call':i,'operation':op,'parent':parent,'thread':1,'wall_ns':wall,'process_cpu_ns':cpu,'exclusive_wall_ns':exclusive_wall,'exclusive_process_cpu_ns':exclusive_cpu}


class CostAnalysisTests(unittest.TestCase):
    def test_nested_inclusive_cost_is_not_counted_twice(self):
        rows=[begin(1,'root'),begin(2,'torch.functional.linear',1,1),end(2,'torch.functional.linear',20,30,20,30,1),end(1,'root',50,60,30,30)]
        result,_=a.summarize(rows)
        self.assertEqual(result['correlation_issues'],[])
        self.assertAlmostEqual(sum(result['completed_exclusive_wall_seconds'].values()),50e-9)
        self.assertNotEqual(sum(result['completed_exclusive_wall_seconds'].values()),70e-9)

    def test_qk_av_classification_and_unfinished_nesting(self):
        q=[{'shape':[1,8,1929,256]},{'shape':[1,8,256,1929]}]
        av=[{'shape':[1,8,1929,1929]},{'shape':[1,8,1929,512]}]
        self.assertEqual(a.category(begin(1,'torch.matmul',args=q)),'QK_D256')
        self.assertEqual(a.category(begin(1,'torch.matmul',args=av)),'AV_D512')
        result,_=a.summarize([begin(1,'root',mono=10),begin(2,'torch.matmul',1,1,av,20)],100)
        self.assertEqual(result['completed_count'],0)
        self.assertEqual(len(result['open_at_trace_end']),2)
        self.assertEqual(result['open_at_trace_end'][-1]['open_interval_at_stop_seconds'],80e-9)
        self.assertEqual(result['completed_exclusive_wall_seconds'],{})

    def test_saved_bf16_bytes_verify_without_tensor_values_or_model(self):
        native=struct.pack('<3H',0x3f80,0x4000,0xbf80)
        f32=struct.pack('<3f',1,2,-1)
        x=a.inspect_bf16_pair(native,f32)
        self.assertTrue(x['BF16_to_F32_bits_exact']);self.assertTrue(x['all_finite'])
        self.assertEqual(x['argmax_id'],1);self.assertEqual(x['argmax_tie_count'],1)
        self.assertNotIn('values',x)
        self.assertFalse(a.inspect_bf16_pair(native,struct.pack('<3f',1,3,-1))['BF16_to_F32_bits_exact'])
        with self.assertRaises(ValueError):a.inspect_bf16_pair(b'x',b'')

    def test_bad_exclusive_metadata_is_reported(self):
        result,_=a.summarize([begin(1,'root'),end(1,'root',10,10,9,10)])
        self.assertTrue(result['correlation_issues'])


class SavedCostCheckpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result=json.loads((TRACK/'results/native-qat-cost-checkpoint-01/result.json').read_text())

    def test_one_consumed_partial_checkpoint_and_release(self):
        x=self.result
        self.assertEqual(x['forward_attempts'],1)
        self.assertFalse(x['completed_forward'])
        self.assertEqual(x['guard']['actual_child_exit'],-15)
        self.assertTrue(x['guard']['child_reaped'])
        self.assertFalse(x['memory_lock_admission'])
        self.assertFalse(x['automatic_replay'])
        self.assertEqual(x['phone_calls'],0)
        self.assertTrue(x['strict_loaded_validation_passed'])

    def test_valid_uncapped_nested_trace_and_operator_localization(self):
        t=self.result['trace']
        self.assertEqual(t['correlation_issues'],[])
        self.assertEqual(t['malformed_line_numbers'],[])
        self.assertFalse(t['trace_may_be_capped'])
        self.assertEqual(t['begin_count'],959)
        self.assertEqual(t['completed_count'],954)
        self.assertEqual(t['groups']['AV_D256']['completed_calls'],18)
        self.assertEqual(t['groups']['AV_D512']['completed_calls'],4)
        self.assertGreater(t['AV_only_full35_layer_projection_seconds'],600)
        self.assertEqual(t['open_at_trace_end'][-1]['operation'],'torch.functional.linear')
        self.assertIn('layers.21.mlp.up_proj',t['open_at_trace_end'][-2]['operation'])

    def test_full_property_evaluated_once_and_bounded_verbose_retained(self):
        x=self.result;t=x['trace']
        self.assertEqual(t['groups']['full_token_embedding_dequant']['completed_calls'],1)
        self.assertLess(t['groups']['full_token_embedding_dequant']['exclusive_wall_total_seconds'],2)
        for stream in x['guard']['streams'].values():
            self.assertEqual(stream['discarded_bytes'],0)
            self.assertIsNone(stream['error'])
        self.assertEqual(x['forward_sampled_IO_delta']['read_bytes'],4988928)
        self.assertIn('Missing records',x['kernel_identity_boundary'])


class SavedFullCheckpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result=json.loads((TRACK/'results/native-qat-prefill-1800-01/result.json').read_text())

    def test_complete_native_logits_and_coverage(self):
        x=self.result;v=x['independent_logit_verification']
        self.assertTrue(x['completed_forward']);self.assertTrue(v['passed'])
        self.assertEqual(v['elements'],262144);self.assertEqual(v['argmax_id'],8291)
        self.assertEqual(v['argmax_tie_count'],1)
        self.assertTrue(v['BF16_to_F32_bits_exact']);self.assertTrue(v['all_finite'])
        self.assertTrue(v['all_35_decoder_boundaries_once'])
        self.assertTrue(v['quant_forward_trace_matches_loaded'])
        self.assertTrue(v['all_native_SRQ_calls_observed'])

    def test_explicit_budget_revision_and_no_computation_or_quality_claim(self):
        x=self.result
        self.assertEqual(x['deadline_revision'],{'separately_authorized':True,'previous_envelope_seconds':600,'this_envelope_seconds':1800})
        self.assertFalse(x['changed_dtype_kernel_weights_scales_or_input'])
        self.assertFalse(x['QNN_root_cause_or_quality_result'])
        self.assertFalse(x['numerical_equality_to_uninstrumented_execution_verified'])
        self.assertEqual(x['guard']['actual_child_exit'],0);self.assertTrue(x['guard']['child_reaped'])
        self.assertIsNone(x['guard']['stop_reason']);self.assertFalse(x['memory_lock_admission'])
        self.assertFalse(x['automatic_replay']);self.assertEqual(x['phone_calls'],0)

    def test_complete_nested_trace_is_not_double_counted(self):
        t=self.result['trace']
        self.assertEqual(t['begin_count'],1496);self.assertEqual(t['completed_count'],1496)
        self.assertEqual(t['open_at_trace_end'],[]);self.assertEqual(t['correlation_issues'],[])
        self.assertFalse(t['trace_may_be_capped']);self.assertEqual(t['malformed_line_numbers'],[])
        self.assertAlmostEqual(sum(t['completed_exclusive_wall_seconds'].values()),948.112969292,places=6)
        self.assertEqual(t['groups']['AV_D256']['completed_calls'],28)
        self.assertEqual(t['groups']['AV_D512']['completed_calls'],7)
        self.assertEqual(t['groups']['full_token_embedding_dequant']['completed_calls'],1)


if __name__=='__main__':unittest.main()
