import importlib
import json
from pathlib import Path
import sys
import unittest

TRACK=Path(__file__).resolve().parents[1]/'improvements/0001-long-collapse-speed-quality'
sys.path.insert(0,str(TRACK/'tools'))


class MappingObserverTests(unittest.TestCase):
    def test_injected_failure_proves_semantics_not_Android_cause(self):
        x=json.loads((TRACK/'results/paired-mapping-observer-readiness-01/injected-fixture-result.json').read_text())
        self.assertTrue(x['original_and_observed_results_equal'])
        self.assertTrue(x['forced_MAP_FAILED_ENOMEM_can_leave_open_return_true_pointer_null_size0'])
        self.assertFalse(x['fixture_proves_actual_Android_cause']);self.assertFalse(x['AS_changed']);self.assertFalse(x['phone_or_model_executed'])
        self.assertEqual(len(x['cases']),4)
        for case in x['cases']:
            self.assertEqual(case['exit'],0)
            if case['mode']=='observed':
                self.assertLessEqual(case['log_events'],32);self.assertLessEqual(case['log_bytes'],32768)
                self.assertTrue(case['CLOEXEC_and_no_authored_heap_calls_passed'])

    def test_mapping_failure_and_open_result_are_independently_recorded(self):
        p=TRACK/'results/paired-mapping-observer-readiness-01/synthetic/observed-1/mapping-stages.log'
        rows=[dict(item.split('=',1) for item in s.split()[1:]) for s in p.read_text().splitlines()]
        maps=[r for r in rows if r['phase']=='mmap.after'];opens=[r for r in rows if r['phase']=='file.open.return']
        self.assertEqual(len(maps),2);self.assertEqual(len(opens),2)
        self.assertTrue(all(r['address_is_MAP_FAILED']=='1' and r['errno_at_observation']=='12' for r in maps))
        self.assertTrue(all(r['File_open_return']=='1' and r['pointer_nonnull']=='0' and r['mapped_bytes']=='0' and r['isOpen']=='0' for r in opens))

    def test_logger_is_fixed_buffer_and_immediate_errno_source_is_preserved(self):
        header=(TRACK/'tools/mapping_stage_trace.hpp').read_text()
        for forbidden in ['std::string','nlohmann','malloc(', 'calloc(', 'realloc(', 'operator new']:
            self.assertNotIn(forbidden,header)
        self.assertIn('errno=saved_errno',header);self.assertIn('s.events<32',header);self.assertIn('s.bytes<32768',header)
        source=(TRACK/'tools/prepare_mapping_stage_capture.py').read_text()
        self.assertIn('const int errno_immediately_after_mmap = errno;',source)
        self.assertIn('return actual;',source)
        p=importlib.import_module('prepare_mapping_stage_capture')
        with self.assertRaises(ValueError):p.patch_mmap('unbound source')

    def test_prior_snapshot_does_not_prove_earlier_mapping_failure(self):
        x=json.loads((TRACK/'results/paired-mapping-observer-readiness-01/result.json').read_text())
        r=x['prior_snapshot'];self.assertEqual(r['AS']-r['VmSize'],2246283264)
        self.assertGreater(r['PLE_file_bytes'],r['AS_headroom'])
        self.assertTrue(r['map_timing_is_earlier_than_snapshot']);self.assertFalse(r['that_difference_proves_AS_cause'])
        self.assertFalse(x['actual_Android_mapping_failure_proven'])

    def test_plan_uses_corrected_finish_hook_without_device_permission(self):
        a=importlib.import_module('phone_mapping_stage_capture');m,b=a.load_adapter();c,_=m.load_lifecycle({},False);plan=c.plan()
        self.assertIn('_finish_remote',c.Controller.__dict__);self.assertNotIn('_cleanup_root',c.Controller.__dict__)
        self.assertEqual(plan['adb_calls'],0);self.assertFalse(plan['phone_permission_granted_by_plan'])
        self.assertEqual(plan['reviewed_stage_digest'],a.DIGEST)
        self.assertEqual(plan['process_deadline_seconds'],300);self.assertEqual(plan['phone_address_space_limit_bytes'],8*1024**3)
        self.assertFalse(b['AS_model_caps_cleanup_budgets_changed'])


if __name__=='__main__':unittest.main()
