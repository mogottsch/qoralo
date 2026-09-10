"""Saved GateB evidence only; no tokenizer/model/device execution."""
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import unittest

EXP = Path(__file__).resolve().parents[1]
TRACK = EXP / 'improvements/0001-long-collapse-speed-quality'
ROOT = TRACK / 'results/phone-return-long-attempt-01'


class LongOutcomeTest(unittest.TestCase):
    def setUp(self):
        self.r = json.loads((ROOT / 'result.json').read_text())

    def test_real_query_counts_and_input_are_distinct_from_exit_code(self):
        r = self.r
        self.assertEqual([], r['analysis_issues'])
        self.assertEqual(1929, r['prompt']['profile_tokens'])
        self.assertTrue(r['prompt']['bytes_exact'])
        self.assertTrue(all(x['single_bos_prefix'] and x['matches_bound_prefix'] for x in r['prompt']['logged_prefixes']))
        self.assertEqual(2048, r['output']['profile_generated_tokens'])
        self.assertEqual(2048, r['output']['retokenized_tokens'])
        p = r['provider_observations']
        self.assertEqual(1, p['context_deserialized'])
        self.assertEqual(1, p['query_enter'])
        self.assertEqual(1, p['query_return'])
        self.assertEqual(16, p['ar128_status0'])
        self.assertEqual(2047, p['ar1_status0'])
        self.assertEqual(2063, p['graphs_status0'])
        self.assertEqual(0, p['graph_nonzero_status'])
        self.assertEqual(1, p['smart_mask'])
        self.assertEqual(0, p['runtime_fallback_markers'])
        self.assertEqual(0, p['cpu_backend_markers'])
        self.assertEqual(0, p['cache_quantization_errors'])
        self.assertTrue(r['stop']['ceiling_reached'])
        self.assertIsNone(r['stop']['explicit_runtime_stop_reason'])

    def test_full_output_equals_all_five_retained_baselines_and_fails_sanity(self):
        r = self.r
        path = ROOT / r['output']['path']
        data = path.read_bytes()
        self.assertEqual(10027, len(data))
        self.assertEqual('f0e9d284f679e2ae426264573bd2be16e7c1e4b190235a3511c5a92ecc097b2d', hashlib.sha256(data).hexdigest())
        self.assertTrue(r['comparison']['candidate_byte_identical_to_all_baselines'])
        self.assertEqual(5, len(r['comparison']['baseline_output_hashes']))
        for baseline in (EXP / 'results/android-qnn-physical-campaign-attempt-02/raw/campaign/outputs').glob('warm-long-*.txt'):
            self.assertEqual(data, baseline.read_bytes())
        self.assertIn(b'<unk>', data)
        self.assertEqual({'looks_sensible', 'issue_notes'}, set(r['output_sanity']))
        self.assertFalse(r['output_sanity']['looks_sensible'])
        self.assertTrue(r['output_sanity']['issue_notes'])
        self.assertFalse(r['publication']['long_repetition_improved'])
        self.assertFalse(r['publication']['speed_acceptance'])
        self.assertFalse(r['publication']['registry_eligible'])

    def test_frozen_metrics_equal_and_window_start_not_causal_onset(self):
        r = self.r['comparison']
        frozen = json.loads((TRACK / 'results/long-collapse-baseline/result.json').read_text())['qnn_collapse']['trajectory']
        self.assertEqual(frozen, r['baseline_metrics'])
        self.assertEqual(frozen, r['candidate_metrics'])
        self.assertTrue(r['all_declared_metrics_equal'])
        self.assertEqual(83, r['candidate_metrics']['rolling_collapse_onset']['start_token_index_zero_based'])
        suffix = r['candidate_metrics']['exact_periodic_suffix']
        self.assertEqual((478, 9, 1570, 174, 4), (suffix['start_token_index_zero_based'], suffix['period_tokens'], suffix['suffix_tokens'], suffix['complete_cycles'], suffix['trailing_partial_cycle_tokens']))
        self.assertIn('not an exact causal onset', r['onset_boundary'])
        self.assertIn('may retain internal quantization', r['cause_boundary'])
        self.assertIsNone(self.r['raw_genie_profile']['normalized_decode_tokens_per_second'])

    def test_provider_log_lossless_identity_and_actual_status_counts(self):
        info = self.r['provider_log']
        digest = hashlib.sha256(); size = 0; counts = Counter()
        with gzip.open(ROOT / info['compressed_path'], 'rb') as source:
            for line in source:
                digest.update(line); size += len(line)
                if b'QnnGraph_execute done. status 0x0' in line: counts['done'] += 1
                if b'Graph ar128_cl4096_1_of_1 execution finished with result 0' in line: counts['ar128'] += 1
                if b'Graph ar1_cl4096_1_of_1 execution finished with result 0' in line: counts['ar1'] += 1
        self.assertEqual(54108333, size)
        self.assertEqual(info['original_sha256'], digest.hexdigest())
        self.assertEqual({'done': 2063, 'ar128': 16, 'ar1': 2047}, dict(counts))

    def test_cleanup_privacy_and_public_hashes(self):
        r = self.r
        self.assertTrue(r['cleanup']['live_native_pid_observed'])
        self.assertTrue(r['cleanup']['recorded_roles_absent'])
        self.assertTrue(r['cleanup']['remote_root_absent'])
        self.assertTrue(r['cleanup']['lock_released'])
        self.assertEqual(0, r['cleanup']['signal_commands'])
        self.assertEqual(281, r['cleanup']['adb_calls'])
        self.assertTrue(r['cleanup']['all_calls_lock_guarded'])
        self.assertTrue(r['cleanup']['raw_pull_before_cleanup'])
        self.assertEqual(2, len(r['privacy_retention']['private_battery_originals']))
        self.assertEqual([], list((ROOT / 'raw/controller/raw/commands').glob('*-telemetry.*.battery.stdout')))
        self.assertIsNone(r['memory']['process_pss'])
        for line in (ROOT / 'SHA256SUMS').read_text().splitlines():
            digest, name = line.split('  ', 1)
            self.assertEqual(digest, hashlib.sha256((ROOT / name).read_bytes()).hexdigest())


if __name__ == '__main__': unittest.main()
