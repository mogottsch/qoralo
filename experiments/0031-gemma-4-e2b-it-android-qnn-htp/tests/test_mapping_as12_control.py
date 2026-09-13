import importlib
import json
from pathlib import Path
import sys
import unittest

TRACK=Path(__file__).resolve().parents[1]/'improvements/0001-long-collapse-speed-quality'
sys.path.insert(0,str(TRACK/'tools'))


class AS12ControlTests(unittest.TestCase):
    def test_materialized_shell_changes_exactly_one_AS_line(self):
        old=importlib.import_module('phone_mapping_stage_capture');new=importlib.import_module('phone_mapping_as12_capture')
        m8,_=old.load_adapter();c8,r8=m8.load_lifecycle({},False);m12,b=new.load_adapter();c12,r12=m12.load_lifecycle({},False)
        s8=c8.scripts('/data/local/tmp/SYNTHETIC_SAME_ROOT');s12=c12.scripts('/data/local/tmp/SYNTHETIC_SAME_ROOT')
        self.assertEqual(set(s8),set(s12))
        self.assertEqual([name for name in s8 if s8[name]!=s12[name]],['model-entry.sh'])
        self.assertEqual(s8['model-entry.sh'].replace('ulimit -v 8388608','ulimit -v 12582912'),s12['model-entry.sh'])
        self.assertEqual(r8['address_space_limit_bytes'],8589934592);self.assertEqual(r12['address_space_limit_bytes'],12884901888)
        self.assertEqual(r8['stage_digest'],r12['stage_digest']);self.assertEqual(r8['libGenie_sha256'],r12['libGenie_sha256'])
        self.assertFalse(b['RAM_budget_changed']);self.assertFalse(b['observer_model_LUT_input_token_time_capture_limits_changed'])

    def test_plan_is_no_permission_and_keeps_other_limits(self):
        m,b=importlib.import_module('phone_mapping_as12_capture').load_adapter();c,_=m.load_lifecycle({},False);p=c.plan()
        self.assertEqual(p['adb_calls'],0);self.assertFalse(p['phone_permission_granted_by_plan'])
        self.assertEqual(p['phone_address_space_limit_bytes'],12884901888);self.assertEqual(p['process_deadline_seconds'],300)
        self.assertEqual(p['capture_payload_cap_bytes'],80*1024**2);self.assertFalse(p['auto_retry'])
        self.assertIn('_finish_remote',c.Controller.__dict__)
        self.assertFalse(b['new_phone_or_model_execution_authorized_by_preparation'])

    def test_actual_readback_is_not_inferred_from_plan(self):
        f=importlib.import_module('phone_mapping_as12_capture').inspect_readbacks
        self.assertIsNone(f([])['matches_expected'])
        self.assertIsNone(f(['GEMMA_MAPPING_V1 role=ple'])['matches_expected'])
        self.assertFalse(f(['GEMMA_ALLOC_V1 rlimit_valid=1 AS_soft=8589934592 AS_hard=8589934592'])['matches_expected'])
        self.assertTrue(f(['GEMMA_MAPPING_V1 rlimit_valid=1 AS_soft=12884901888 AS_hard=12884901888'])['matches_expected'])
        self.assertIsNone(f(['GEMMA_MAPPING_V1 rlimit_valid=0 AS_soft=0 AS_hard=0'])['matches_expected'])

    def test_8GiB_outcome_keeps_shadow_stack_and_QNN_errors_separate(self):
        root=TRACK/'results/paired-mapping-discriminator-01'
        result=json.loads((root/'result.json').read_text());analysis=json.loads((root/'analysis.json').read_text())
        self.assertEqual(result['actual_native_exit'],134);self.assertTrue(result['mappings_valid_this_run'])
        self.assertEqual(result['engine_AS_headroom_bytes'],4407296);self.assertFalse(result['host_reference_started'])
        self.assertEqual(result['first_chunk_payloads'],8);self.assertFalse(result['complete_prefill_or_logits'])
        self.assertTrue(result['postflight_verified']);self.assertTrue(result['phone_lock_released'])
        self.assertTrue(analysis['QNN_provider_errors']);self.assertFalse(analysis['ordering_or_causal_relationship_of_QNN_errors_and_abort_resolved'])
        self.assertFalse(analysis['this_run_diagnoses_earlier_bad_alloc_or139'])

    def test_restricted_input_payloads_are_bound_not_published(self):
        root=TRACK/'results/paired-mapping-discriminator-01'
        inputs=json.loads((root/'private-input-payloads.json').read_text())
        self.assertEqual(len(inputs),8);self.assertEqual(sum(r['bytes'] for r in inputs),4096000)
        self.assertFalse(list(root.rglob('*.raw')))


if __name__=='__main__':unittest.main()
