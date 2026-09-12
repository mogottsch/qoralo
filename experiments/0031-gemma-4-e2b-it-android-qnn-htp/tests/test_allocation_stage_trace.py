import importlib
import json
from pathlib import Path
import sys
import unittest

TRACK=Path(__file__).resolve().parents[1]/'improvements/0001-long-collapse-speed-quality'
sys.path.insert(0,str(TRACK/'tools'))
p=importlib.import_module('prepare_allocation_stage_capture')


class AllocationObserverTests(unittest.TestCase):
    def test_fixed_stack_logger_has_no_authored_heap_calls(self):
        text=(TRACK/'tools/allocation_stage_trace.hpp').read_text()
        for forbidden in ['std::string','nlohmann','malloc(', 'calloc(', 'realloc(', 'operator new']:
            self.assertNotIn(forbidden,text)
        self.assertIn('char data[1536]',text);self.assertIn('char buffer[8192]',text)
        self.assertIn('const int observed_errno=errno;',text)
        self.assertIn('errno=saved_errno',text)
        self.assertIn('a > SIZE_MAX / b',text)
        self.assertIn('errno_at_observation',text)

    def test_lut_and_basic_original_allocations_stay_once(self):
        source='output.resize(tokens.size() * embeddingSize);\noutput.resize(p_vec.size() * embeddingSize);\n'
        changed=p.patch_lut(source)
        self.assertEqual(changed.count('output.resize(tokens.size() * embeddingSize);'),1)
        self.assertEqual(changed.count('output.resize(p_vec.size() * embeddingSize);'),1)
        self.assertEqual(changed.count('gemma_alloc_trace::resize('),2)
        source='std::vector<uint8_t> eosEmbedding(embedBufSize, 0.0);\nstd::vector<uint8_t> eosPerLayerEmbedding(embedPerLayerBufSize, 0.0);\nengine.process(embedding_vectors, embedding_perlayer_vectors, {}, logits);\n'
        changed=p.patch_basic(source)
        self.assertEqual(changed.count('engine.process(embedding_vectors, embedding_perlayer_vectors, {}, logits);'),1)
        self.assertIn('scalar_call',changed)
        self.assertEqual(changed.count('return std::vector<uint8_t>'),2)
        with self.assertRaises(ValueError):p.patch_lut('unbound source')

    def test_saved_cpp_noheap_exception_errno_and_overflow_receipts(self):
        x=json.loads((TRACK/'results/paired-allocation-observer-readiness-01/fixed-stack-test-result.json').read_text())
        self.assertEqual(x['synthetic_exit'],0)
        for key in ['logger_Cplusplus_new_and_link_wrapped_malloc_calloc_realloc_forbidden_test_passed','original_calls_and_return_values_preserved','original_exception_preserved','errno_snapshot_preserved_and_labelled_observation','overflow_diagnostic_checked','self_memory_and_rlimit_readbacks_observed','CLOEXEC_verified']:self.assertTrue(x[key])
        self.assertLessEqual(x['record_count'],64);self.assertLessEqual(x['bytes'],65536)
        self.assertFalse(x['full_model_or_phone_executed'])

    def test_old_AS_setting_absence_not_called_unlimited_or_causal(self):
        x=json.loads((TRACK/'results/paired-allocation-observer-readiness-01/retained-launch-AS-comparison.json').read_text())
        self.assertEqual(x['successful_entry']['AS_setting_lines'],[])
        self.assertEqual(x['failed_entry']['AS_setting_lines'],['ulimit -v 8388608 || exit 72'])
        self.assertIsNone(x['successful_entry']['actual_kernel_limit_readback'])
        self.assertIsNone(x['failed_entry']['actual_kernel_limit_readback'])
        self.assertFalse(x['same_runtime_binary_claimed'])

    def test_failed_run_preserves_zero_graphs_and_unknown_allocation(self):
        x=json.loads((TRACK/'results/paired-prefill-checkpoint-02/result.json').read_text())
        self.assertEqual(x['actual_native_exit'],1);self.assertEqual(x['graph_executions'],0)
        self.assertEqual(x['captured_payloads'],0);self.assertFalse(x['host_reference_started'])
        self.assertTrue(x['raw_pull_completed']);self.assertTrue(x['phone_lock_released'])
        self.assertEqual(x['cleanup'],'verified_absent');self.assertEqual(x['signal_operations'],0)
        self.assertEqual(x['postquery_IDs']['count'],1929)
        self.assertFalse(x['allocation_diagnosis']['AS_sole_cause_established'])
        self.assertFalse(x['allocation_diagnosis']['cap_underflow_demonstrated'])

    def test_allocation_adapter_is_plan_only_with_same_caps(self):
        a=importlib.import_module('phone_allocation_stage_capture');module,receipt=a.load_adapter();lifecycle,_=module.load_lifecycle({},False);plan=lifecycle.plan()
        self.assertFalse(receipt['AS_limit_token_cap_and_cleanup_budgets_changed'])
        self.assertEqual(plan['adb_calls'],0);self.assertFalse(plan['phone_permission_granted_by_plan'])
        self.assertEqual(plan['process_deadline_seconds'],300)
        self.assertEqual(plan['phone_address_space_limit_bytes'],8*1024**3)
        self.assertEqual(plan['reviewed_stage_digest'],a.DIGEST)


if __name__=='__main__':unittest.main()
