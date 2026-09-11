"""Host-only fixed-scope tests, reusing the original complete fake-ADB suite."""
import importlib
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

TRACK = Path(__file__).resolve().parents[1]/'improvements/0001-long-collapse-speed-quality'
sys.path.insert(0, str(TRACK/'tools'))
adapter = importlib.import_module('phone_value_precision_short')
original = importlib.import_module('phone_return_controller')
base_tests = importlib.import_module('test_phone_return_controller')


class ValueScopeTest(unittest.TestCase):
    def test_inverse_is_byte_exact_and_shell_is_unchanged(self):
        source, shell, changes, _ = adapter.materialize_sources()
        for old, new, count in reversed(changes):
            self.assertEqual(source.count(new), count)
            source = source.replace(new, old)
        self.assertEqual(source, (TRACK/'tools/phone_return_controller.py').read_text())
        self.assertEqual(shell, (TRACK/'tools/phone_return_shell.py').read_text())

    def test_changed_helper_rejected(self):
        with patch.object(adapter, 'COPY_HELPER_SHA', '0'*64):
            with self.assertRaisesRegex(RuntimeError, 'pinned lifecycle/helper'):
                adapter.materialize_sources()

    def test_changed_context_evidence_rejected(self):
        with patch.object(adapter, 'CONTEXT_RESULT_SHA', '0'*64):
            with self.assertRaisesRegex(RuntimeError, 'context evidence changed'):
                adapter.load_lifecycle()

    def test_plan_binds_new_stage_without_changing_old_scope(self):
        lifecycle, receipt = adapter.load_lifecycle()
        plan = lifecycle.Controller().run()
        self.assertEqual(plan['reviewed_stage_digest'], adapter.STAGE_DIGEST)
        self.assertEqual(plan['adb_calls'], 0)
        self.assertFalse(plan['long_script'])
        self.assertFalse(plan['phone_permission_granted_by_plan'])
        self.assertEqual(plan['process_deadline_seconds'], 1800)
        self.assertEqual(receipt['context_sha256'], adapter.CONTEXT_SHA)
        self.assertNotEqual(original.DIGEST, lifecycle.DIGEST)
        self.assertEqual(original.STAGE.name, 'stage-freeze-20260910T105830Z-01')

    def test_old_stage_cannot_authorize_new_candidate(self):
        lifecycle, _ = adapter.load_lifecycle()
        with self.assertRaises(lifecycle.GuardError):
            lifecycle.Controller().run(execute=True, reviewed_digest=original.DIGEST,
                                       pi_slot='fake', run_id='fake')


class ValueLifecycleTest(base_tests.ControllerTest):
    """Same adversarial lock/PID/raw-retention tests against the adapted module."""
    def setUp(self):
        lifecycle, _ = adapter.load_lifecycle()
        binding = patch.object(base_tests, 'module', lifecycle)
        binding.start()
        self.addCleanup(binding.stop)
        super().setUp()

    def test_receipt_direct_launch_and_new_remote_namespace(self):
        result = self.execute()
        self.assertEqual(result['scope_adapter']['stage_digest'], adapter.STAGE_DIGEST)
        self.assertTrue(result['remote_root'].startswith('/data/local/tmp/vibevoice-0031-value-'))
        launch = next(argv[-1] for op, argv, _ in self.fake.calls if op == 'process.launch')
        self.assertNotIn('&&', launch)
        self.assertNotIn('cd ', launch)
        self.assertIn(self.controller.remote+'/evidence/launcher.stdout', launch)
        self.assertFalse(result['long_script'])
        self.assertIsNone(result['runtime_success'])


if __name__ == '__main__':
    unittest.main()
