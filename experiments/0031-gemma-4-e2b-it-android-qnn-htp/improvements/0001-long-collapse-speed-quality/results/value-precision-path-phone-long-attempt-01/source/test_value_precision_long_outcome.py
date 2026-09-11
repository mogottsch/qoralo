"""Immutable saved candidate outcome; no phone/model or tokenizer execution."""
import gzip
import hashlib
import json
from pathlib import Path
import unittest

TRACK = Path(__file__).resolve().parents[1]/'improvements/0001-long-collapse-speed-quality'
RESULT = TRACK/'results/value-precision-path-phone-long-attempt-01'


class ValueLongOutcomeTests(unittest.TestCase):
    def setUp(self):
        self.result = json.loads((RESULT/'result.json').read_text())

    def test_new_output_is_bound_and_not_mistaken_for_prior_negative(self):
        result = self.result
        self.assertEqual(result['analysis_issues'], [])
        self.assertIsNone(result['comparison_missing_reason'])
        self.assertEqual(result['context_sha256'], '27e19e32ef479dfb39b53e6530cd25105c3c8e9ccf9fa4b9e9af4b5d770fabdd')
        output = RESULT/result['observations']['output']['path']
        self.assertEqual(hashlib.sha256(output.read_bytes()).hexdigest(), '5e3c8bff8006912eabc16b86783d59f387d9239042d55a3f3f312914610cc5c0')
        self.assertFalse(result['comparison']['candidate_byte_identical_to_all_baselines'])
        self.assertEqual(result['observations']['prompt']['profile_prompt_tokens'], 1929)
        self.assertEqual(result['observations']['actual_generated_tokens'], 2048)
        self.assertFalse(result['output_sanity']['looks_sensible'])
        self.assertIsNone(result['observations']['raw_genie_profile']['normalized_decode_tokens_per_second'])

    def test_null_narrow_window_criterion_does_not_erase_long_period_collapse(self):
        metrics = self.result['comparison']['candidate_metrics']
        self.assertIsNone(metrics['rolling_collapse_onset'])
        suffix = metrics['exact_periodic_suffix']
        self.assertEqual(suffix, {'period_tokens':44, 'start_token_index_zero_based':560,
            'suffix_tokens':1488, 'complete_cycles':33, 'trailing_partial_cycle_tokens':36})
        self.assertGreater(suffix['suffix_tokens']/metrics['token_count'], 0.7)
        self.assertFalse(self.result['output_sanity']['looks_sensible'])
        self.assertFalse(self.result['comparison']['all_declared_metrics_equal'])

    def test_real_execution_cleanup_and_lossless_provider_log(self):
        result = self.result; collection = result['collection']
        self.assertEqual(collection['cleanup'], 'verified_absent')
        self.assertTrue(collection['process_cleanup']['all_absent'])
        self.assertTrue(collection['phone_lock_released'])
        self.assertTrue(collection['raw_pull_completed'])
        self.assertFalse(collection['rpc_preflight']['functional_rpc_health_proven'])
        counts = result['observations']['execution_markers']
        self.assertEqual(counts['htp_initialized'], 1)
        self.assertEqual(counts['graph_execute_status0'], 2063)
        self.assertEqual(counts['graph_execute_nonzero_status'], 0)
        digest=hashlib.sha256();size=0
        with gzip.open(RESULT/result['provider_log']['compressed_path'],'rb') as stream:
            for data in iter(lambda:stream.read(4*1024*1024),b''):
                digest.update(data);size+=len(data)
        self.assertEqual(digest.hexdigest(), result['provider_log']['original_sha256'])
        self.assertEqual(size, result['provider_log']['original_bytes'])


if __name__=='__main__': unittest.main()
