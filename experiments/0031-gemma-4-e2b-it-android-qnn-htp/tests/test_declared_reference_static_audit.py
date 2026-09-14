import importlib
import json
from pathlib import Path
import sys
import unittest

import numpy as np

TRACK=Path(__file__).resolve().parents[1]/'improvements/0001-long-collapse-speed-quality'
sys.path.insert(0,str(TRACK/'tools'))
audit=importlib.import_module('audit_declared_reference_static')


class StaticReferenceAuditTests(unittest.TestCase):
    def test_documented_low_bits_ignore_upper_container_bits(self):
        words=np.array([0x0d,0xfd,0x08,0xf8,0x07],dtype=np.uint8)
        np.testing.assert_array_equal(audit.signed_low_bits(words,4),[-3,-3,-8,-8,7])

    def test_FP16_transport_prototype_is_metadata_specific(self):
        words=np.array([0x3c00,0x8000],dtype=np.uint16);half=audit.prototype_fp16_storage_view(words,'Float_16')
        np.testing.assert_array_equal(half.view(np.uint16),words);self.assertEqual(half[0],1)
        self.assertIs(audit.prototype_fp16_storage_view(words,'uFxp_16'),words)

    def test_static_weight_evidence_does_not_fit_QNN_logits(self):
        path=TRACK/'.local/declared-reference-static-audit/bw4-02/result.json'
        if not path.exists():self.skipTest('private static audit unavailable')
        result=json.loads(path.read_text());self.assertEqual(result['model_or_operator_forward_calls'],0)
        head=result['weights'][0];self.assertEqual(head['sampled_values'],1572864)
        self.assertEqual(head['candidates']['documented_signed_BW4']['max_absolute_error'],0)
        self.assertGreater(head['candidates']['signed_int8_container_without_BW_interpretation']['nonzero_sign_disagreements'],500000)

    def test_active_FP16_defect_and_dormant_Cast_gap_remain_distinct(self):
        root=TRACK/'.local/declared-reference-static-audit'
        if not (root/'fp16-transport-01/result.json').exists():self.skipTest('private audit unavailable')
        f=json.loads((root/'fp16-transport-01/result.json').read_text());c=json.loads((root/'controls-02/result.json').read_text())
        self.assertEqual(len(f['static_tensors']),30);self.assertEqual(len(f['affected_consumers']),15)
        self.assertEqual(f['first_known_affected_operator']['index'],52);self.assertEqual(f['affected_operator_begins_in_saved_full_run'],240)
        self.assertTrue(f['all_affected_consumers_seen_in_all16chunks']);self.assertFalse(f['production_reference_implementation_changed'])
        self.assertIn('NOT an active explanation',c['dormant_Cast_generality_gap'])
        self.assertTrue(f['synthetic_actual_loader_preserved_view_RmsNorm_Cast_path']['prototype_matches_expected_half_bytes'])


if __name__=='__main__':unittest.main()
