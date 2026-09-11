"""Saved/source audit checks only; no model/runtime/phone execution."""
import importlib
import json
from pathlib import Path
import sys
import unittest

TRACK=Path(__file__).resolve().parents[1]/'improvements/0001-long-collapse-speed-quality'
sys.path.insert(0,str(TRACK/'tools'))
a=importlib.import_module('audit_saved_termination')


class TerminationAuditTests(unittest.TestCase):
    def test_bounded_protobuf_token_union(self):
        self.assertEqual(a.token_union(bytes.fromhex('0a030a0132')), [50])
        with self.assertRaises(ValueError):list(a.fields(bytes.fromhex('0a08ff')))
        with self.assertRaises(ValueError):a.varint(b'\x80',0)

    def test_actual_policy_gap_is_not_promoted_to_observed_missed_token(self):
        result=json.loads((a.RESULT/'result.json').read_text())
        self.assertEqual(result['qnn_context']['eos-token'],[1,106])
        self.assertEqual(result['model_metadata']['stop_sequences'],[[1],[50],[106]])
        self.assertEqual(set(result['qat_generation_eos_ids']),{1,50,106})
        self.assertEqual(result['special_token_names']['50'],'<|tool_response>')
        self.assertEqual(result['special_token_names']['106'],'<turn|>')
        self.assertIsNone(result['actual_missed_token50_observed'])
        self.assertFalse(result['actual_qnn_sampled_id_stream_retained'])
        self.assertFalse(result['termination_or_input_changed'])

    def test_same_text_is_not_misreported_as_same_effective_history(self):
        result=json.loads((a.RESULT/'result.json').read_text())
        for route in result['reference_routes'].values():
            for tier in route['input_comparison'].values():
                self.assertTrue(tier['same_rendered_bytes'])
                self.assertTrue(tier['entire_reference_equals_extra_BOS_then_QNN'])
                self.assertEqual(tier['reference_count'],tier['qnn_count']+1)
            for run in route['long_actual_callback_evidence']:
                self.assertEqual(run['filtered_callback_count'],756)
                self.assertIsNone(run['terminating_sampled_id'])


if __name__=='__main__':unittest.main()
