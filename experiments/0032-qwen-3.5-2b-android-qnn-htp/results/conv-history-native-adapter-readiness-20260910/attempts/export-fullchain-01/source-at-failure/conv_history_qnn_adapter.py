#!/usr/bin/env python3
"""Fixed weight-free one-case QNN adapter. Preparation never initializes QNN.

execute-one and internal workers require a separate explicit approved release.
No model/checkpoint arguments, auto retry, resume or multi-case execution mode.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys
import threading
import time

import conv_history_probe as probe
from conv_history_native_hooks import NativeHooks, deny_manager_creation, file_identity, introspect_binding
from conv_history_probe_hooks import graph_snapshot
from qwen_host_guard import supervise

EXP = Path(__file__).resolve().parents[1]
REFERENCE = EXP / 'results/conv-history-probe-readiness-20260910/cpu-reference'
SDK = Path('/home/moritz/opt/qairt/2.49.0.260730')
PYTHON = EXP.parents[1] / 'artifacts/venv-executorch-1.2/bin/python'
LIMITS = {'compile_seconds': 120, 'runtime_seconds': 60, 'total_active_seconds': 240,
          'termination_grace_seconds': 20, 'threads': 4}
MAX_PTE_BYTES = 16 * 1024 * 1024  # fixed tiny graphs, not a full-model load path
_EXECUTION_PERMISSION = object()  # only require_release installs this in-memory token


def load_json(path):
    return json.loads(Path(path).read_text())


def environment(scratch):
    if not (SDK / 'lib/x86_64-linux-clang').is_dir():
        raise RuntimeError('Preinstalled pinned SDK required; never install or activate an SDK')
    site = PYTHON.parent.parent / 'lib/python3.11/site-packages'
    libraries = [SDK/'lib/x86_64-linux-clang', site/'executorch/backends/qualcomm/sdk/libcxx-14.0.0',
                 site/'executorch/extension/pybindings']
    env = dict(os.environ, QNN_SDK_ROOT=str(SDK), TMPDIR=str(scratch),
               OMP_NUM_THREADS='4', MKL_NUM_THREADS='4', OPENBLAS_NUM_THREADS='4')
    env['LD_LIBRARY_PATH'] = ':'.join(map(str, libraries))
    env['PATH'] = str(EXP.parents[1]/'artifacts/tools/flatbuffers-25.12.19') + ':' + env.get('PATH','')
    return env


def source_pins():
    own = [EXP/'tools'/name for name in
           ('conv_history_qnn_adapter.py', 'conv_history_native_hooks.py', 'conv_history_probe.py',
            'conv_history_probe_hooks.py', 'audit_conv_history_metadata.py', 'qwen_host_guard.py')]
    base = PYTHON.parent.parent/'lib/python3.11/site-packages/executorch/backends/qualcomm'
    backend = [base/name for name in ('qnn_preprocess.py','builders/node_visitor.py','utils/utils.py',
               'utils/qnn_manager_lifecycle.py','_passes/qnn_pass_manager.py','_passes/annotate_quant_attrs.py',
               '_passes/fold_qdq.py','_passes/insert_io_qdq.py','_passes/insert_requantize.py','_passes/layout_transform.py')]
    return [file_identity(path) for path in own+backend]


def reviewed_inputs():
    records = load_json(REFERENCE/'result.json')['files']
    raw = []
    for name, expected_size in (('raw/history.f32le',98304),('raw/projection.f32le',24576)):
        data = (REFERENCE/name).read_bytes()
        if len(data) != expected_size or probe.digest(data) != records[name]['sha256']:
            raise ValueError('Accepted synthetic input bytes changed')
        raw.append(data)
    torch = probe.cpu_torch()
    return tuple(torch.frombuffer(bytearray(data), dtype=torch.float32).reshape(shape)
                 for data, shape in zip(raw, (probe.HISTORY_SHAPE,probe.PROJECTION_SHAPE))), tuple(raw)


def export_case(case, directory):
    """Allowed tiny CPU export only; never imports QNN or lowers the graph."""
    store = probe.Evidence(directory)
    state = {'evidence_class':'tiny_cpu_export_only', 'case':case, 'qnn_imported':False,
             'backend_init_compile_run':False, 'status':'started'}
    try:
        torch = probe.cpu_torch(); torch.set_num_threads(4)
        model = probe.make_module(case); inputs, raw = reviewed_inputs()
        if list(model.parameters()) or list(model.buffers()):
            raise ValueError('Fixed probe unexpectedly has weights/buffers')
        ep = torch.export.export(model, inputs, strict=True)
        snapshot = graph_snapshot(ep)
        store.json('graph.json',snapshot)
        store.raw('graph.txt',str(ep.graph).encode())
        q = sum('quantized_decomposed.quantize_per_tensor.' in str(n.target) for n in ep.graph.nodes)
        dq = sum('quantized_decomposed.dequantize_per_tensor.' in str(n.target) for n in ep.graph.nodes)
        expected = probe.case_spec(case)['qdq_pair_count']
        if q != expected or dq != expected or ep.state_dict:
            raise ValueError('Export changed fixed Q/DQ topology or introduced state')
        # PT2 stays LOCAL-ONLY. It is not loaded by the eventual compiler, which
        # reconstructs the fixed module from the pinned source and reviewed inputs.
        path = store.directory/'tiny.pt2'; torch.export.save(ep,path)
        state.update(status='complete', quantize_nodes=q, dequantize_nodes=dq,
                     export_identity=file_identity(path), graph_sha256=probe.digest((store.directory/'graph.json').read_bytes()),
                     input_hashes=[probe.digest(x) for x in raw], torch_version=torch.__version__)
    except BaseException as error:
        state.update(status='error',error={'type':type(error).__name__,'message':str(error)})
        raise
    finally:
        store.json('result.json',state)
    return state


def prepare_request(case, directory, binding_report_path):
    """Source/prep entrypoint: CPU export + request, no backend initialization."""
    state = export_case(case,directory)
    binding_report = load_json(binding_report_path)
    if binding_report['evidence_class'] != 'native_binding_interface_introspection_only':
        raise ValueError('Need the retained native interface introspection, not fabricated runtime proof')
    request = {'schema_version':1,'case':case,'spec':probe.case_spec(case),'limits':LIMITS,
               'input_hashes':state['input_hashes'],'sources':source_pins(),
               'binding_identity':binding_report['binding'], 'sdk_root':str(SDK),
               'reference_result':file_identity(REFERENCE/'result.json'),
               'prepared_export':state, 'execution_authorized':False,
               'route':'SM8550/v73 QNN HTP quantized backend, host x86 simulation; no weights',
               'compile_options':{'use_fp16':False,'use_multi_contexts':False,'TagQuantIO':False,'saver':False,'debug':True},
               'maximum_high_level_compile_invocations':1,'maximum_forward_calls':1,
               'internal_native_callback_counts':'recorded, not assumed equal to logical phase count',
               'automatic_retry_resume_followon':False}
    path=Path(directory)/'request.json'
    with path.open('x') as f:
        json.dump(request,f,indent=2); f.write('\n'); f.flush(); os.fsync(f.fileno())
    return request


def validate_request(path):
    request=load_json(path); case=request['case']
    if case not in probe.CASES or request['spec'] != json.loads(json.dumps(probe.case_spec(case))) or request['limits'] != LIMITS:
        raise ValueError('Unreviewed variant, graph definition or budget')
    if request['sdk_root'] != str(SDK) or request['compile_options'] != {'use_fp16':False,'use_multi_contexts':False,'TagQuantIO':False,'saver':False,'debug':True}:
        raise ValueError('Unreviewed backend/precision options')
    if request['sources'] != source_pins() or request['reference_result'] != file_identity(REFERENCE/'result.json'):
        raise ValueError('Pinned source/reference manifest changed')
    binding=request['binding_identity'];binding_path=Path(binding['path'])
    expected_parent=PYTHON.parent.parent/'lib/python3.11/site-packages/executorch/backends/qualcomm/python'
    if binding_path.parent != expected_parent or not binding_path.name.startswith('PyQnnManagerAdaptor.') or binding_path.suffix!='.so':
        raise ValueError('Unreviewed native binding path')
    if binding_path.stat().st_size>32*1024*1024 or file_identity(binding_path)!=binding:
        raise ValueError('Pinned binding changed or exceeds introspection bound')
    return request


def require_release(request_path, release_path, root):
    request=validate_request(request_path); release=load_json(release_path)
    expected={'status':'approved','scope':'one_tiny_case_compile_and_one_forward','case':request['case'],
              'request_sha256':probe.digest(Path(request_path).read_bytes()), 'output_directory':str(Path(root).absolute())}
    if any(release.get(k) != v for k,v in expected.items()) or not release.get('approval_reference'):
        raise PermissionError('Separate Pi execution approval bound to this case/request/output directory required')
    request['_execution_permission'] = _EXECUTION_PERMISSION
    return request


@contextmanager
def observe_managers(binding, hooks, store):
    """Future released compile only. Preserve the native call boundary/provenance."""
    original=binding.QnnManager
    counts={'constructors':0,'Compile':0}
    class ManagerProxy:
        def __init__(self,*args,**kwargs):
            counts['constructors']+=1
            self.inner=original(*args,**kwargs)
        def __getattr__(self,name):
            return getattr(self.inner,name)
        def Compile(self,*args,**kwargs):
            counts['Compile']+=1; ordinal=counts['Compile']
            store.json(f'native-compile-{ordinal}-entered.json', {'ordinal':ordinal,'high_level_phase':'one compile invocation','provenance':hooks.provenance})
            result=self.inner.Compile(*args,**kwargs)
            # Native context bytes first; missing optional IO taps cannot erase them.
            data=result.tobytes() if hasattr(result,'tobytes') else bytes(result)
            store.raw(f'native-context-{ordinal}.bin',data)
            hooks.manager_io(self.inner)
            return result
    binding.QnnManager=ManagerProxy
    try:
        yield counts
    finally:
        binding.QnnManager=original


def delegation_report(info):
    rows={name:{'delegated':x.delegated,'non_delegated':x.non_delegated} for name,x in info.delegation_by_operator.items()}
    bad={name:r['non_delegated'] for name,r in rows.items() if r['non_delegated'] and name!='getitem'}
    return {'operators':rows,'delegated_subgraphs':info.num_delegated_subgraphs,'delegated_nodes':info.num_delegated_nodes,
            'nondelegated_tensor_compute':bad,
            'all_tensor_compute_delegated':not bad and info.num_delegated_subgraphs>0 and info.num_delegated_nodes>0}


def final_program_report(program):
    """Audit actual emitted instructions, not merely an early delegation summary."""
    plans=[]
    for plan in program.execution_plan:
        kernels=[]; delegates=[]
        for chain in plan.chains:
            for instruction in chain.instructions:
                arg=instruction.instr_args; kind=type(arg).__name__
                if kind=='KernelCall':
                    op=plan.operators[arg.op_index]; kernels.append({'name':op.name,'overload':op.overload})
                elif kind=='DelegateCall': delegates.append(plan.delegates[arg.delegate_index].id)
                elif kind not in ('MoveCall','FreeCall','JumpFalseCall'):
                    kernels.append({'unknown_instruction':kind})
        plans.append({'name':plan.name,'called_kernels':kernels,'delegate_calls':delegates})
    valid=bool(plans) and all(not p['called_kernels'] and p['delegate_calls'] and set(p['delegate_calls'])=={'QnnBackend'} for p in plans)
    return {'plans':plans,'zero_kernel_calls_all_delegates_qnn':valid,
            'rule':'No approved tensor-free KernelCall exemptions in these fixed probes; Move/Free/Jump are VM plumbing.'}


def load_compiler_api():
    # Only the separately released compile worker calls this import bundle.
    from types import SimpleNamespace
    binding, introspection=introspect_binding()
    from executorch.backends.qualcomm._passes.qnn_pass_manager import get_capture_program_passes
    from executorch.backends.qualcomm._passes import (FoldQDQ,InsertRequantize,InsertIOQDQ,LayoutTransform,FuseConsecutiveCast,FuseConsecutiveTranspose,TagQuantIO)
    from executorch.backends.qualcomm.builders.node_visitor import NodeVisitor
    from executorch.backends.qualcomm.qnn_preprocess import QnnBackend
    from executorch.backends.qualcomm.utils.constants import QCOM_PASS_ACTIVATE_KEY
    from executorch.backends.qualcomm.utils.utils import (generate_htp_compiler_spec,generate_qnn_executorch_compiler_spec,get_soc_to_chipset_map,to_edge_transform_and_lower_to_qnn)
    from executorch.devtools.backend_debug import get_delegation_info
    from executorch.exir import ExecutorchBackendConfig
    from executorch.exir.passes.memory_planning_pass import MemoryPlanningPass
    return SimpleNamespace(**locals())


class RealCompiler:
    def __init__(self,api_loader=None,evidence_kind='native_binding'):
        if api_loader is not None and evidence_kind!='mock':
            raise ValueError('Injected compiler APIs must be labelled mock')
        self.api_loader=api_loader or load_compiler_api
        self.evidence_kind=evidence_kind

    def compile(self,case,store):
        api=self.api_loader();binding=api.binding;introspection=api.introspection
        torch=probe.cpu_torch(); torch.set_num_threads(4)
        model=probe.make_module(case); inputs,_=reviewed_inputs()
        if list(model.parameters()) or list(model.buffers()):raise ValueError('Probe must remain weight-free')
        job=api.get_capture_program_passes();job[api.TagQuantIO][api.QCOM_PASS_ACTIVATE_KEY]=False
        specs=api.generate_qnn_executorch_compiler_spec(soc_model=api.get_soc_to_chipset_map()['SM8550'],
                backend_options=api.generate_htp_compiler_spec(use_fp16=False,use_multi_contexts=False),debug=True,saver=False)
        store.json('compiler-specs.json',[{'key':s.key,'value_hex':s.value.hex()} for s in specs])
        hooks=NativeHooks(store,introspection['dtype_table'],{'kind':self.evidence_kind,'binding':introspection['binding']})
        passes=[*job,api.FoldQDQ,api.InsertRequantize,api.InsertIOQDQ,api.LayoutTransform,api.FuseConsecutiveCast,api.FuseConsecutiveTranspose]
        with hooks.install(passes,api.QnnBackend,binding.PyQnnTensorWrapper,api.NodeVisitor), observe_managers(binding,hooks,store) as counts:
            try:
                with torch.no_grad():
                    edge=api.to_edge_transform_and_lower_to_qnn(model,inputs,specs,passes_job=job,
                         skip_node_id_set=set(),skip_node_op_set=set(),convert_linear_to_conv2d=False)
            finally:
                store.json('capture-summary.json',hooks.summary())
                store.json('native-manager-counts.json',{'provenance':hooks.provenance,**counts})
        delegation=delegation_report(api.get_delegation_info(edge.exported_program().graph_module))
        store.json('delegation.json',delegation)  # preserve even when fallback exists
        program=edge.to_executorch(config=api.ExecutorchBackendConfig(memory_planning_pass=api.MemoryPlanningPass(alloc_graph_input=False)))
        path=store.directory/'probe.pte'
        with path.open('xb') as f:program.write_to_file(f);f.flush();os.fsync(f.fileno())
        final=final_program_report(program.executorch_program);store.json('final-program.json',final)
        return {'pte':file_identity(path),'delegation':delegation,'final_program':final,'capture':hooks.summary()}


def compile_worker(request,root,compiler=None):
    store=probe.Evidence(Path(root)/'compile/data'); state={'case':request['case'],'phase':'compile','status':'started'}
    try:
        adapter=compiler or RealCompiler();state['adapter_kind']=adapter.evidence_kind
        if adapter.evidence_kind!='mock' and request.get('_execution_permission') is not _EXECUTION_PERMISSION:
            raise PermissionError('No validated native execution release')
        state['high_level_compile_invocations']=1
        artifact=adapter.compile(request['case'],store)
        store.json('artifact.json',artifact)
        if not artifact['delegation']['all_tensor_compute_delegated'] or not artifact['final_program']['zero_kernel_calls_all_delegates_qnn']:
            raise ValueError('Fallback/unknown emitted kernel: no runtime permitted')
        if not 0 < artifact['pte']['bytes'] <= MAX_PTE_BYTES:raise ValueError('Not a bounded tiny PTE')
        state.update(status='complete',artifact=artifact)
    except BaseException as error:
        state.update(status='error',error={'type':type(error).__name__,'message':str(error)});raise
    finally:store.json('result.json',state)
    return state


class RealRuntime:
    evidence_kind='native_binding'
    def load(self,path):
        # Loading creates backend state; therefore this is runtime-phase only.
        from executorch.extension.pybindings.portable_lib import _load_for_executorch
        return _load_for_executorch(str(path))


def runtime_abi(meta):
    if meta.num_inputs()!=2 or meta.num_outputs()!=1:raise ValueError('Wrong tiny PTE ABI')
    records=[]
    for info,shape in [(meta.input_tensor_meta(0),probe.HISTORY_SHAPE),(meta.input_tensor_meta(1),probe.PROJECTION_SHAPE),(meta.output_tensor_meta(0),probe.HISTORY_SHAPE)]:
        dtype=info.dtype(); value=int(getattr(dtype,'value',dtype))
        records.append({'shape':list(info.sizes()),'et_scalar_type':value})
        if tuple(info.sizes())!=shape or value!=6:raise ValueError('Expected logical FP32 tiny ABI (ET ScalarType.Float=6)')
    return records


def runtime_worker(request,root,runtime=None):
    root=Path(root);store=probe.Evidence(root/'runtime/data');state={'case':request['case'],'phase':'runtime','status':'started','forward_calls':0}
    try:
        compiled=load_json(root/'compile/data/result.json')
        if compiled['status']!='complete':raise ValueError('Compile phase did not complete')
        a=compiled['artifact'];path=root/'compile/data/probe.pte'
        if not a['delegation']['all_tensor_compute_delegated'] or not a['final_program']['zero_kernel_calls_all_delegates_qnn']:
            raise ValueError('No zero-fallback proof')
        if not 0<path.stat().st_size<=MAX_PTE_BYTES or a['pte']!=file_identity(path):raise ValueError('PTE identity/size mismatch')
        adapter=runtime or RealRuntime();state['adapter_kind']=adapter.evidence_kind
        if adapter.evidence_kind!='mock' and request.get('_execution_permission') is not _EXECUTION_PERMISSION:
            raise PermissionError('No validated native execution release')
        if state['adapter_kind']!=compiled['adapter_kind']:raise ValueError('Mock/native provenance mismatch')
        probe.cpu_torch().set_num_threads(4)
        inputs,before=reviewed_inputs()
        if [probe.digest(x) for x in before]!=request['input_hashes']:raise ValueError('Input hash mismatch')
        for name,data in zip(('history','projection'),before):store.raw(name+'.f32le',data)
        module=adapter.load(path);store.json('abi.json',runtime_abi(module.method_meta('forward')))
        state['forward_calls']=1
        outputs=module.forward(list(inputs))
        # Preserve arbitrary returned tensor bytes before count/shape/dtype/metrics checks.
        torch=probe.cpu_torch();descriptors=[]
        for index,tensor in enumerate(outputs):
            data=tensor.detach().cpu().contiguous().view(torch.uint8).numpy().tobytes()
            descriptor={'shape':list(tensor.shape),'dtype':str(tensor.dtype),**store.raw(f'output-{index}.raw',data)}
            descriptors.append(descriptor)
        store.json('raw-output-descriptors.json',descriptors)
        if len(outputs)!=1 or tuple(outputs[0].shape)!=probe.HISTORY_SHAPE or outputs[0].dtype!=torch.float32:
            raise ValueError('Unexpected output ABI; raw outputs retained')
        comparison=probe.validate_output(request['case'],outputs[0],before)
        comparison['inputs_unchanged']=before==tuple(probe.tensor_bytes(x) for x in inputs)
        store.json('comparison.json',comparison)
        if not comparison['inputs_unchanged']:raise ValueError('Reviewed inputs mutated')
        state.update(status='complete',comparison=comparison, capture=a.get('capture'),
                     claim='one host QNN-x86 tiny observation; equality or difference is not a model/FP32/physical verdict')
    except BaseException as error:
        state.update(status='error',error={'type':type(error).__name__,'message':str(error)});raise
    finally:store.json('result.json',state)
    return state


def run_one_case(request_path,release_path,root,supervisor=supervise):
    """External phase guards; a single case only, no retry/resume or follow-on."""
    root=Path(root).absolute();request=require_release(request_path,release_path,root)
    root.mkdir(parents=True,exist_ok=False);started=time.monotonic();deadline=started+240
    result={'case':request['case'],'status':'started','phases':[],'limits':LIMITS,'automatic_followon':False}
    try:
        for phase,budget in (('compile',120),('runtime',60)):
            if (root/'STOP').exists():raise RuntimeError('coordinator_requested_stop')
            remaining=deadline-time.monotonic()
            if remaining<=0:raise TimeoutError('case active deadline')
            folder=root/phase;folder.mkdir();guard=folder/'guard';guard.mkdir();scratch=folder/'scratch';scratch.mkdir()
            command=['nice','-n','15','ionice','-c','2','-n','7',str(PYTHON),str(Path(__file__).absolute()),
                     '_'+phase+'-worker','--request',str(Path(request_path).absolute()),'--release',str(Path(release_path).absolute()),'--output-dir',str(root)]
            (folder/'command.json').write_text(json.dumps(command)+'\n')
            done=threading.Event()
            def watch_stop():
                while not done.wait(.1):
                    if (root/'STOP').exists():(guard/'STOP').touch();return
            watcher=threading.Thread(target=watch_stop,daemon=True);watcher.start()
            try:
                observed=supervisor(command,guard,min(budget,remaining),env=environment(scratch),grace=20)
            finally:done.set();watcher.join()
            result['phases'].append({'phase':phase,**observed})
            if observed['exit_code']!=0 or observed['reason']!='process_exit':raise RuntimeError(f'{phase} stopped: {observed}')
            phase_result=load_json(folder/'data/result.json')
            if phase_result['status']!='complete':raise RuntimeError(f'{phase} did not complete')
        if time.monotonic()>deadline:raise TimeoutError('case active deadline exceeded')
        result['status']='complete'
    except BaseException as error:
        result.update(status='error',error={'type':type(error).__name__,'message':str(error)});raise
    finally:
        result['elapsed_seconds']=time.monotonic()-started
        with (root/'result.json').open('x') as f:json.dump(result,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode',choices=('inspect-binding','prepare','execute-one','_compile-worker','_runtime-worker'))
    p.add_argument('--case',choices=probe.CASES);p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--binding-report',type=Path);p.add_argument('--request',type=Path);p.add_argument('--release',type=Path)
    args=p.parse_args()
    if args.mode=='inspect-binding':
        store=probe.Evidence(args.output_dir);_,report=introspect_binding();store.json('binding.json',report)
    elif args.mode=='prepare':
        if args.case is None or args.binding_report is None:p.error('prepare needs --case and --binding-report')
        prepare_request(args.case,args.output_dir,args.binding_report)
    else:
        if args.request is None or args.release is None:p.error('execution requires --request and --release')
        if args.mode=='execute-one':run_one_case(args.request,args.release,args.output_dir)
        else:
            request=require_release(args.request,args.release,args.output_dir)
            (compile_worker if args.mode=='_compile-worker' else runtime_worker)(request,args.output_dir)


if __name__=='__main__':main()
