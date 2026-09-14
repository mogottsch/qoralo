import importlib
import json
from pathlib import Path
import sys
import unittest

import numpy as np

TRACK=Path(__file__).resolve().parents[1]/'improvements/0001-long-collapse-speed-quality'
sys.path.insert(0,str(TRACK/'tools'))
audit=importlib.import_module('audit_reference_zero_boundary')


class ReferenceZeroBoundaryTests(unittest.TestCase):
    def test_actual_epsilon_disappears_on_every_representable_mean_code(self):
        result=audit.same_grid_zero_check(.023287702351808548,9.994658967116266e-7)
        self.assertEqual(result['all_representable_mean_codes_tested'],65536);self.assertEqual(result['codes_changed_by_epsilon'],0)
        self.assertEqual(result['zero_mean_after_add_code'],0)
        self.assertGreater(audit.same_grid_zero_check(.023287702351808548,.02)['codes_changed_by_epsilon'],0)

    def test_zero_negative_power_is_positive_infinity_not_NaN(self):
        with np.errstate(divide='ignore',invalid='raise'):value=np.power(np.float32(0),np.float32(-.5))
        self.assertTrue(np.isposinf(value));self.assertFalse(np.isnan(value))
        # A portable hypothetical clamp is not evidence that a backend implements it.
        self.assertEqual(int(np.clip(value,0,65535)),65535)

    def test_CPU_observations_do_not_become_HTP_or_saturation_claims(self):
        path=TRACK/'.local/reference-zero-boundary/cpu-03/result.json'
        if not path.exists():self.skipTest('retained CPU fixture unavailable')
        r=json.loads(path.read_text());records=r['CPU_fixture']['records']
        rejected=[x for x in records if x.get('case')=='direct_UF16_Power' and x.get('stage')=='addPower']
        self.assertEqual(rejected[0]['status'],3110)
        outputs={x['case']:x for x in records if x.get('event')=='output'}
        self.assertEqual(outputs['F32_Power']['values'][0],'+Inf')
        self.assertEqual(outputs['F32_Power_then_Convert']['codes'][0],0)
        self.assertEqual(outputs['F32_specials_Convert']['codes'][:3],[0,0,0])
        self.assertFalse(r['QNN_compiler_fusion_or_HTP_edge_behavior_established'])
        self.assertFalse(r['CPU_fixture']['phone_or_HTP_used'])

    def test_pre_execution_fixture_failures_are_preserved_separately(self):
        root=TRACK/'.local/reference-zero-boundary'
        if not (root/'cpu-01/cpu-result.json').exists():self.skipTest('retained fixture attempts unavailable')
        first=json.loads((root/'cpu-01/cpu-result.json').read_text());second=json.loads((root/'cpu-02/cpu-result.json').read_text())
        self.assertEqual(first['harness_exit'],3);self.assertEqual(first['successful_graph_executions'],0)
        self.assertEqual(second['successful_graph_executions'],0)
        self.assertEqual(sum(x.get('status')==7004 for x in second['records']),4)


if __name__=='__main__':unittest.main()
