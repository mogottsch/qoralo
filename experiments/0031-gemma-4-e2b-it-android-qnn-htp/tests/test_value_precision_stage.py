import hashlib
import importlib.util
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[1]/'improvements/0001-long-collapse-speed-quality/tools/prepare_value_precision_stage.py'
spec = importlib.util.spec_from_file_location('value_stage', PATH)
stage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage)


class ValueStageTests(unittest.TestCase):
    def test_only_four_fixed_bindings_change_and_inverse_is_exact(self):
        original = stage.LEGACY.read_text()
        adapted = stage.materialize(original)
        for before, after in reversed(stage.REPLACEMENTS):
            self.assertEqual(adapted.count(after), 1)
            adapted = adapted.replace(after, before)
        self.assertEqual(adapted, original)
        self.assertEqual(hashlib.sha256(adapted.encode()).hexdigest(), stage.LEGACY_SHA)

    def test_modified_legacy_source_rejected(self):
        with self.assertRaises(ValueError):
            stage.materialize(stage.LEGACY.read_text()+'\n')

    def test_loaded_copy_does_not_import_model_or_change_request(self):
        module, source = stage.load_preparer()
        self.assertEqual(module.CONTEXT_SHA, stage.CONTEXT_SHA)
        self.assertEqual(module.COMPILE_RESULT_SHA, stage.RESULT_SHA)
        self.assertIn('dialog setMaxNumTokens dialog1 16', module.SCRIPT)
        self.assertEqual(module.SCRIPT.count('dialog query'), 1)
        self.assertEqual(module.INPUTS['short']['tokens'], 170)
        self.assertEqual(module.INPUTS['long']['tokens'], 1929)
        self.assertEqual(hashlib.sha256(stage.LEGACY.read_bytes()).hexdigest(), stage.LEGACY_SHA)


if __name__ == '__main__':
    unittest.main()
