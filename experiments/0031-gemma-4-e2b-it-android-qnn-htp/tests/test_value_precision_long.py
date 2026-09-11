"""Host-only new-candidate exact-long bindings."""
import importlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

TRACK = Path(__file__).resolve().parents[1]/'improvements/0001-long-collapse-speed-quality'
sys.path.insert(0, str(TRACK/'tools'))
preparer = importlib.import_module('prepare_value_precision_long_stage')


class LongPreparationTests(unittest.TestCase):
    def test_inverse_reconstructs_original_and_script_is_unchanged(self):
        module, source = preparer.load_preparer()
        for before, after in reversed(preparer.REPLACEMENTS):
            self.assertEqual(source.count(after), 1)
            source = source.replace(after, before)
        self.assertEqual(source, preparer.LEGACY.read_text())
        old = importlib.import_module('prepare_long_genie_stage')
        self.assertEqual(module.SCRIPT, old.SCRIPT)
        self.assertEqual(module.SCRIPT.count('dialog query'), 1)
        self.assertIn('dialog setMaxNumTokens dialog1 2048', module.SCRIPT)
        self.assertNotIn('prompts/short.txt', module.SCRIPT)

    def test_only_new_physical_short_result_can_satisfy_prerequisite(self):
        with patch.object(preparer, 'SHORT_RESULT_SHA', '0'*64):
            with self.assertRaisesRegex(RuntimeError, 'short result changed'):
                preparer.load_preparer()


class LongLifecycleTests(unittest.TestCase):
    def test_inverse_materialization_and_default_plan(self):
        adapter = importlib.import_module('phone_value_precision_long')
        source, shell, changes, _ = adapter.materialize_sources()
        for old, new, count in reversed(changes):
            self.assertEqual(source.count(new), count)
            source = source.replace(new, old)
        original_source, original_shell, _, _ = adapter.short.materialize_sources()
        self.assertEqual(source, original_source)
        self.assertEqual(shell.replace('exact-long.script', 'first-short.script'), original_shell)
        lifecycle, receipt = adapter.load_lifecycle()
        plan = lifecycle.Controller().run()
        self.assertTrue(plan['long_script'])
        self.assertEqual(plan['reviewed_stage_digest'], adapter.STAGE_DIGEST)
        self.assertEqual(plan['adb_calls'], 0)
        self.assertFalse(plan['phone_permission_granted_by_plan'])
        self.assertEqual(receipt['short_result_commit'], 'df07102')

    def test_short_digest_cannot_authorize_long(self):
        adapter = importlib.import_module('phone_value_precision_long')
        lifecycle, _ = adapter.load_lifecycle()
        with self.assertRaises(lifecycle.GuardError):
            lifecycle.Controller().run(execute=True, reviewed_digest=adapter.short.STAGE_DIGEST,
                                       pi_slot='fake', run_id='fake')

    def test_long_fake_timeout_uses_same_lock_and_scoped_identity(self):
        adapter = importlib.import_module('phone_value_precision_long')
        base = importlib.import_module('test_phone_return_controller')
        long_tests = importlib.import_module('test_phone_return_long')
        lifecycle, _ = adapter.load_lifecycle()
        with tempfile.TemporaryDirectory() as directory, patch.object(base, 'module', lifecycle):
            root = Path(directory); stage = root/'stage'; stage.mkdir()
            (stage/'SHA256SUMS').write_text('fake\n')
            fake = long_tests.LongFake(); fake.mode = 'hang'
            clock = base.FakeClock(); clock.fast = True
            controller = lifecycle.Controller(stage=stage, output_root=root/'runs', slot_root=root/'slots',
                lock_path=root/'phone.lock', transport=fake, clock=clock,
                stage_verifier=lambda *args: {'files': {'bin/genie-app': {}, 'exact-long.script': {}}})
            fake.controller = clock.controller = controller
            result = controller.run(execute=True, reviewed_digest=adapter.STAGE_DIGEST,
                                    pi_slot='fake-slot', run_id='fake-long')
            self.assertEqual(result['process_timeout'], 'host_1800s_deadline')
            self.assertEqual(result['cleanup'], 'verified_absent')
            self.assertTrue(result['raw_pull_completed'])
            self.assertTrue(result['phone_lock_released'])
            self.assertIsNone(result['runtime_success'])
            self.assertFalse(result['signal_guard_atomic'])
            signals = [argv[-1] for op, argv, _ in fake.calls if op.startswith('signal.')]
            self.assertTrue(signals)
            self.assertTrue(all('exact-long.script' in text and 'first-short.script' not in text for text in signals))


class LongAnalysisScopeTests(unittest.TestCase):
    def test_observation_inverse_and_isolated_stage(self):
        import inspect
        analysis = importlib.import_module('analyze_value_precision_long')
        observe, _, source, _ = analysis.adapted_functions()
        restored = source.replace('2048', '16').replace('1929', '170').replace('long', 'short')
        self.assertEqual(restored, inspect.getsource(analysis.old_short.observations))
        self.assertEqual(observe.__globals__['FROZEN'], analysis.STAGE)
        self.assertNotEqual(analysis.old_short.FROZEN, analysis.STAGE)

    def test_long_validation_accepts_missing_optional_profile_not_wrong_input(self):
        analysis = importlib.import_module('analyze_value_precision_long')
        _, validate, _, _ = analysis.adapted_functions()
        fixtures = importlib.import_module('test_value_precision_short_analysis').ValueAnalysisTests()
        fixtures.setUp()
        fixtures.collection['reviewed_stage_digest'] = analysis.scope.STAGE_DIGEST
        fixtures.obs['prompt']['profile_prompt_tokens'] = 1929
        fixtures.obs['actual_generated_tokens'] = 2048
        fixtures.obs['stop']['configured_ceiling_observed'] = 2048
        self.assertEqual(validate(fixtures.collection, fixtures.obs, fixtures.commands, fixtures.manifest), [])
        fixtures.obs['actual_generated_tokens'] = None
        fixtures.obs['prompt']['profile_prompt_tokens'] = None
        self.assertEqual(validate(fixtures.collection, fixtures.obs, fixtures.commands, fixtures.manifest), [])
        fixtures.obs['prompt']['profile_prompt_tokens'] = 1928
        self.assertTrue(validate(fixtures.collection, fixtures.obs, fixtures.commands, fixtures.manifest))


if __name__ == '__main__':
    unittest.main()
