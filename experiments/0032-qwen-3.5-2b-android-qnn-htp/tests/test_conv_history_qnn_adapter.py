"""Real adapter control flow with mock backend/runtime APIs; tiny CPU export only."""
import inspect
import json
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace as NS
import unittest
from unittest import mock

EXP=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(EXP/'tools'))
import conv_history_probe as probe
import conv_history_qnn_adapter as a
from conv_history_native_hooks import NativeHooks, deny_manager_creation, dtype_identity, native_tensor_encoding

TABLE=[{'name':'QNN_DATATYPE_UFIXED_POINT_16','code':1046}, {'name':'QNN_DATATYPE_FLOAT_32','code':562},
       {'name':'QNN_DATATYPE_UNDEFINED','code':2147483647}]


class TensorView:
    def __init__(self,raw=1046,missing=False):self.raw=raw;self.missing=missing;self.calls=0
    def GetName(self):return 'history@0'
    def GetDims(self):return [1,6144,1,4]
    def GetDataType(self):return self.raw
    def GetEncodings(self):
        self.calls+=1
        if self.missing:raise RuntimeError('optional getter unavailable')
        return NS(axis=-1,data=[{'scale':0.0007933978922665119,'offset':-37640}])


class Op:
    def __init__(self,missing=False):self.missing=missing
    def GetOpWrapper(self):return self
    def GetName(self):return 'quantize'
    def GetOpType(self):return 'Quantize'
    def GetPackageName(self):return 'qti.aisw'
    def GetInputTensors(self):return [TensorView(562)]
    def GetOutputTensors(self):return [TensorView(missing=self.missing)]


def fake_program(late_kernel=False):
    DelegateCall=type('DelegateCall',(),{})
    d=DelegateCall();d.delegate_index=0
    instructions=[NS(instr_args=d)]
    if late_kernel:
        KernelCall=type('KernelCall',(),{});k=KernelCall();k.op_index=0;instructions.append(NS(instr_args=k))
    return NS(execution_plan=[NS(name='forward',chains=[NS(instructions=instructions)],
                                delegates=[NS(id='QnnBackend')],operators=[NS(name='aten::add',overload='out')])])


def fake_api(fallback=False,missing=False,late_kernel=False,fail=False):
    stats={'lower_calls':0,'manager_constructors':0,'native_shaped_compile_calls':0}
    gm=NS(graph=NS(nodes=[NS(name='history',op='placeholder',target='history',args=(),kwargs={},
                            meta={'quant_attrs':{'scale':0.0007933978922665119,'zero_point':37640}})]))
    class Pass:
        def __call__(self,program):return NS(graph_module=program)
    class Tag(Pass):pass
    class Visitor:
        def get_quant_encoding_conf(self,node,target):return ('SCALE_OFFSET',{'scale':0.0007933978922665119,'offset':-37640})
    class Backend:
        @staticmethod
        def _build_op_wrappers(program,*args):
            Pass()(program);Visitor().get_quant_encoding_conf(program.graph.nodes[0],program.graph.nodes[0])
            return [Op(missing)]
    class Manager:
        def __init__(self,*args):stats['manager_constructors']+=1
        def Compile(self,*args):stats['native_shaped_compile_calls']+=1;return b'MOCK CONTEXT NOT QNN'
        def GetGraphNames(self):return ['forward']
        def GetGraphInputs(self,name):raise RuntimeError('optional manager IO unavailable')
        def GetGraphOutputs(self,name):return []
    binding=NS(QnnManager=Manager,PyQnnTensorWrapper=lambda x:x)
    class Program:
        executorch_program=fake_program(late_kernel)
        def write_to_file(self,f):f.write(b'MOCK PTE NOT LOADABLE')
    class Edge:
        def exported_program(self):return NS(graph_module=gm)
        def to_executorch(self,**kwargs):return Program()
    def lower(model,inputs,specs,**kwargs):
        stats['lower_calls']+=1;stats['kwargs']=kwargs
        if fail:raise RuntimeError('mock lower failure')
        manager=binding.QnnManager()
        Backend._build_op_wrappers(gm)
        manager.Compile(['forward'],[])
        return Edge()
    def options(**kwargs):stats['htp_options']=kwargs;return kwargs
    def specs(**kwargs):stats['compiler_options']=kwargs;return [NS(key='mock-spec',value=b'no SDK spec')]
    info=NS(num_delegated_subgraphs=1,num_delegated_nodes=3,
            delegation_by_operator={'cat':NS(delegated=2,non_delegated=int(fallback))})
    api=NS(binding=binding,introspection={'dtype_table':TABLE,'binding':{'scope':'MOCK'}},
           get_capture_program_passes=lambda:{Pass:{'activate':True},Tag:{'activate':True}},TagQuantIO=Tag,
           FoldQDQ=Pass,InsertRequantize=Pass,InsertIOQDQ=Pass,LayoutTransform=Pass,
           FuseConsecutiveCast=Pass,FuseConsecutiveTranspose=Pass,NodeVisitor=Visitor,QnnBackend=Backend,
           QCOM_PASS_ACTIVATE_KEY='activate',get_soc_to_chipset_map=lambda:{'SM8550':'mock-soc'},
           generate_htp_compiler_spec=options,generate_qnn_executorch_compiler_spec=specs,
           to_edge_transform_and_lower_to_qnn=lower,get_delegation_info=lambda gm:info,
           ExecutorchBackendConfig=lambda **kwargs:kwargs,MemoryPlanningPass=lambda **kwargs:kwargs)
    return api,stats


def request(case='fullchain'):
    _,raw=a.reviewed_inputs()
    return {'case':case,'input_hashes':[probe.digest(x) for x in raw]}


class Runtime:
    evidence_kind='mock'
    def __init__(self,case='fullchain',fail=False,mutate=False,bad_abi=False):
        self.case=case;self.fail=fail;self.mutate=mutate;self.bad_abi=bad_abi;self.loads=0;self.forwards=0
    def load(self,path):self.loads+=1;return self
    def method_meta(self,name):
        def info(shape):return NS(sizes=lambda:shape,dtype=lambda:NS(value=6))
        return NS(num_inputs=lambda:3 if self.bad_abi else 2,num_outputs=lambda:1,
                  input_tensor_meta=lambda i:info((probe.HISTORY_SHAPE,probe.PROJECTION_SHAPE)[i]),
                  output_tensor_meta=lambda i:info(probe.HISTORY_SHAPE))
    def forward(self,inputs):
        self.forwards+=1
        if self.fail:raise RuntimeError('mock forward error')
        data=probe.oracle(self.case,*(probe.tensor_bytes(x) for x in inputs))
        if self.mutate:inputs[0][0,0,0,0]=99.
        torch=probe.cpu_torch()
        return [torch.frombuffer(bytearray(data),dtype=torch.float32).reshape(probe.HISTORY_SHAPE)]


class NativeAdapterTest(unittest.TestCase):
    def compile(self,root,**kwargs):
        api,stats=fake_api(**kwargs)
        compiler=a.RealCompiler(api_loader=lambda:api,evidence_kind='mock')
        return a.compile_worker(request(),root,compiler),stats

    def test_dtype_integer_enum_value_name_and_unknown(self):
        for value in (1046,'1046','QNN_DATATYPE_UFIXED_POINT_16','Qnn_DataType_t.QNN_DATATYPE_UFIXED_POINT_16',NS(value=1046)):
            row=dtype_identity(value,TABLE);self.assertTrue(row['resolved']);self.assertTrue(row['fixed_point'])
        self.assertFalse(dtype_identity(562,TABLE)['fixed_point'])
        self.assertFalse(dtype_identity(999,TABLE)['resolved'])
        self.assertFalse(dtype_identity(1046.5,TABLE)['resolved'])
        self.assertFalse(dtype_identity(2147483647,TABLE)['resolved'])

    def test_native_shaped_integer_getter_reads_scale_offset(self):
        t=TensorView(1046);row=native_tensor_encoding(t,lambda x:x,TABLE)
        self.assertEqual(1,t.calls);self.assertEqual(-37640,row['encodings'][0]['qnn_offset'])
        self.assertEqual(1046,row['dtype']['code']);self.assertIsNone(row['encoding_kind'])

    def test_unknown_dtype_does_not_fabricate_encoding(self):
        t=TensorView(999);row=native_tensor_encoding(t,lambda x:x,TABLE)
        self.assertIsNone(row['encodings']);self.assertEqual(0,t.calls);self.assertIn('unresolved',row['encoding_reason'])

    def test_optional_missing_getter_is_nullable(self):
        row=native_tensor_encoding(TensorView(missing=True),lambda x:x,TABLE)
        self.assertIsNone(row['encodings']);self.assertIn('optional getter unavailable',row['encoding_reason'])

    def test_manager_denial_and_restoration_without_backend(self):
        original=type('Manager',(),{});binding=NS(QnnManager=original)
        with deny_manager_creation(binding) as counts:
            with self.assertRaises(PermissionError):binding.QnnManager()
        self.assertIs(binding.QnnManager,original);self.assertEqual(1,counts['manager_constructor_attempts'])

    def test_injected_api_cannot_claim_native(self):
        with self.assertRaises(ValueError):a.RealCompiler(api_loader=lambda:None)

    def test_native_worker_requires_release_before_import_bundle(self):
        with tempfile.TemporaryDirectory() as td,mock.patch.object(a,'load_compiler_api',side_effect=AssertionError('must not import')):
            with self.assertRaises(PermissionError):a.compile_worker(request(),Path(td))

    def test_real_adapter_control_flow_with_mock_backend_apis(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);result,stats=self.compile(root)
            self.assertEqual('complete',result['status']);self.assertEqual('mock',result['adapter_kind'])
            self.assertEqual(1,stats['lower_calls']);self.assertEqual(1,stats['native_shaped_compile_calls'])
            self.assertFalse(stats['htp_options']['use_fp16']);self.assertFalse(stats['htp_options']['use_multi_contexts'])
            self.assertFalse(stats['compiler_options']['saver']);self.assertEqual(set(),stats['kwargs']['skip_node_op_set'])
            tag=next(k for k in stats['kwargs']['passes_job'] if k.__name__=='Tag')
            self.assertFalse(stats['kwargs']['passes_job'][tag]['activate'])
            capture=result['artifact']['capture'];self.assertTrue(capture['wrapper_scale_offset_capture_complete'])
            self.assertFalse(capture['internal_finalized_graph_known'])
            events=list((root/'compile/data/taps').glob('*native-wrapper*'));self.assertTrue(events)
            self.assertEqual('mock',a.load_json(events[0])['capture_provenance']['kind'])

    def test_mock_compiled_success_and_one_forward(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);self.compile(root);runtime=Runtime()
            result=a.runtime_worker(request(),root,runtime)
            self.assertEqual((1,1),(runtime.loads,runtime.forwards));self.assertEqual('complete',result['status'])
            self.assertTrue(result['comparison']['all_output_bytes_match_scalar_oracle'])
            self.assertTrue((root/'runtime/data/output-0.raw').exists())

    def test_missing_tap_keeps_compile_and_raw_runtime_output(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);compiled,_=self.compile(root,missing=True)
            self.assertFalse(compiled['artifact']['capture']['wrapper_scale_offset_capture_complete'])
            got=a.runtime_worker(request(),root,Runtime())
            self.assertEqual('complete',got['status']);self.assertTrue((root/'runtime/data/output-0.raw').exists())

    def test_fallback_preserves_pte_but_rejects_runtime(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            with self.assertRaises(ValueError):self.compile(root,fallback=True)
            self.assertTrue((root/'compile/data/probe.pte').exists())
            runtime=Runtime()
            with self.assertRaises(ValueError):a.runtime_worker(request(),root,runtime)
            self.assertEqual(0,runtime.loads)

    def test_final_emitter_kernel_not_hidden_by_early_delegation(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            with self.assertRaises(ValueError):self.compile(root,late_kernel=True)
            final=a.load_json(root/'compile/data/final-program.json')
            self.assertFalse(final['zero_kernel_calls_all_delegates_qnn'])

    def test_compile_error_preserves_taps_without_retry(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);api,stats=fake_api(fail=True)
            with self.assertRaises(RuntimeError):a.compile_worker(request(),root,a.RealCompiler(lambda:api,'mock'))
            self.assertEqual(1,stats['lower_calls']);self.assertTrue((root/'compile/data/capture-summary.json').exists())

    def test_forward_failure_is_single_call(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);self.compile(root);runtime=Runtime(fail=True)
            with self.assertRaises(RuntimeError):a.runtime_worker(request(),root,runtime)
            self.assertEqual(1,runtime.forwards);self.assertTrue((root/'runtime/data/result.json').exists())

    def test_input_mutation_detected_after_raw_retention(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);self.compile(root)
            with self.assertRaises(ValueError):a.runtime_worker(request(),root,Runtime(mutate=True))
            self.assertTrue((root/'runtime/data/output-0.raw').exists())

    def test_wrong_abi_stops_before_forward(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);self.compile(root);runtime=Runtime(bad_abi=True)
            with self.assertRaises(ValueError):a.runtime_worker(request(),root,runtime)
            self.assertEqual(0,runtime.forwards)

    def test_tampered_pte_stops_before_load(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);self.compile(root);(root/'compile/data/probe.pte').write_bytes(b'changed')
            runtime=Runtime()
            with self.assertRaises(ValueError):a.runtime_worker(request(),root,runtime)
            self.assertEqual(0,runtime.loads)

    def test_release_binds_case_hash_root_and_approval_reference(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);req=root/'request.json';req.write_text('{}');release=root/'release.json'
            value={'status':'approved','scope':'one_tiny_case_compile_and_one_forward','case':'fullchain',
                   'request_sha256':probe.digest(req.read_bytes()),'output_directory':str(root/'run'),'approval_reference':'MOCK TEST ONLY'}
            release.write_text(json.dumps(value))
            with mock.patch.object(a,'validate_request',return_value=request()):
                accepted=a.require_release(req,release,root/'run');self.assertIs(a._EXECUTION_PERMISSION,accepted['_execution_permission'])
                value['case']='aligned';release.write_text(json.dumps(value))
                with self.assertRaises(PermissionError):a.require_release(req,release,root/'run')

    def test_guard_success_has_only_compile_and_runtime_phases(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/'run';seen=[]
            def supervise(cmd,guard,timeout,**kwargs):
                seen.append((cmd,timeout,kwargs['grace']))
                if '_compile-worker' in cmd:self.compile(root)
                else:a.runtime_worker(request(),root,Runtime())
                return {'exit_code':0,'reason':'process_exit','mock':True}
            with mock.patch.object(a,'require_release',return_value=request()):
                result=a.run_one_case('mock-request','mock-release',root,supervise)
            self.assertEqual('complete',result['status']);self.assertEqual(2,len(seen))
            self.assertEqual((120,20),(seen[0][1],seen[0][2]));self.assertEqual((60,20),(seen[1][1],seen[1][2]))
            self.assertNotEqual(str(a.PYTHON.resolve()),str(a.PYTHON)) # venv symlink is intentionally NOT resolved

    def test_guard_compile_timeout_has_no_runtime_or_retry(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/'run';seen=[]
            def supervise(*args,**kwargs):seen.append(1);return {'exit_code':-15,'reason':'host_timeout'}
            with mock.patch.object(a,'require_release',return_value=request()),self.assertRaises(RuntimeError):
                a.run_one_case('mock-request','mock-release',root,supervise)
            self.assertEqual(1,len(seen));self.assertFalse((root/'runtime').exists())

    def test_case_stop_propagates_to_active_phase_guard(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/'run'
            def supervise(cmd,guard,*args,**kwargs):
                (root/'STOP').touch();time.sleep(.25);self.assertTrue((guard/'STOP').exists())
                return {'exit_code':-15,'reason':'coordinator_requested_stop'}
            with mock.patch.object(a,'require_release',return_value=request()),self.assertRaises(RuntimeError):
                a.run_one_case('mock-request','mock-release',root,supervise)
            self.assertFalse((root/'runtime').exists())

    def test_total_deadline_blocks_second_phase(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/'run';seen=[]
            def supervise(*args,**kwargs):seen.append(1);self.compile(root);return {'exit_code':0,'reason':'process_exit'}
            with mock.patch.object(a,'require_release',return_value=request()),mock.patch.object(a.time,'monotonic',side_effect=[0,0,241,241]),self.assertRaises(TimeoutError):
                a.run_one_case('mock-request','mock-release',root,supervise)
            self.assertEqual(1,len(seen))

    def test_actual_tiny_cpu_exports_handle_opoverload_metadata(self):
        with tempfile.TemporaryDirectory() as td:
            for case,count in (('fullchain',4),('outputonly',1),('aligned',4)):
                root=Path(td)/case;result=a.export_case(case,root)
                self.assertEqual('complete',result['status'])
                self.assertEqual(count,result['quantize_nodes']);self.assertEqual(count,result['dequantize_nodes'])
                self.assertFalse(result['backend_init_compile_run']);self.assertFalse(result['qnn_imported'])
                graph=a.load_json(root/'graph.json');self.assertFalse(graph['tensor_payloads_read'])
                self.assertIn('quantized_decomposed',json.dumps(graph))

    def test_no_native_qnn_module_imported_in_mock_suite(self):
        self.assertFalse(any(n.startswith('executorch.backends.qualcomm') for n in sys.modules))


if __name__=='__main__':
    probe.cpu_torch().set_num_threads(4)
    unittest.main()
