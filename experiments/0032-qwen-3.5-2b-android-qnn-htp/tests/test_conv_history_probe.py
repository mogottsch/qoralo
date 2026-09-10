"""Tiny CPU references + mocked lowering/runtime only; no real QNN imports."""
import inspect
import json
from pathlib import Path
import struct
import sys
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest import mock

TOOLS = Path(__file__).resolve().parents[1] / 'tools'
sys.path.insert(0, str(TOOLS))
import conv_history_probe as probe
from conv_history_probe_hooks import Hooks, graph_snapshot, tensor_encoding


class TensorView:
    def __init__(self, dtype='QNN_DATATYPE_UFIXED_POINT_16', fail=False):
        self.dtype, self.fail = dtype, fail
        self.calls = 0
    def GetName(self): return 'input_history@0'
    def GetDims(self): return [1,6144,1,4]
    def GetDataType(self): return self.dtype
    def GetEncodings(self):
        self.calls += 1
        if self.fail: raise RuntimeError('getter unavailable')
        return NS(axis=-1, data=[{'scale': probe.encodings()['state_input']['scale'], 'offset': -37640}])


class Op:
    def __init__(self): self.tensor = TensorView()
    def GetOpWrapper(self): return self
    def GetName(self): return 'quantize'
    def GetOpType(self): return 'Quantize'
    def GetPackageName(self): return 'qti.aisw'
    def GetInputTensors(self): return [TensorView('QNN_DATATYPE_FLOAT_32')]
    def GetOutputTensors(self): return [self.tensor]


def graph():
    class NoPayload:
        shape = (1,6144,1,4)
        dtype = 'torch.float32'
        def tolist(self): raise AssertionError('payload access forbidden')
    node = NS(name='history', op='placeholder', target='history', args=(), kwargs={},
              meta={'val': NoPayload(), 'quant_attrs': {'scale': 1., 'zero_point': 0}})
    return NS(graph=NS(nodes=[node]))


def classes():
    class Base:
        def __call__(self, gm):
            gm.graph.nodes[0].meta['quant_attrs']['scale'] = 2.
            return NS(graph_module=gm)
    class Pass(Base): pass
    class Visitor:
        def get_quant_encoding_conf(self, node, target):
            return 'SCALE_OFFSET', {'scale': 2., 'offset': -37640}
    class Backend:
        calls = 0
        @staticmethod
        def _build_op_wrappers(program, *args, **kwargs):
            Backend.calls += 1
            Pass()(program)
            Visitor().get_quant_encoding_conf(program.graph.nodes[0], program.graph.nodes[0])
            return [Op()]
    return Pass, Visitor, Backend


class Compiler:
    evidence_kind = 'mock'
    def __init__(self, fallback=False, fail=False):
        self.calls = 0; self.fallback = fallback; self.fail = fail
    def compile(self, spec, store):
        self.calls += 1
        store.json('mock-compile-entered.json', {'mock': True, 'case': spec['case']})
        if self.fail: raise RuntimeError('mock compile interruption')
        P,V,B=classes()
        with Hooks(store).install([P],B,lambda x:x,V):
            B._build_op_wrappers(graph())  # API-shaped mocks, not backend support checks
        return {'bytes': b'NOT A QNN BINARY', 'case': spec['case'],
                'delegation': {'all_tensor_compute_delegated': not self.fallback}}


class Runtime:
    evidence_kind = 'mock'
    def __init__(self, fail=False, mutate=False): self.calls=0; self.fail=fail; self.mutate=mutate
    def forward(self, artifact, inputs):
        self.calls += 1
        if self.fail: raise RuntimeError('mock native error')
        torch = probe.cpu_torch()
        data = probe.oracle(artifact['case'], *(probe.tensor_bytes(x) for x in inputs))
        if self.mutate: inputs[0][0,0,0,0] = 7.
        return torch.frombuffer(bytearray(data), dtype=torch.float32).reshape(probe.HISTORY_SHAPE)


class ProbeTest(unittest.TestCase):
    def test_exact_case_definitions_four_one_four_qdq_pairs(self):
        specs = [probe.case_spec(c) for c in probe.CASES]
        self.assertEqual([4,1,4], [s['qdq_pair_count'] for s in specs])
        self.assertEqual(specs[0]['stages']['projection'], specs[0]['stages']['output'])
        self.assertEqual(1, len({json.dumps(e) for e in specs[2]['stages'].values()}))
        self.assertIsNone(specs[1]['stages']['history'])
        self.assertIsNone(specs[1]['stages']['projection'])
        self.assertIsNone(specs[1]['stages']['concat'])

    def test_three_cpu_variants_match_all_scalar_oracle_bytes(self):
        inputs = probe.make_inputs(); before = tuple(probe.tensor_bytes(x) for x in inputs)
        for case, selected in zip(probe.CASES, [22.131549835205078,23.721895217895508,23.721895217895508]):
            model = probe.make_module(case)
            self.assertEqual([], list(model.parameters())); self.assertEqual([], list(model.buffers()))
            output = model(*inputs)
            r = probe.validate_output(case, output, before)
            self.assertTrue(r['all_output_bytes_match_scalar_oracle']); self.assertTrue(r['finite'])
            self.assertEqual(selected, r['selected_actual'])
            self.assertEqual(list(probe.HISTORY_SHAPE), r['shape'])
        self.assertEqual(before, tuple(probe.tensor_bytes(x) for x in inputs))

    def test_input_and_slice_geometry(self):
        h,p = probe.make_inputs()
        self.assertEqual(98304, len(probe.tensor_bytes(h))); self.assertEqual(24576,len(probe.tensor_bytes(p)))
        self.assertEqual(probe.COMMON_VALUE, h[0,6053,0,3].item())
        data=probe.oracle('outputonly',probe.tensor_bytes(h),probe.tensor_bytes(p))
        e=probe.encodings()['slice_output']
        for slot, value in enumerate((0.5,-0.75,probe.COMMON_VALUE,0.125)):
            self.assertEqual(probe.scalar_qdq(value,e)['output_fp32'],struct.unpack_from('<f',data,(6053*4+slot)*4)[0])

    def test_prepare_retains_raw_three_references_and_is_exclusive(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'run'; r=probe.prepare(path)
            self.assertEqual('complete',r['status']); self.assertEqual(3,r['cpu_reference_forwards'])
            self.assertEqual(0,r['qnn_compile_calls']); self.assertEqual(0,r['qnn_runtime_calls'])
            for case in probe.CASES: self.assertEqual(98304,(path/case/'output.f32le').stat().st_size)
            with self.assertRaises(FileExistsError):probe.prepare(path)

    def test_cpu_validation_failure_preserves_raw_and_stops(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'run'; orig=probe.validate_output
            def bad(*a):
                r=orig(*a); r['all_output_bytes_match_scalar_oracle']=False; return r
            with mock.patch.object(probe,'validate_output',bad),self.assertRaises(ValueError):probe.prepare(path)
            self.assertTrue((path/'fullchain/output.f32le').exists())
            self.assertFalse((path/'outputonly').exists())
            self.assertEqual('error',json.loads((path/'result.json').read_text())['status'])

    def test_reject_real_interfaces_before_any_call(self):
        c,r=Compiler(),Runtime(); c.evidence_kind='real'
        with self.assertRaises(PermissionError):probe.mock_case('fullchain',Path('forbidden'),c,r)
        self.assertEqual(0,c.calls); self.assertEqual(0,r.calls)

    def test_mock_success_exactly_one_compile_and_forward(self):
        with tempfile.TemporaryDirectory() as td:
            c,r=Compiler(),Runtime(); result=probe.mock_case('fullchain',Path(td)/'run',c,r)
            self.assertEqual((1,1),(c.calls,r.calls)); self.assertEqual('mock_interfaces_not_qnn',result['evidence_class'])

    def test_mock_compile_failure_no_retry_or_runtime(self):
        with tempfile.TemporaryDirectory() as td:
            c,r=Compiler(fail=True),Runtime(); path=Path(td)/'run'
            with self.assertRaises(RuntimeError):probe.mock_case('fullchain',path,c,r)
            self.assertEqual((1,0),(c.calls,r.calls)); self.assertTrue((path/'result.json').exists())

    def test_mock_fallback_preserves_artifact_without_execution(self):
        with tempfile.TemporaryDirectory() as td:
            c,r=Compiler(fallback=True),Runtime(); path=Path(td)/'run'
            with self.assertRaises(ValueError):probe.mock_case('fullchain',path,c,r)
            self.assertEqual(0,r.calls); self.assertTrue((path/'mock-compiled-artifact.bin').exists())

    def test_mock_runtime_error_no_retry(self):
        with tempfile.TemporaryDirectory() as td:
            c,r=Compiler(),Runtime(fail=True); path=Path(td)/'run'
            with self.assertRaises(RuntimeError):probe.mock_case('fullchain',path,c,r)
            self.assertEqual((1,1),(c.calls,r.calls)); self.assertTrue((path/'history.f32le').exists())

    def test_mock_mutation_preserves_output_then_rejects(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'run'
            with self.assertRaises(ValueError):probe.mock_case('fullchain',path,Compiler(),Runtime(mutate=True))
            self.assertTrue((path/'output.f32le').exists())

    def test_hook_install_does_not_compile_or_build(self):
        P,V,B=classes()
        with tempfile.TemporaryDirectory() as td:
            hooks=Hooks(probe.Evidence(Path(td)/'run'))
            with hooks.install([P],B,lambda x:x,V): self.assertEqual(0,B.calls)
            self.assertEqual(0,hooks.counter)

    def test_hooks_capture_pass_change_selection_and_native_shaped_getters(self):
        P,V,B=classes(); gm=graph()
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'run'; hooks=Hooks(probe.Evidence(path))
            with hooks.install([P],B,lambda x:x,V):
                output=B._build_op_wrappers(gm)
                self.assertEqual(1,output[0].tensor.calls)
            taps=[json.loads(p.read_text()) for p in sorted((path/'taps').glob('*.json'))]
            pre=next(x for x in taps if x.get('pass_type') and x['nodes'][0]['metadata']['quant_attrs']['scale']==1.)
            post=next(x for x in taps if x.get('pass_type') and x['nodes'][0]['metadata']['quant_attrs']['scale']==2.)
            self.assertFalse(pre['tensor_payloads_read']); self.assertFalse(post['tensor_payloads_read'])
            enc=taps[-1]['operators'][0]['outputs'][0]['encodings'][0]
            self.assertEqual(-37640,enc['qnn_offset']); self.assertEqual(8,len(enc['scale_float32_le_hex']))
            self.assertFalse(taps[-1]['finalized_or_fused_graph'])
            self.assertNotIn('__call__',P.__dict__)

    def test_hook_restoration_on_build_failure(self):
        P,V,B=classes(); before=inspect.getattr_static(B,'_build_op_wrappers'); v=V.get_quant_encoding_conf
        with tempfile.TemporaryDirectory() as td:
            hooks=Hooks(probe.Evidence(Path(td)/'run'))
            with self.assertRaises(RuntimeError):
                with hooks.install([P],B,lambda x:x,V):
                    raise RuntimeError('interrupt')
        self.assertIs(before,inspect.getattr_static(B,'_build_op_wrappers'))
        self.assertIs(v,V.get_quant_encoding_conf); self.assertNotIn('__call__',P.__dict__)

    def test_failed_pass_capture_and_propagation(self):
        P,V,B=classes()
        def bad(self,gm):raise RuntimeError('pass failed')
        P.__call__=bad
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'run'; hooks=Hooks(probe.Evidence(path))
            with hooks.install([P],B,lambda x:x,V),self.assertRaises(RuntimeError):B._build_op_wrappers(graph())
            self.assertTrue(list((path/'taps').glob('*failed-pass.json')))
            self.assertTrue(list((path/'taps').glob('*failed-wrapper-build.json')))
        self.assertIs(bad,P.__call__)

    def test_missing_encoding_is_null_not_fake_zero(self):
        r=tensor_encoding(TensorView(fail=True),lambda x:x)
        self.assertIsNone(r['encodings']); self.assertIn('getter unavailable',r['encoding_reason'])

    def test_float_tensor_does_not_read_undefined_encoding(self):
        v=TensorView('QNN_DATATYPE_FLOAT_32')
        self.assertIsNone(tensor_encoding(v,lambda x:x)['encodings']); self.assertEqual(0,v.calls)

    def test_graph_capture_never_reads_tensor_payload(self):
        r=graph_snapshot(graph())
        self.assertFalse(r['tensor_payloads_read']); self.assertEqual([1,6144,1,4],r['nodes'][0]['value_metadata']['shape'])

    def test_optional_manager_io_getters_only(self):
        manager=NS(GetGraphNames=lambda:['forward'],GetGraphInputs=lambda n:[TensorView()],GetGraphOutputs=lambda n:[])
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'run'; hooks=Hooks(probe.Evidence(path)); hooks.manager_io(manager)
            tap=json.loads(next((path/'taps').glob('*.json')).read_text())
            self.assertEqual('forward',tap['graphs'][0]['name']); self.assertEqual([],tap['graphs'][0]['outputs'])

    def test_budget_no_implicit_followon_and_no_real_adapter(self):
        p=probe.runtime_plan()
        self.assertEqual(720,p['aggregate_active_deadline_seconds']); self.assertFalse(p['automatic_follow_on_authorized'])
        self.assertEqual(1,p['per_case']['forward_calls_max']); self.assertFalse(p['automatic_retry_or_resume'])

    def test_no_qnn_imported_by_this_test_harness(self):
        self.assertFalse(any(n.startswith('executorch.backends.qualcomm') for n in sys.modules))


if __name__=='__main__':
    probe.cpu_torch().set_num_threads(4)
    unittest.main()
