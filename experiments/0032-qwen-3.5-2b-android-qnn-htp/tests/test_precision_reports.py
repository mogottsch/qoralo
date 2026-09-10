from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "precision_reports", EXP / "tools/compare_precision_reports.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PrecisionReportsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline = json.loads(
            (EXP / "results/host-histogram-precision-20260910/baseline/hidden-comparison.json").read_text()
        )

    def test_self_comparison_preserves_all_73_outputs(self):
        report = module.summarize_reports(self.baseline, self.baseline)
        self.assertEqual(73, len(report["outputs"]))
        self.assertEqual(24, report["hidden_layers_compared"])
        self.assertEqual(0, report["hidden_layers_with_higher_cosine"])
        self.assertTrue(report["all_outputs_finite"])
        self.assertTrue(all(row["cosine_delta"] == 0 for row in report["outputs"]))

    def test_different_prompt_position_is_rejected(self):
        candidate = copy.deepcopy(self.baseline)
        candidate["token_position"] = 173
        with self.assertRaisesRegex(ValueError, "token_position"):
            module.summarize_reports(self.baseline, candidate)

    def test_different_input_token_is_rejected(self):
        candidate = copy.deepcopy(self.baseline)
        candidate["token_id"] = 760
        with self.assertRaisesRegex(ValueError, "token_id"):
            module.summarize_reports(self.baseline, candidate)

    def test_swapped_layers_are_rejected(self):
        candidate = copy.deepcopy(self.baseline)
        candidate["outputs"][49], candidate["outputs"][50] = (
            candidate["outputs"][50], candidate["outputs"][49]
        )
        with self.assertRaisesRegex(ValueError, "identity"):
            module.summarize_reports(self.baseline, candidate)

    def test_missing_output_is_rejected(self):
        candidate = copy.deepcopy(self.baseline)
        candidate["outputs"].pop()
        with self.assertRaisesRegex(ValueError, "count"):
            module.summarize_reports(self.baseline, candidate)

    def test_geometry_mismatch_is_rejected(self):
        candidate = copy.deepcopy(self.baseline)
        candidate["outputs"][0]["qnn_x86"]["shape"] = [1]
        with self.assertRaisesRegex(ValueError, "geometry"):
            module.summarize_reports(self.baseline, candidate)

    def test_nonfinite_observation_is_retained_not_hidden(self):
        candidate = copy.deepcopy(self.baseline)
        candidate["outputs"][0]["qnn_x86"]["finite"] = False
        result = module.summarize_reports(self.baseline, candidate)
        self.assertFalse(result["all_outputs_finite"])


if __name__ == "__main__":
    unittest.main()
