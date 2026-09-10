from __future__ import annotations

import json
import math
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[1] / 'tools'
sys.path.insert(0, str(TOOLS))
import conv_history_sweep as sweep


class SweepPreparationTest(unittest.TestCase):
    def test_neighbors_are_binary32_and_directional(self):
        for value in (-30., -.5, -0.0, 0.0, .5, 22.):
            self.assertLess(sweep.adjacent(value, -1), value)
            self.assertGreater(sweep.adjacent(value, 1), value)
            if value:
                self.assertEqual(value, sweep.adjacent(sweep.adjacent(value, 1), -1))
        self.assertEqual('01000000', struct.pack('<f', sweep.adjacent(0, 1)).hex())

    def test_neighbors_reject_nonfinite_and_invalid_direction(self):
        for value in (math.inf, -math.inf, math.nan):
            with self.assertRaises(ValueError): sweep.adjacent(value, 1)
        with self.assertRaises(ValueError): sweep.adjacent(1, 0)

    def test_actual_clipping_onsets_straddle_code_range(self):
        h = sweep.probe.case_spec('fullchain')['stages']['history']
        rows = {r['label']: r for r in sweep.sample_values()}
        for side, direction in [('upper', 1), ('lower', -1)]:
            value = rows[side + '_actual_clipping_onset_at']['value']
            self.assertTrue(sweep.scalar_qdq(value, h)['clipped'])
            self.assertFalse(sweep.scalar_qdq(sweep.adjacent(value, -direction), h)['clipped'])
            self.assertTrue(sweep.scalar_qdq(sweep.adjacent(value, direction), h)['clipped'])

    def test_endpoints_are_not_unbounded_code_clipping_onsets(self):
        h = sweep.probe.case_spec('fullchain')['stages']['history']
        rows = {r['label']: r for r in sweep.sample_values()}
        for side in ('upper', 'lower'):
            endpoint = rows[f'history_{side}_endpoint_at']['value']
            onset = rows[f'{side}_actual_clipping_onset_at']['value']
            self.assertNotEqual(endpoint, onset)
            self.assertFalse(sweep.scalar_qdq(endpoint, h)['clipped'])

    def test_upper_sweep_inside_final_range_and_lower_confound_explicit(self):
        out = sweep.probe.case_spec('fullchain')['stages']['output']
        bounds = sweep.scalar_qdq(0, out)
        rows = {r['label']: r for r in sweep.sample_values()}
        for row in rows.values():
            if row['family'] == 'above_history_within_final_range':
                self.assertLessEqual(row['value'], bounds['representable_max_fp32'])
                self.assertFalse(sweep.scalar_qdq(row['value'], out)['clipped'])
        self.assertTrue(sweep.scalar_qdq(rows['lower_minus_two_steps']['value'], out)['clipped'])

    def test_pack_changes_only_declared_slot3_channels(self):
        raw, rows = sweep.build_pack()
        before = (sweep.FIRST / 'raw/case/runtime/data/history.f32le').read_bytes()
        self.assertEqual(98304, len(raw[0])); self.assertEqual(24576, len(raw[1]))
        allowed = {c*4+3 for row in rows[:-1] for c in row['channels']}
        for index in range(24576):
            if index not in allowed:
                self.assertEqual(before[index*4:index*4+4], raw[0][index*4:index*4+4])
        self.assertEqual((sweep.FIRST / 'raw/case/runtime/data/projection.f32le').read_bytes(), raw[1])
        self.assertEqual([6053], rows[-1]['channels'])
        for row in rows[:-1]:
            self.assertEqual(3072, row['channels'][1] - row['channels'][0])
            for channel in row['channels']:
                self.assertEqual(row['value'], struct.unpack_from('<f', raw[0], (channel*4+3)*4)[0])

    def test_stage_outputs_match_full_array_oracle(self):
        raw, rows = sweep.build_pack()
        oracle = sweep.probe.oracle('fullchain', *raw)
        for row in rows:
            self.assertEqual(['history', 'concat', 'output'], [s['stage'] for s in row['fullchain_stages']])
            for channel in row['channels']:
                self.assertEqual(row['expected_output_fp32'], struct.unpack_from('<f', oracle, (channel*4+2)*4)[0])

    def test_frozen_route_is_exact_same_pte_and_receipts(self):
        route = sweep.frozen_route()
        self.assertEqual(sweep.PTE_SHA, route['pte']['sha256'])
        self.assertEqual(232144, route['pte']['bytes'])
        self.assertTrue(route['zero_executorch_tensor_fallback_receipt'])
        self.assertEqual(4, len(route['firstcase_receipts']))

    def test_changed_pte_identity_is_rejected_without_load(self):
        original = sweep.identity
        def wrong(path):
            result = original(path)
            if str(path).endswith('probe.pte'): result['sha256'] = '0'*64
            return result
        with patch.object(sweep, 'identity', side_effect=wrong):
            with self.assertRaisesRegex(ValueError, 'PTE bytes changed'): sweep.frozen_route()

    def test_failed_cpu_setup_preserves_inputs_oracles_and_forbids_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'failed'
            with patch.object(sweep.probe, 'cpu_torch', side_effect=RuntimeError('synthetic CPU setup error')):
                with self.assertRaisesRegex(RuntimeError, 'synthetic'): sweep.prepare(root)
            result = json.loads((root / 'result.json').read_text())
            self.assertEqual('error', result['status'])
            self.assertEqual(0, result['cpu_forwards'])
            self.assertEqual(0, result['native_forwards'])
            self.assertEqual(98304, (root / 'fullchain-oracle.f32le').stat().st_size)
            with self.assertRaises(FileExistsError): sweep.prepare(root)

    def test_metadata_preparation_imports_no_torch_or_native_qnn(self):
        code = f"import sys; sys.path.insert(0,{str(TOOLS)!r}); import conv_history_sweep as s; s.frozen_route(); s.build_pack(); assert 'torch' not in sys.modules; assert not any(k.startswith('executorch') for k in sys.modules)"
        subprocess.run([sys.executable, '-c', code], check=True, timeout=20)


if __name__ == '__main__':
    unittest.main()
