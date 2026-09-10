"""Offline regression checks of retained GateA evidence; no device/runtime calls."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

EXP = Path(__file__).resolve().parents[1]
TRACK = EXP / 'improvements/0001-long-collapse-speed-quality'
ROOT = TRACK / 'results/phone-return-short-attempt-01'
spec = importlib.util.spec_from_file_location('short_analysis', TRACK / 'tools/analyze_phone_return_short.py')
analysis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analysis)


class PhysicalShortTest(unittest.TestCase):
    def setUp(self):
        self.result = json.loads((ROOT / 'result.json').read_text())

    def test_actual_query_provider_and_effective_input_not_exit_code_only(self):
        r = self.result
        self.assertEqual([], r['analysis_issues'])
        obs = r['observations']
        self.assertTrue(obs['query_completion_observed_beyond_exit_code'])
        m = obs['execution_markers']
        self.assertEqual(1, m['query_enter'])
        self.assertEqual(1, m['query_return'])
        self.assertEqual(1, m['context_deserialized'])
        self.assertEqual(2, m['ar128_completed_status0'])
        self.assertEqual(15, m['ar1_completed_status0'])
        self.assertEqual(17, m['graph_execute_status0'])
        self.assertEqual(0, m['graph_execute_nonzero_status'])
        self.assertEqual(1, m['smart_mask_selected'])
        self.assertEqual(0, m['cache_quantization_error'])
        self.assertEqual(0, m['cpu_backend_markers'])
        self.assertEqual(0, m['runtime_fallback_markers'])
        self.assertEqual(170, obs['prompt']['profile_prompt_tokens'])
        self.assertTrue(obs['prompt']['rendered_bytes_exact_in_runtime_stdout'])
        for prefix in obs['prompt']['runtime_prefix_observations']:
            self.assertEqual(157, prefix['complete_token_count'])
            self.assertTrue(prefix['matches_bound_prefix'])
            self.assertEqual([2, 105], prefix['complete_prefix'][:2])
        self.assertEqual(16, obs['actual_generated_tokens'])
        self.assertTrue(obs['stop']['ceiling_reached'])
        self.assertIsNone(obs['stop']['explicit_runtime_stop_reason'])

    def test_exact_output_sanity_and_no_long_or_speed_acceptance(self):
        r = self.result
        output = ROOT / r['observations']['output']['path']
        self.assertEqual(89, output.stat().st_size)
        self.assertEqual('70711436da1fba6f0b7d869c319f8d97c0819d36affbd369e119c1c3f04d6357',
                         hashlib.sha256(output.read_bytes()).hexdigest())
        self.assertEqual({'looks_sensible': True, 'issue_notes': None}, r['output_sanity'])
        self.assertTrue(r['baseline_short_prefix_comparison']['byte_identical'])
        self.assertTrue(r['publication']['gate_a_compatibility_only'])
        self.assertFalse(r['publication']['long_repetition_acceptance'])
        self.assertFalse(r['publication']['speed_acceptance'])
        self.assertFalse(r['publication']['registry_eligible'])
        self.assertIsNone(r['observations']['raw_genie_profile']['normalized_decode_tokens_per_second'])

    def test_optional_profile_loss_does_not_erase_raw_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            raw = Path(directory)
            device = raw / 'raw/device'
            device.mkdir(parents=True)
            for name in ('genie-verbose.log', 'runner.stdout', 'short-output.txt'):
                shutil.copy2(ROOT / 'raw/controller/raw/device' / name, device / name)
            obs = analysis.observations(raw, raw / 'raw/commands')
            self.assertTrue(obs['query_completion_observed_beyond_exit_code'])
            self.assertIsNone(obs['actual_generated_tokens'])
            self.assertIsNone(obs['stop']['ceiling_reached'])
            self.assertTrue(obs['raw_genie_profile']['profile_error'])
            self.assertIsNone(obs['raw_genie_profile']['normalized_decode_tokens_per_second'])

    def test_cleanup_and_private_battery_boundary(self):
        r = self.result
        self.assertTrue(r['cleanup']['remote_root_absent'])
        self.assertTrue(r['cleanup']['recorded_role_pids_absent'])
        self.assertTrue(r['cleanup']['lock_released'])
        self.assertEqual(0, r['cleanup']['signal_commands_issued'])
        self.assertEqual(44, r['cleanup']['adb_calls'])
        self.assertTrue(r['cleanup']['all_adb_calls_lock_guarded'])
        self.assertTrue(r['cleanup']['raw_pull_before_cleanup'])
        self.assertFalse(r['cleanup']['native_live_pid_sampled'])
        self.assertEqual(2, len(r['privacy_retention']['private_originals']))
        self.assertEqual([], list((ROOT / 'raw/controller/raw/commands').glob('*-telemetry.*.battery.stdout')))
        for phase in ('before', 'after'):
            battery = json.loads((ROOT / f'derived/battery-{phase}.json').read_text())
            self.assertEqual(69, battery['level_percent'])
            self.assertEqual(31.9, battery['temperature_c'])
            self.assertTrue(battery['usb_powered'])
            self.assertEqual({'level_percent', 'temperature_c', 'voltage_mv', 'usb_powered', 'scope'}, set(battery))
        self.assertEqual(0, r['operating_context']['thermal']['before']['status'])
        self.assertEqual(0, r['operating_context']['thermal']['after']['status'])
        self.assertIsNone(r['memory']['process_pss'])

    def test_public_evidence_hashes(self):
        for line in (ROOT / 'SHA256SUMS').read_text().splitlines():
            digest, name = line.split('  ', 1)
            self.assertEqual(digest, hashlib.sha256((ROOT / name).read_bytes()).hexdigest())


if __name__ == '__main__':
    unittest.main()
