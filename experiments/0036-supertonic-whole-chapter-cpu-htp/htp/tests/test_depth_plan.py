import importlib.util
import json
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from inspect_context_sizes import footprint


def graph(ddr):
    return {'graphBlobInfoV2':{'ioTensorSize':0,'opDataSize':0,'constSize':0,'ddrTensorSize':ddr,'sharedWeightsSize':0},'graphBlobInfo':{'info':{'spillFillBufferSize':0}}}


class DepthPlanTests(unittest.TestCase):
    def test_allowance_alignment_and_margin(self):
        result=footprint(graph(1600000000))
        self.assertTrue(result['passes_conservative_gate'])
        self.assertEqual(result['aligned_planning_estimate_bytes']%(64*1024**2),0)
        self.assertGreaterEqual(result['aligned_planning_estimate_bytes'],1600000000+128*1024**2)
        self.assertGreaterEqual(result['remaining_signed_margin_bytes'],64*1024**2)

    def test_near_ceiling_candidate_rejected(self):
        self.assertFalse(footprint(graph(2028594432))['passes_conservative_gate'])
        self.assertFalse(footprint(graph(2210381312))['passes_conservative_gate'])

    def test_private_three_part_structural_and_cpu_proof(self):
        p=ROOT/'.local/text-depth-three-01/structural-proof.json'
        if not p.exists():self.skipTest('private artifact absent')
        d=json.loads(p.read_text());self.assertEqual(d['source_nodes'],1934);self.assertEqual(d['source_initializers'],146)
        for key in ('all_original_nodes_covered','all_original_node_bytes_unchanged','all_original_initializer_bytes_unchanged','all_original_initializers_covered'):self.assertTrue(d[key])
        self.assertEqual(d['sequence_extent_unchanged'],3200)
        self.assertEqual(list(d['parts']),['text3_a','text3_b','text3_c'])
        result=json.loads((ROOT/'.local/text-depth-three-cpu-proof-01/result.json').read_text())
        self.assertTrue(result['bitwise_equal']);self.assertEqual(result['max_absolute_error'],0)
        self.assertEqual(result['total_Run_calls'],3);self.assertTrue(result['original_baseline_reused'])

    def test_stage_excludes_bad_text_context_and_CPU_outputs(self):
        p=ROOT/'.local/depth-stage-01/stage-provenance.json'
        if not p.exists():self.skipTest('private artifact absent')
        stage=json.loads(p.read_text());self.assertEqual(stage['text_depth_parts'],3)
        names=set(stage['files'])
        self.assertNotIn('contexts/text-context.onnx',names)
        self.assertFalse(any('CPU-validation' in n for n in names))
        for c in ('duration','text3_a','text3_b','text3_c','vector','vocoder'):
            self.assertIn('contexts/'+c+'-context.onnx',names)
        self.assertTrue(all(r['passes_conservative_gate'] for r in stage['allocation_plan']))
        self.assertEqual(stage['actual_neural_Run_calls'],{'duration':1,'text3_a':1,'text3_b':1,'text3_c':1,'vector':5,'vocoder':1})


if __name__=='__main__':unittest.main()
