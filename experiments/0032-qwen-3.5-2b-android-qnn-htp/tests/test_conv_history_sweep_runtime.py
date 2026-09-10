from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[1] / 'tools'
sys.path.insert(0, str(TOOLS))
import conv_history_sweep_runtime as adapter

PACK = TOOLS.parent / 'results/conv-history-sweep-readiness-20260910/pack'


class FakeRuntime:
    evidence_kind = 'mock'
    def __init__(self, mode='ok'):
        self.mode = mode; self.loads = 0; self.forwards = 0
    def load(self, path):
        self.loads += 1
        if self.mode == 'load_error': raise RuntimeError('synthetic load failure')
        return self
    def method_meta(self, method):
        def info(shape): return SimpleNamespace(dtype=lambda: 6, sizes=lambda: shape)
        return SimpleNamespace(num_inputs=lambda: 1 if self.mode == 'bad_abi' else 2, num_outputs=lambda: 1,
            input_tensor_meta=lambda i: info((adapter.probe.HISTORY_SHAPE, adapter.probe.PROJECTION_SHAPE)[i]),
            output_tensor_meta=lambda i: info(adapter.probe.HISTORY_SHAPE))
    def forward(self, inputs):
        self.forwards += 1
        if self.mode == 'forward_error': raise RuntimeError('synthetic forward failure')
        torch = adapter.probe.cpu_torch()
        raw = adapter.probe.oracle('fullchain', *(adapter.probe.tensor_bytes(t) for t in inputs))
        output = torch.frombuffer(bytearray(raw), dtype=torch.float32).reshape(adapter.probe.HISTORY_SHAPE)
        if self.mode == 'nonfinite': output[0, 0, 0, 0] = float('nan')
        if self.mode == 'mismatch': output[0, 0, 0, 0] += .01
        if self.mode == 'mutation': inputs[0][0, 0, 0, 0] += 1
        return [output.flatten()] if self.mode == 'bad_output' else [output]


class SweepRuntimeReadinessTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.prepared = Path(cls.temporary.name) / 'prepared'
        cls.request = adapter.prepare_request(PACK, cls.prepared)
        cls.request_path = cls.prepared / 'request.json'
    @classmethod
    def tearDownClass(cls): cls.temporary.cleanup()

    def release(self, root):
        path = root.parent / 'release.json'
        path.write_text(json.dumps({'status': 'approved', 'scope': self.request['scope'],
            'request_sha256': adapter.probe.digest(self.request_path.read_bytes()),
            'output_directory': str(root.absolute()), 'approval_reference': 'SYNTHETIC TEST ONLY, never executed'}))
        return path

    def test_saved_pack_and_request_verify_without_backend(self):
        self.assertEqual('verified_saved_bytes_only', adapter.sweep.verify(PACK)['status'])
        request = adapter.validate_request(self.request_path)
        self.assertFalse(request['execution_authorized'])
        self.assertFalse(request['compile_allowed'])
        self.assertEqual(0, request['limits']['maximum_compiles'])
        self.assertEqual(adapter.sweep.PTE_SHA, request['frozen_route']['pte']['sha256'])
        self.assertEqual(230736, request['frozen_route']['context']['bytes'])

    def test_unapproved_template_and_old_scope_fail(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)/'run'
            with self.assertRaises(PermissionError):
                adapter.require_release(self.request_path, self.prepared/'release-template.json', root)
            release = self.release(root); value = json.loads(release.read_text())
            value['scope'] = 'one_tiny_case_compile_and_one_forward'; release.write_text(json.dumps(value))
            with self.assertRaises(PermissionError): adapter.require_release(self.request_path, release, root)

    def test_request_digest_output_binding_and_budget_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)/'run'; release = self.release(root)
            with self.assertRaises(PermissionError): adapter.require_release(self.request_path, release, root.parent/'other')
            record = json.loads(release.read_text()); record['request_sha256'] = '0'*64; release.write_text(json.dumps(record))
            with self.assertRaises(PermissionError): adapter.require_release(self.request_path, release, root)
            modified = json.loads(self.request_path.read_text()); modified['limits']['maximum_compiles'] = 1
            path = Path(d)/'bad.json'; path.write_text(json.dumps(modified))
            with self.assertRaises(ValueError): adapter.validate_request(path)

    def test_unguarded_native_worker_rejected_before_runtime_construction(self):
        with tempfile.TemporaryDirectory() as d, patch.object(adapter.base, 'RealRuntime') as constructor:
            with self.assertRaises(PermissionError): adapter.worker(self.request, Path(d)/'run')
            constructor.assert_not_called()

    def test_injected_native_provenance_rejected(self):
        runtime = FakeRuntime(); runtime.evidence_kind = 'native_binding'
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError): adapter.worker(self.request, Path(d)/'run', runtime)
        self.assertEqual(0, runtime.loads)

    def test_single_mock_load_forward_preserves_raw_and_inputs(self):
        runtime = FakeRuntime()
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)/'run'; result = adapter.worker(self.request, root, runtime)
            self.assertEqual((1, 1), (runtime.loads, runtime.forwards))
            self.assertEqual('mock', result['evidence_kind'])
            self.assertEqual(0, result['actual_native_loads'])
            self.assertEqual(0, result['actual_native_forwards'])
            self.assertEqual('byte_equal', result['comparison']['numerical_status'])
            self.assertTrue(result['comparison']['inputs_unchanged'])
            self.assertEqual((PACK/'cpu-output.f32le').read_bytes(), (root/'runtime/data/output-0.raw').read_bytes())
            with self.assertRaises(FileExistsError): adapter.worker(self.request, root, runtime)
            self.assertEqual(1, runtime.forwards)

    def test_nonfinite_and_finite_mismatch_are_collection_not_equivalence(self):
        for mode, expected in [('nonfinite', 'nonfinite'), ('mismatch', 'finite_mismatch')]:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as d:
                root = Path(d)/'run'; result = adapter.worker(self.request, root, FakeRuntime(mode))
                self.assertEqual('complete', result['status'])
                self.assertEqual(expected, result['comparison']['numerical_status'])
                self.assertFalse(result['comparison']['all_output_bytes_match_scalar_oracle'])
                self.assertEqual(98304, (root/'runtime/data/output-0.raw').stat().st_size)

    def test_mutation_retains_before_after_and_output(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)/'run'
            with self.assertRaisesRegex(ValueError, 'mutated'): adapter.worker(self.request, root, FakeRuntime('mutation'))
            folder = root/'runtime/data'
            self.assertTrue((folder/'output-0.raw').exists())
            self.assertNotEqual((folder/'history.f32le').read_bytes(), (folder/'history-after.f32le').read_bytes())
            self.assertEqual('error', json.loads((folder/'result.json').read_text())['status'])

    def test_bad_abi_does_not_forward_and_bad_output_is_saved_first(self):
        with tempfile.TemporaryDirectory() as d:
            runtime = FakeRuntime('bad_abi')
            with self.assertRaises(ValueError): adapter.worker(self.request, Path(d)/'abi', runtime)
            self.assertEqual(0, runtime.forwards)
            root = Path(d)/'output'
            with self.assertRaises(ValueError): adapter.worker(self.request, root, FakeRuntime('bad_output'))
            self.assertTrue((root/'runtime/data/output-0.raw').exists())

    def test_errors_keep_attempt_counts_without_retry(self):
        for mode, forwards in [('load_error', 0), ('forward_error', 1)]:
            with tempfile.TemporaryDirectory() as d:
                root = Path(d)/'run'; runtime = FakeRuntime(mode)
                with self.assertRaises(RuntimeError): adapter.worker(self.request, root, runtime)
                self.assertEqual((1, forwards), (runtime.loads, runtime.forwards))
                result = json.loads((root/'runtime/data/result.json').read_text())
                self.assertEqual('error', result['status'])
                self.assertTrue((root/'runtime/data/history.f32le').exists())

    def test_external_guard_timeout_retains_partial_data_and_no_retry(self):
        calls = []
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)/'run'; release = self.release(root)
            def guard(command, directory, budget, env, grace):
                calls.append(command)
                self.assertEqual(60, budget); self.assertEqual(20, grace)
                self.assertEqual('4', env['OMP_NUM_THREADS'])
                self.assertIn('_worker', command); self.assertNotIn('_compile-worker', command)
                data = root/'runtime/data'; data.mkdir(); (data/'partial.raw').write_bytes(b'synthetic partial')
                return {'exit_code': -15, 'reason': 'timeout', 'child_reaped': True}
            with self.assertRaises(RuntimeError): adapter.run_one(self.request_path, release, root, guard)
            self.assertEqual(1, len(calls)); self.assertTrue((root/'runtime/data/partial.raw').exists())
            self.assertEqual('error', json.loads((root/'result.json').read_text())['status'])

    def test_fake_transport_success_and_total_deadline(self):
        for expire in (False, True):
            with tempfile.TemporaryDirectory() as d:
                root = Path(d)/'run'; release = self.release(root)
                def guard(command, directory, budget, env, grace):
                    adapter.worker(self.request, root, FakeRuntime())
                    return {'exit_code': 0, 'reason': 'process_exit', 'child_reaped': True}
                # Only this adapter's clock is mocked, not thread/stdlib clocks.
                clock = SimpleNamespace(monotonic=iter([0., 0., 91. if expire else 1., 92. if expire else 2.]).__next__)
                with patch.object(adapter, 'time', clock):
                    if expire:
                        with self.assertRaises(TimeoutError): adapter.run_one(self.request_path, release, root, guard)
                    else:
                        result = adapter.run_one(self.request_path, release, root, guard)
                        self.assertEqual('complete', result['status'])
                        self.assertEqual('injected_test_transport', result['transport_kind'])
                        self.assertEqual('mock', result['worker']['evidence_kind'])
                self.assertTrue((root/'runtime/data/output-0.raw').exists())

    def test_external_stop_propagates_to_guard(self):
        import time
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)/'run'; release = self.release(root)
            def guard(command, directory, budget, env, grace):
                (root/'STOP').touch()
                deadline = time.monotonic() + 3
                while not (directory/'STOP').exists() and time.monotonic() < deadline: time.sleep(.02)
                self.assertTrue((directory/'STOP').exists())
                return {'exit_code': -15, 'reason': 'coordinator_requested_stop', 'child_reaped': True}
            with self.assertRaises(RuntimeError): adapter.run_one(self.request_path, release, root, guard)
            self.assertEqual('coordinator_requested_stop', json.loads((root/'result.json').read_text())['phases'][0]['reason'])

    def test_pack_tamper_is_rejected_before_mock_load(self):
        import shutil
        with tempfile.TemporaryDirectory() as d:
            pack = Path(d)/'pack'; shutil.copytree(PACK, pack)
            path = pack/'history.f32le'; raw = bytearray(path.read_bytes()); raw[0] ^= 1; path.write_bytes(raw)
            request = dict(self.request, pack_directory=str(pack), pack_manifest=adapter.sweep.identity(pack/'result.json'))
            runtime = FakeRuntime()
            with self.assertRaisesRegex(ValueError, 'Pack bytes changed'):
                adapter.worker(request, Path(d)/'run', runtime)
            self.assertEqual(0, runtime.loads)

    def test_native_imports_absent_in_separate_preparation_process(self):
        code = f"import sys; sys.path.insert(0,{str(TOOLS)!r}); import conv_history_sweep_runtime as a; a.validate_request({str(self.request_path)!r}); assert 'torch' not in sys.modules; assert not any(k.startswith('executorch') for k in sys.modules)"
        subprocess.run([sys.executable, '-c', code], check=True, timeout=30)


if __name__ == '__main__': unittest.main()
