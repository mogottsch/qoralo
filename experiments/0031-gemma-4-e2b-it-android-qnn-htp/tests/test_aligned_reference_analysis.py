import importlib
import json
import hashlib
from pathlib import Path
import struct
import sys
import unittest

TRACK=Path(__file__).resolve().parents[1]/'improvements/0001-long-collapse-speed-quality'
sys.path.insert(0,str(TRACK/'tools'))
a=importlib.import_module('analyze_aligned_litert_reference')


class AlignedAnalysisTests(unittest.TestCase):
    def test_full_input_not_count_only(self):
        record={'actual_effective_token_ids':[2,105,7],'expected_effective_token_ids':[2,105,7],'all_ids_equal':True,'prefill_not_yet_started':True}
        expected=struct.pack('<3i',2,105,7)
        self.assertTrue(a.input_alignment(record,expected)['exact_frozen_ids_equal'])
        record['actual_effective_token_ids']=[2,105,8]
        self.assertFalse(a.input_alignment(record,expected)['exact_frozen_ids_equal'])

    def test_invalid_ids_rejected(self):
        for values in ([True,2],[-1],[262144],['2'],None):
            with self.assertRaises(ValueError):a.packed(values)

    def test_prefix_difference_is_descriptive(self):
        result=a.prefix_comparison([818,42,9],[818,42,10,11])
        self.assertEqual(result['common_prefix_tokens'],2)
        self.assertEqual(result['first_differing_index'],2)
        self.assertEqual(result['reference_id_at_difference'],9)

    def test_filtered_terminal_not_invented(self):
        result=a.prefix_comparison([818,42],[818,42,106])
        self.assertIsNone(result['first_differing_index'])
        self.assertTrue(result['one_stream_ended_after_common_prefix'])
        self.assertIsNone(result['qnn_id_at_difference'])


class SavedAlignedOutcomeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root=TRACK/'results/aligned-reference-phone-long-attempt-01'
        cls.result=json.loads((cls.root/'result.json').read_text())

    def test_exact_input_and_one_completed_request(self):
        x=self.result
        self.assertEqual(x['analysis_issues'],[])
        self.assertTrue(x['input_alignment']['exact_frozen_ids_equal'])
        self.assertEqual(x['input_alignment']['actual_count'],1929)
        self.assertEqual(x['input_alignment']['actual_int32le_sha256'],a.INPUT_SHA)
        self.assertTrue(all(x['scope_checks'].values()))
        self.assertEqual(len(x['runner']['runs']),1)
        self.assertEqual(x['runner']['runs'][0]['runtime_prefill_tokens'],1929)
        self.assertFalse(x['runner']['runs'][0]['rewind_called'])

    def test_sensible_complete_output_with_filtered_id_boundary(self):
        x=self.result;output=self.root/x['output']['path']
        self.assertEqual(hashlib.sha256(output.read_bytes()).hexdigest(),'c64a18a7e0059a2a874b6310133f4f00f53f0f2c1d8b935acaec3d29c6d0d55d')
        self.assertEqual(output.stat().st_size,3717)
        self.assertEqual(x['output']['callback_tokens'],643)
        self.assertEqual(x['runner']['runs'][0]['runtime_generated_tokens'],644)
        self.assertTrue(x['output']['callback_ids_stop_filtered'])
        self.assertIsNone(x['internal_terminal_id'])
        self.assertEqual(x['output_sanity'],{'looks_sensible':True,'issue_notes':None})
        self.assertIsNone(x['frozen_callback_trajectory_metrics']['exact_periodic_suffix'])
        self.assertEqual(x['trajectory_comparison']['first_differing_index'],0)
        self.assertFalse(x['runtime_equivalence_proven'])

    def test_full_cleanup_and_unchanged_apk_checks(self):
        x=self.result;c=x['cleanup']
        self.assertEqual(c['adb_calls'],149)
        for k in ('all_calls_locked_noninheritable','all_roles_absent','lock_released','raw_pull_before_root_removal','root_absent'):self.assertTrue(c[k])
        self.assertEqual(c['signal_guard_events'],[])
        self.assertTrue(x['collection']['postflight_installed_app_identity']['unchanged'])
        self.assertTrue(x['collection']['current_app_preflight']['target_processes_absent'])
        self.assertTrue(x['collection']['app_quiescence_before_launch']['target_processes_absent'])
        self.assertEqual(x['collection']['process_exit_code'],0)

    def test_privacy_and_preserved_offline_failure(self):
        x=self.result
        self.assertEqual(x['private_original_hashes_verified'],622)
        self.assertEqual(len(x['private_battery_originals']),2)
        for row in x['private_battery_originals']:
            self.assertEqual(a.sha(Path(row['path'])),row['sha256'])
            self.assertFalse((self.root/'raw/controller/raw/commands'/Path(row['path']).name).exists())
        first=json.loads((self.root/'analysis-attempt-01.json').read_text())
        self.assertTrue(first['analysis_issues'])
        self.assertTrue(x['offline_analysis_correction']['no_new_model_request'])
        self.assertFalse(x['new_inference_authorized'])


if __name__=='__main__':unittest.main()
