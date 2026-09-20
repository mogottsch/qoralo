import importlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

TRACK=Path(__file__).resolve().parents[1]/'improvements/0001-long-collapse-speed-quality'
sys.path.insert(0,str(TRACK/'tools'))
f=importlib.import_module('freeze_embedding_boundary_checkpoint')


class EmbeddingBoundaryCheckpointTests(unittest.TestCase):
    def test_declared_requantization_matches_recorded_export_contract(self):
        encoding={'scale':0.050521295210894414,'offset':-170}
        grid={'scale':0.0006225576507858932,'offset':-30370}
        r=f.requantization(encoding,grid)
        self.assertAlmostEqual(r['requant_scale'],81.15119161593829,places=9)
        self.assertEqual(r['requant_offset_int32'],16574)
        self.assertLessEqual(r['reachable_code_min'],16574)
        self.assertGreaterEqual(r['reachable_code_max'],37267)
        self.assertTrue(r['all_codes_in_UINT16_range'])

    def test_error_budget_declares_three_terms_and_no_acceptance_threshold(self):
        b=f.error_budget({'scale':0.050521295210894414},0.0008041618001537465,8.58862018585205)
        self.assertAlmostEqual(b['LUT_UINT8_half_step'],0.025260647605447207)
        self.assertEqual(b['native_BF16_half_ulp_at_max_abs_value'],f.bf16_half_ulp(8.58862018585205))
        self.assertAlmostEqual(b['per_element_budget_at_max_abs_value'],
                               b['LUT_UINT8_half_step']+b['UINT8_to_UINT16_max_added_error']+b['native_BF16_half_ulp_at_max_abs_value'])
        self.assertIn('not an accuracy acceptance threshold',b['boundary'].lower().replace('claimed hardware error bound and ',''))

    def test_bf16_half_ulp_scales_with_magnitude(self):
        self.assertEqual(f.bf16_half_ulp(0),0.0)
        self.assertEqual(f.bf16_half_ulp(1.0),2.0**-8)
        self.assertEqual(f.bf16_half_ulp(-8.0),2.0**-5)
        self.assertLess(f.bf16_half_ulp(0.1),f.bf16_half_ulp(4.0))

    def test_capture_code_image_check_rejects_out_of_image_codes(self):
        reach={'reachable_code_min':16574,'reachable_code_max':37267}
        with tempfile.TemporaryDirectory() as tmp:
            good=Path(tmp)/'good.raw';np.full(128*1536,20000,dtype='<u2').tofile(good)
            self.assertTrue(f.inspect_capture_codes(good,reach)['inside_declared_LUT_image'])
            bad=Path(tmp)/'bad.raw';values=np.full(128*1536,20000,dtype='<u2');values[7]=65535;values.tofile(bad)
            self.assertFalse(f.inspect_capture_codes(bad,reach)['inside_declared_LUT_image'])
            short=Path(tmp)/'short.raw';np.zeros(16,dtype='<u2').tofile(short)
            with self.assertRaises(ValueError):f.inspect_capture_codes(short,reach)

    def test_frozen_contract_is_declarative_and_admits_its_limits(self):
        path=TRACK/'results/embedding-boundary-checkpoint-01/contract.json'
        if not path.exists():self.skipTest('frozen contract not published yet')
        c=json.loads(path.read_text())
        self.assertEqual(c['classification'],'frozen_input_boundary_checkpoint_not_executed')
        self.assertFalse(c['executed_by_this_freeze'])
        self.assertFalse(c['internal_layer_activations_saved_on_either_route'])
        self.assertEqual(c['free_parameters_or_fitted_scalars'],0)
        self.assertEqual(c['input_ids'],1929)
        self.assertEqual([s['graph_input'] for s in c['sides']],['inputs_embeds','per_layer_inputs'])
        for side in c['sides']:
            self.assertFalse(side['native_side']['saved_native_activation_available'])
        self.assertTrue(c['captured_chunk0_check']['inside_declared_LUT_image'])
        self.assertEqual(c['execution_envelope_if_authorized']['model_forward_calls'],0)
        self.assertEqual(c['execution_envelope_if_authorized']['ADB_calls'],0)
        self.assertTrue(any('layer' in x for x in c['what_this_cannot_decide']))


if __name__=='__main__':unittest.main()
