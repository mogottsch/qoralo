"""One retained physical trace plus host-only app-guard regression checks."""
import hashlib
import importlib
import json
from pathlib import Path
import struct
import sys
import unittest

TRACK=Path(__file__).resolve().parents[1]/'improvements/0001-long-collapse-speed-quality'
RESULT=TRACK/'results/selected-id-phone-long-attempt-01'
sys.path.insert(0,str(TRACK/'tools'))


class SavedTraceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result=json.loads((RESULT/'result.json').read_text())
        cls.correlation=json.loads((RESULT/'accepted-generation-correlation.json').read_text())

    def test_complete_genuine_generation_ids_without_50_or_configured_eos(self):
        parser=importlib.import_module('analyze_selected_id_trace')
        raw=parser.summarize((RESULT/'raw/controller/raw/device/runner.stderr').read_text(),2048)
        self.assertFalse(raw['trace_errors'])
        self.assertTrue(raw['coverage_complete_against_profile'])
        records=self.correlation['accepted_generation_records']
        self.assertEqual(len(records),2048)
        self.assertFalse(self.correlation['excluded_unpromoted_observations'])
        self.assertTrue(self.correlation['accepted_generation_coverage_complete'])
        self.assertEqual([r['token'] for r in records],[r['token'] for r in raw['records']])
        self.assertTrue(all(r['token'] not in (1,50,106) for r in records))
        self.assertEqual([r['ordinal'] for r in records],list(range(2048)))
        self.assertTrue(all(r['n_past']==1929+max(0,r['ordinal']-1) for r in records))
        self.assertIsNone(self.correlation['internal_stop_decision'])
        data=(RESULT/'accepted-selected-ids.int32le').read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(),'8a78560be15953ec6e41bb3f20606c4572d18cc30ebe233309d344cee6d150bc')
        self.assertEqual(list(struct.unpack('<2048i',data)),[r['token'] for r in records])

    def test_actual_primary_phase_and_order_not_prefill_or_proposals(self):
        bound=json.loads((RESULT/'basic-scope-binding.json').read_text())
        self.assertTrue(bound['confirmed'])
        self.assertTrue(all(bound['checks'].values()))
        records=self.correlation['accepted_generation_records']
        self.assertEqual(records[0]['phase'],'first_generated_after_complete_prefill')
        self.assertEqual(records[0]['producer_execution_index'],15)
        self.assertEqual(records[1]['primary_decode_step'],1)
        self.assertEqual(records[-1]['producer_execution_index'],2062)
        marker=self.result['observations']['execution_markers']
        self.assertEqual((marker['ar128_completed_status0'],marker['ar1_completed_status0']),(16,2047))
        self.assertEqual(marker['query_enter'],1)
        self.assertEqual(marker['query_return'],1)
        for k in ('cpu_backend_markers','runtime_fallback_markers','graph_execute_nonzero_status','cache_quantization_error'):
            self.assertEqual(marker[k],0)

    def test_full_input_parity_and_same_visible_negative_without_equivalence(self):
        parity=self.result['input_parity']
        self.assertTrue(parity['exact_frozen_input_ids_equal'])
        self.assertEqual(parity['tokens'],1929)
        self.assertEqual(parity['int32le_sha256'],'3b5c04febbc9d55c529ee7ece510607203dbdc8256a6abc05ba0498cf4e52b64')
        comparison=self.result['visible_comparison_to_f11df93']
        self.assertTrue(comparison['visible_bytes_equal'])
        self.assertFalse(comparison['runtime_equivalence_established'])
        output=RESULT/self.result['observations']['output']['path']
        self.assertEqual(hashlib.sha256(output.read_bytes()).hexdigest(),comparison['reference_output_sha256'])
        self.assertFalse(self.result['output_sanity']['looks_sensible'])
        metrics=self.result['accepted_generation_trace']['direct_selected_id_metrics']
        self.assertIsNone(metrics['rolling_collapse_onset'])
        self.assertEqual(metrics['exact_periodic_suffix']['period_tokens'],44)
        self.assertEqual(metrics['exact_periodic_suffix']['suffix_tokens'],1488)
        self.assertIsNone(self.result['observations']['stop']['explicit_runtime_stop_reason'])

    def test_full_guarded_cleanup_and_absent_watchdog_not_a_delivered_signal(self):
        c=self.result['cleanup']
        self.assertEqual(c['adb_calls'],277)
        for k in ('all_calls_locked_noninheritable','raw_pull_before_root_removal','all_scoped_roles_absent','remote_root_absent','phone_lock_released'):
            self.assertTrue(c[k])
        self.assertEqual(c['signal_guard_events'],[{'operation':'signal.watchdog.TERM','response':'ABSENT','command_exit':0,'delivered_signal_observed':False}])
        self.assertFalse(c['signal_guard_atomic'])
        self.assertEqual(len(self.result['private_battery_originals']),2)
        for item in self.result['private_battery_originals']:
            self.assertFalse((RESULT/'raw/controller/raw/commands'/Path(item['private_original_path']).name).exists())
        self.assertFalse(self.result['registry_eligible'])
        self.assertFalse(self.result['speed_acceptance'])


class AppGuardTests(unittest.TestCase):
    def test_identity_and_quiescence_fail_without_changing_app_or_starting_model(self):
        guard=importlib.import_module('phone_selected_id_appguard')
        text=''.join(f'APK\t{k}\t{v}\n' for k,v in guard.EXPECTED.items())
        text+=''.join(f'PID\t{k}\t\n' for k in list(guard.EXPECTED)+['dev.vibevoice.podcast.internal:generation'])
        self.assertTrue(guard.validate(text.encode(),True)['target_processes_absent'])
        with self.assertRaises(ValueError):guard.validate(text.replace(next(iter(guard.EXPECTED.values())),'0'*64).encode(),True)
        with self.assertRaises(ValueError):guard.validate(text.replace('PID\tdev.vibevoice.podcast.internal:generation\t\n','PID\tdev.vibevoice.podcast.internal:generation\t123\n').encode(),True)
        with self.assertRaises(ValueError):guard.validate(b'',True)
        self.assertNotIn('force-stop',guard.IDENTITY+guard.QUIESCENCE)
        self.assertNotIn('kill ',guard.IDENTITY+guard.QUIESCENCE)


if __name__=='__main__':unittest.main()
