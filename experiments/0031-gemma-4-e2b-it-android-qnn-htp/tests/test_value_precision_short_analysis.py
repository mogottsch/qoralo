"""Saved-only synthetic receipts; no ADB, model or tokenizer execution."""
import importlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

TRACK = Path(__file__).resolve().parents[1]/'improvements/0001-long-collapse-speed-quality'
sys.path.insert(0, str(TRACK/'tools'))
a = importlib.import_module('analyze_value_precision_short')


class ValueAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.collection = {'reviewed_stage_digest': a.scope.STAGE_DIGEST, 'identity_verified': True,
            'input_hashes_verified': True, 'process_exit_code': 0, 'raw_pull_completed': True,
            'cleanup': 'verified_absent', 'process_cleanup': {'all_absent': True}, 'phone_lock_released': True}
        self.obs = {'query_completion_observed_beyond_exit_code': True,
            'prompt': {'rendered_bytes_exact_in_runtime_stdout': True, 'single_bos_prefix_observed': True,
                       'profile_prompt_tokens': 170, 'runtime_prefix_observations': [{'matches_bound_prefix': True}]},
            'stop': {'configured_ceiling_observed': 16}, 'actual_generated_tokens': 16, 'execution_markers': {}}
        self.commands = [{'operation': x, 'lock_held': True, 'lock_fd_inheritable': False}
                         for x in ('raw.pull', 'cleanup.remove')]
        self.manifest = {'context_sha256': a.scope.CONTEXT_SHA}

    def issues(self):
        return a.validation_issues(self.collection, self.obs, self.commands, self.manifest)

    def test_missing_optional_profile_values_and_early_stop_remain_valid(self):
        self.assertEqual(self.issues(), [])
        self.obs['prompt']['profile_prompt_tokens'] = None
        self.obs['actual_generated_tokens'] = None
        self.assertEqual(self.issues(), [])
        self.obs['actual_generated_tokens'] = 8
        self.assertEqual(self.issues(), [])

    def test_actual_ceiling_count_and_input_errors_rejected(self):
        self.obs['actual_generated_tokens'] = 17
        self.assertTrue(self.issues())
        self.obs['actual_generated_tokens'] = 16
        self.obs['prompt']['profile_prompt_tokens'] = 171
        self.assertTrue(self.issues())

    def test_source_and_lifecycle_binding_required(self):
        self.collection['reviewed_stage_digest'] = 'wrong'
        self.assertTrue(self.issues())
        self.collection['reviewed_stage_digest'] = a.scope.STAGE_DIGEST
        self.commands.reverse()
        self.assertTrue(self.issues())
        self.commands.reverse()
        self.commands[0]['lock_fd_inheritable'] = True
        self.assertTrue(self.issues())

    def test_observation_globals_do_not_mutate_historical_helper(self):
        helper, observe = a.load_helpers()
        self.assertEqual(observe.__globals__['FROZEN'], a.STAGE)
        self.assertNotEqual(helper.FROZEN, a.STAGE)
        self.assertIs(observe.__code__, helper.observations.__code__)

    def test_partial_raw_survives_parser_failure_and_private_battery_is_not_copied(self):
        helper, _ = a.load_helpers()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); run = root/'.local/value-precision-phone-short-runs/fake'
            (run/'raw/commands').mkdir(parents=True)
            (run/'raw/device').mkdir()
            (run/'raw/device/short-output.txt').write_text('retained partial output')
            (run/'collection.json').write_text(json.dumps(self.collection))
            private = run/'raw/commands/0001-telemetry.before.battery.stdout'
            private.write_text('level: 50\ntemperature: 320\nPRIVATE_LEARNED_SLEEP_SENTINEL\n')
            stage = root/'stage'; stage.mkdir()
            (stage/'frozen-manifest.json').write_text(json.dumps(self.manifest))
            dest = root/'results/value-precision-path-phone-short-test'
            argv = ['saved-analysis', '--run-dir', str(run), '--result-dir', str(dest)]
            with patch.object(a, 'TRACK', root), patch.object(a, 'STAGE', stage), \
                 patch.object(a.scope, 'STAGE_DIGEST', a.sha(stage/'frozen-manifest.json')), \
                 patch.object(a, 'load_helpers', return_value=(helper, Mock(side_effect=FileNotFoundError('missing profile/log')))), \
                 patch.object(sys, 'argv', argv):
                a.main()
            self.assertEqual((dest/'raw/controller/raw/device/short-output.txt').read_text(), 'retained partial output')
            self.assertFalse((dest/'raw/controller/raw/commands'/private.name).exists())
            self.assertIn('PRIVATE_LEARNED_SLEEP_SENTINEL', private.read_text())
            report = json.loads((dest/'result.json').read_text())
            self.assertTrue(report['analysis_issues'])
            self.assertIsNone(report['operating_context']['battery_core_extracts']['before']['usb_powered'])
            self.assertEqual(report['output_sanity'], {'looks_sensible': None, 'issue_notes': None})
            self.assertTrue((dest/'SHA256SUMS').exists())
            for path in dest.rglob('*'):
                if path.is_file(): self.assertNotIn('PRIVATE_LEARNED_SLEEP_SENTINEL', path.read_text())


if __name__ == '__main__':
    unittest.main()
