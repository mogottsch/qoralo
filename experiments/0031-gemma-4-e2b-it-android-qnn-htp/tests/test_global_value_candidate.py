"""Host candidate gate regressions; no SDK, model execution, or phone required."""
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

EXP = Path(__file__).resolve().parents[1]
TRACK = EXP / 'improvements/0001-long-collapse-speed-quality'
spec = importlib.util.spec_from_file_location('inspect_global_value', TRACK / 'tools/inspect_global_value_dlc.py')
inspection = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inspection)


def fixture(path, *, changed=True, wrong_output=False, unrelated=False):
    with path.open('w', newline='') as dst:
        writer = csv.writer(dst)
        writer.writerow(['Id', 'Name', 'Type', 'Inputs', 'Outputs', 'Out Dims', 'Runtimes', 'Parameters'])
        writer.writerow(['0', 'convert0', 'Convert', 'a', 'b', '1', 'D', ''])
        writer.writerow(['', '', '', '', '', '', '', 'extra parameters do not count as ops'])
        for role, suffix in [('Input', 'in'), ('Output', 'out')]:
            writer.writerow([role + ' Name', 'Dimensions', 'Type', 'Encoding Info'])
            for layer in (4, 9, 14):
                datatype = 'Float_16' if changed else 'uFxp_16'
                if wrong_output and role == 'Output' and layer == 9:
                    datatype = 'uFxp_16'
                writer.writerow([f'past_value_{layer}_h0_{suffix}', '1,1,1,512', datatype,
                                 '' if datatype == 'Float_16' else 'scale=0.1'])
            writer.writerow([f'swa_key_0_h0_{suffix}', '1,1,256,1', 'uFxp_16',
                             'changed' if unrelated else 'scale=0.2'])
        writer.writerow(['Total parameters: 10'])


class CandidateGateTest(unittest.TestCase):
    def compare(self, **kwargs):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root / 'ar1.csv', changed=False)
            fixture(root / 'candidate.csv', **kwargs)
            with patch.object(inspection, 'BASE', root):
                return inspection.compare(1, root / 'candidate.csv')

    def test_expected_fp16_inputs_and_outputs_pass(self):
        result = self.compare()
        self.assertTrue(result['datatype_scope_passed'])
        self.assertEqual(6, len(result['selected_cache_interfaces']))
        self.assertEqual(1, result['candidate_operator_count'])
        self.assertFalse(result['full_htp_delegation_proven'])

    def test_inherited_quantized_output_fails_even_with_fp16_inputs(self):
        result = self.compare(wrong_output=True)
        self.assertFalse(result['datatype_scope_passed'])
        self.assertIn('past_value_9_h0_out: wanted Float_16, observed uFxp_16', result['issues'])

    def test_removing_encodings_without_converted_dtype_change_fails(self):
        result = self.compare(changed=False)
        self.assertFalse(result['datatype_scope_passed'])
        self.assertEqual(6, len(result['issues']))

    def test_unselected_interface_change_fails(self):
        result = self.compare(unrelated=True)
        self.assertFalse(result['datatype_scope_passed'])
        self.assertTrue(any('unselected interface changed' in issue for issue in result['issues']))

    def test_failed_attempts_are_retained_and_preconversion(self):
        for ordinal in (1, 2, 3):
            folder = TRACK / f'results/global-value-fp16-attempt-{ordinal:02d}'
            result = json.loads((folder / 'result.json').read_text())
            self.assertFalse(result['conversion_started'])
            self.assertFalse(result['phone_access'])
            for line in (folder / 'SHA256SUMS').read_text().splitlines():
                digest, name = line.split('  ', 1)
                self.assertEqual(digest, hashlib.sha256((folder / name).read_bytes()).hexdigest())

    def test_app_priority_interruption_is_not_model_or_fidelity_failure(self):
        folder = TRACK / 'results/global-value-fp16-attempt-04'
        result = json.loads((folder / 'result.json').read_text())
        self.assertEqual('app_priority_interruption_not_model_failure', result['classification'])
        self.assertTrue(result['outcome']['patch_validation_passed'])
        self.assertTrue(result['outcome']['ar1_conversion_started'])
        self.assertFalse(result['outcome']['ar1_conversion_completed'])
        self.assertFalse(result['outcome']['ar128_conversion_started'])
        self.assertEqual(0, result['outcome']['dlc_count'])
        self.assertFalse(result['outcome']['compile_started'])
        self.assertFalse(result['outcome']['automatic_restart'])
        self.assertTrue(result['outcome']['owned_process_group_empty_after_stop'])
        self.assertEqual(-15, result['outcome']['supervisor_exit']['exit_code'])
        self.assertIsNone(result['unmeasured']['actual_dlc_cache_signatures'])
        self.assertIsNone(result['unmeasured']['unsupported_or_fallback_count'])
        self.assertIsNone(result['unmeasured']['host_trajectory_or_fidelity'])
        self.assertFalse(result['publication']['registry_eligible'])
        for ar, item in zip((1, 128), result['patch']['independent_scope_validation']['variants']):
            expected = {f'past_value_{i}_h0_in' for i in (4, 9, 14)}
            if ar == 1:
                expected |= {f'past_value_{i}_h0_out' for i in (4, 9, 14)}
            self.assertEqual(expected, set(item['exact_removed_encodings']))
            self.assertTrue(item['other_encodings_unchanged'])
            self.assertTrue(item['weight_initializers_unchanged'])
        for line in (folder / 'SHA256SUMS').read_text().splitlines():
            digest, name = line.split('  ', 1)
            self.assertEqual(digest, hashlib.sha256((folder / name).read_bytes()).hexdigest())

    def test_attempt05_ar1_csv_gate_and_ar128_storage_failure_are_separate(self):
        folder = TRACK / 'results/global-value-fp16-attempt-05'
        result = json.loads((folder / 'result.json').read_text())
        self.assertEqual('partial_ar1_fp16_dlc_success_ar128_tmpfs_exhaustion', result['classification'])
        self.assertTrue(result['outcome']['ar1_conversion_completed'])
        self.assertTrue(result['outcome']['ar128_conversion_started'])
        self.assertFalse(result['outcome']['ar128_conversion_completed'])
        self.assertFalse(result['failure']['numerical_or_model_failure'])
        observed = inspection.compare(1, folder / 'raw/inspection-02/ar1.csv.gz',
                                      folder / 'raw/baseline-ar1.csv.gz')
        self.assertEqual(observed, result['ar1_interface_inspection'])
        self.assertTrue(observed['datatype_scope_passed'])
        self.assertEqual(0, observed['convert_count_delta'])
        self.assertEqual(31, observed['candidate_operator_counts']['Convert'])
        self.assertEqual(6875, observed['candidate_operator_count'])
        self.assertEqual(38, len(observed['candidate_io']['input']))
        self.assertEqual(31, len(observed['candidate_io']['output']))
        self.assertEqual(81, result['float_precision_fallback_observation']['candidate_count'])
        self.assertEqual(75, result['float_precision_fallback_observation']['baseline_count'])
        self.assertIsNone(result['unmeasured']['full_htp_delegation'])
        self.assertIsNone(result['unmeasured']['host_fidelity'])
        self.assertTrue(result['scratch_cleanup']['verified_absent'])
        self.assertFalse(result['publication']['registry_eligible'])
        for line in (folder / 'SHA256SUMS').read_text().splitlines():
            digest, name = line.split('  ', 1)
            self.assertEqual(digest, hashlib.sha256((folder / name).read_bytes()).hexdigest())

    def test_new_attempt_cannot_overwrite_previous_artifacts(self):
        source = (TRACK / 'tools/convert_global_value_fp16.py').read_text()
        self.assertIn('refusing to overwrite an earlier attempt', source)
        self.assertIn('exist_ok=False', source)
        self.assertNotIn('destination.unlink(', source)
        self.assertIn('if ar == 1:', source)


if __name__ == '__main__':
    unittest.main()
