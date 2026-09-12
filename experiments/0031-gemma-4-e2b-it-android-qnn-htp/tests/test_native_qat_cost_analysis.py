import importlib
import json
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


if __name__=='__main__':unittest.main()
