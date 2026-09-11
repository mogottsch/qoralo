"""Synthetic accepted-generation correlation, never model observations."""
import importlib
from pathlib import Path
import sys
import unittest

TOOLS=Path(__file__).resolve().parents[1]/'improvements/0001-long-collapse-speed-quality/tools'
sys.path.insert(0,str(TOOLS))
parse=importlib.import_module('analyze_selected_id_trace')
a=importlib.import_module('correlate_selected_id_trace')


class CorrelationTests(unittest.TestCase):
    def trace(self):
        return parse.summarize('\n'.join([
            'GEMMA_SELECTED_ID_V1 ordinal=0 token=7 configured_eos=0 n_past=1929',
            'GEMMA_SELECTED_ID_V1 ordinal=1 token=50 configured_eos=0 n_past=1929',
            'GEMMA_SELECTED_ID_V1 ordinal=2 token=106 configured_eos=1 n_past=1930']),3)

    def run_correlation(self,trace=None,**changes):
        args=dict(input_count=1929,accepted_generated_count=3,basic_scope_confirmed=True,
                  ar128_status0_count=16,ar1_status0_count=2)
        args.update(changes)
        return a.correlate(trace or self.trace(),**args)

    def test_first_and_second_selected_ids_share_preincrement_npast(self):
        result=self.run_correlation()
        self.assertTrue(result['accepted_generation_coverage_complete'])
        records=result['accepted_generation_records']
        self.assertEqual([r['producer_execution_index'] for r in records],[15,16,17])
        self.assertEqual(records[0]['phase'],'first_generated_after_complete_prefill')
        self.assertEqual(records[1]['primary_decode_step'],1)
        self.assertTrue(result['id50_continuation_observations'][0]['later_accepted_generation_observed'])
        self.assertIsNone(result['internal_stop_decision'])

    def test_unconfirmed_scope_never_promotes_proposal_or_prefill_records(self):
        result=self.run_correlation(basic_scope_confirmed=False)
        self.assertFalse(result['accepted_generation_records'])
        self.assertEqual(len(result['excluded_unpromoted_observations']),3)
        self.assertIsNone(result['accepted_id50_observed'])

    def test_wrong_position_and_not_accepted_token_are_preserved_but_excluded(self):
        trace=self.trace();trace['records'][1]['n_past']=128
        result=self.run_correlation(trace)
        self.assertFalse(result['accepted_generation_coverage_complete'])
        self.assertIsNone(result['accepted_id50_observed'])
        self.assertEqual(result['excluded_unpromoted_observations'][0]['observation']['token'],50)
        result=self.run_correlation(accepted_generated_count=1,ar1_status0_count=0)
        self.assertIsNone(result['accepted_id50_observed'])
        self.assertEqual(len(result['excluded_unpromoted_observations']),2)

    def test_optional_backend_count_gap_does_not_invent_a_producer_step(self):
        result=self.run_correlation(ar1_status0_count=None)
        self.assertTrue(result['accepted_generation_coverage_complete'])
        self.assertFalse(result['backend_execution_counts_bound'])
        self.assertTrue(all(r['producer_execution_index'] is None for r in result['accepted_generation_records']))

    def test_no_later_record_is_not_a_stop_decision(self):
        trace=self.trace();trace['records']=trace['records'][:2]
        result=self.run_correlation(trace,accepted_generated_count=2,ar1_status0_count=1)
        self.assertTrue(result['accepted_id50_observed'])
        self.assertIsNone(result['id50_continuation_observations'][0]['later_accepted_generation_observed'])
        self.assertIsNone(result['internal_stop_decision'])


if __name__=='__main__':unittest.main()
