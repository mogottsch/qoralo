#!/usr/bin/env python3
"""One paired weight-free K-cache probe. Fresh evidence paths; no automatic retry."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import sys
import time

EXP=Path(__file__).resolve().parents[1]
DESIGN=EXP/'results/persistent-boundary-source-design-20260911'
PYTHON=EXP.parents[1]/'artifacts/venv-executorch-1.2/bin/python'
SDK=Path('/home/moritz/opt/qairt/2.49.0.260730')
CACHE=(1,2,256,4095)
KEY=(1,2,256,1)
OUTPUT=(1,2,256,4096)
SHAPES=(CACHE,KEY,CACHE,KEY)
NAMES=('cache3','key3','cache15','key15')
ANCHOR=(0,1,24,0)
ANCHOR_VALUE=10.028990745544434
MAX_PTE=16*1024*1024


def load(path):return json.loads(Path(path).read_text())


def identity(path):
    path=Path(path);h=hashlib.sha256()
    with path.open('rb') as f:
        while b:=f.read(1024*1024):h.update(b)
    return {'path':str(path.resolve()),'bytes':path.stat().st_size,'sha256':h.hexdigest()}


def save(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())


def domains():
    s=load(DESIGN/'selected-states.json')['states'];cats=load(DESIGN/'selected-cat-paths.json')['selected_paths'];out=[]
    for row,cat in zip(s,cats,strict=True):
        assert row['state_index']==cat['state_index']
        assert cat['cat_encoding']==cat['current_key_encoding']
        out.append({'state_index':row['state_index'],'input':row['input']['unique_domain'],'output':cat['cat_encoding']})
    assert [r['state_index'] for r in out]==[3,15]
    return out


def arrays():
    import numpy as np
    v=[np.zeros(s,dtype='<f4') for s in SHAPES]
    v[0][ANCHOR]=ANCHOR_VALUE;v[0][0,0,0,0]=1;v[2][ANCHOR]=1
    return v


def qdq(a,e):
    import numpy as np
    code=np.rint(np.multiply(a,np.float32(1.0/e['scale']),dtype=np.float32))
    code=np.clip(np.add(code,np.float32(e['zero_point']),dtype=np.float32),0,65535)
    return np.multiply(np.subtract(code,np.float32(e['zero_point']),dtype=np.float32),np.float32(e['scale']),dtype=np.float32)


def oracle(inputs,enc,skip_input=False):
    import numpy as np
    result=[]
    for i,d in enumerate(enc):
        old=inputs[2*i] if skip_input else qdq(inputs[2*i],d['input'])
        new=qdq(inputs[2*i+1],d['output'])
        result.append(qdq(np.concatenate((old,new),axis=-1),d['output']))
    return result


def module(enc):
    import torch
    import torch.ao.quantization.fx._decomposed  # public CPU Q/DQ registration
    def apply(x,e):
        args=(e['scale'],e['zero_point'],0,65535,torch.int32)
        return torch.ops.quantized_decomposed.dequantize_per_tensor.default(torch.ops.quantized_decomposed.quantize_per_tensor.default(x,*args),*args)
    class PairedK(torch.nn.Module):
        def forward(self,cache3,key3,cache15,key15):
            a=torch.cat((apply(cache3,enc[0]['input']),apply(key3,enc[0]['output'])),dim=-1)
            b=torch.cat((apply(cache15,enc[1]['input']),apply(key15,enc[1]['output'])),dim=-1)
            return apply(a,enc[0]['output']),apply(b,enc[1]['output'])
    return PairedK().eval()


def source_and_runtime_files():
    site=PYTHON.parent.parent/'lib/python3.11/site-packages';et=site/'executorch';q=et/'backends/qualcomm'
    files=[Path(__file__),EXP/'tools/qwen_host_guard.py',DESIGN/'selected-states.json',DESIGN/'selected-cat-paths.json',PYTHON.resolve()]
    files += [EXP/'tools'/n for n in ('conv_history_qnn_adapter.py','conv_history_native_hooks.py','conv_history_probe.py','conv_history_probe_hooks.py','audit_conv_history_metadata.py')]
    files += [q/n for n in ('qnn_preprocess.py','builders/node_visitor.py','builders/utils.py','builders/op_cat.py','builders/op_quantize.py','builders/op_dequantize.py','builders/op_to.py','utils/utils.py','utils/qnn_manager_lifecycle.py','_passes/qnn_pass_manager.py','_passes/annotate_quant_attrs.py','_passes/fold_qdq.py','_passes/insert_io_qdq.py','_passes/insert_requantize.py','_passes/layout_transform.py')]
    files += list((q/'python').glob('PyQnnManagerAdaptor*.so'))
    files += list((et/'extension/pybindings').glob('*.so'))
    files += [site/'torch/lib'/n for n in ('libtorch_cpu.so','libtorch_python.so','libc10.so')]
    files += [SDK/'lib/x86_64-linux-clang'/n for n in ('libQnnHtp.so','libQnnHtpQemu.so','libQnnSystem.so')]
    assert files and all(f.is_file() for f in files)
    return list(dict.fromkeys(files))


def verify(request):
    for r in request['pins']+request['inputs']+request['references']:
        if identity(r['path'])!=r:raise ValueError('Changed binding: '+r['path'])
    assert resource.getrlimit(resource.RLIMIT_AS)[0]==4294967296
    assert os.sched_getaffinity(0)=={0,1,2,3}
    assert os.environ['QNN_SDK_ROOT']==str(SDK)


def prepared_inputs(request):
    import numpy as np
    return [np.fromfile(r['path'],dtype='<f4').reshape(shape) for r,shape in zip(request['inputs'],SHAPES,strict=True)]


def prepare(root):
    import numpy as np
    import torch
    torch.set_num_threads(4);torch.set_num_interop_threads(1)
    d=root/'prepare';d.mkdir();state={'status':'started','CPU_reference_forwards':0,'SDK_calls':0};save(d/'started.json',state)
    try:
        enc=domains();v=arrays();model=module(enc);assert not list(model.parameters()) and not list(model.buffers())
        inputs=[];references=[]
        for name,a in zip(NAMES,v):
            path=d/(name+'.f32le');a.tofile(path);inputs.append(identity(path))
        expected=oracle(v,enc);alternative=oracle(v,enc,True)
        for label,vs in [('fullchain',expected),('catonly_hypothesis',alternative)]:
            for i,a in enumerate(vs):
                path=d/f'{label}-{i}.f32le';a.tofile(path);references.append(identity(path))
        state['CPU_reference_forwards']=1
        with torch.no_grad():actual=model(*[torch.from_numpy(a) for a in v])
        match=[]
        for i,a in enumerate(actual):
            path=d/f'cpu-output-{i}.f32le';a.numpy().tofile(path);match.append(np.array_equal(a.numpy().view('u4'),expected[i].view('u4')))
        save(d/'cpu-reference.json',{'all_bytes_match':match,'elements_per_output':expected[0].size,
             'fullchain_anchors':[float(a[ANCHOR]) for a in expected],
             'catonly_hypothesis_anchors':[float(a[ANCHOR]) for a in alternative],
             'reference_only_not_native':True})
        assert all(match) and abs(float(expected[0][ANCHOR])-float(alternative[0][ANCHOR]))>3
        request={'case':'paired_K3_K15_consumer','authorization':'Moritz standing proceed-until-done and Pi explicit paired K-cache preparation+bounded compile/load/forward direction,2026-09-11; no additional approval gate.',
            'root':str(root),'domains':enc,'input_shapes':SHAPES,'output_shapes':[OUTPUT,OUTPUT],
            'pins':[identity(p) for p in source_and_runtime_files()], 'inputs':inputs,'references':references,
            'limits':{'AS_bytes':4294967296,'CPUs':[0,1,2,3],'compile_seconds':120,'runtime_seconds':60,'active_seconds':240,'grace_seconds':20,'PTE_max_bytes':MAX_PTE},
            'compile_options':{'TagQuantIO':False,'use_fp16':False,'use_multi_contexts':False,'debug':True,'saver':False,'soc':'SM8550','host_simulation':True},
            'scope':'one high-level compile, one load, one paired forward; no learned weights or full-model/phone calls; no automatic retry',
            'runtime_pin_limit':'selected route/native/Torch files, not an exhaustive OS dependency inventory'}
        save(root/'request.json',request);state.update(status='complete',inputs=inputs,reference_match=match,torch=torch.__version__,numpy=np.__version__)
    except BaseException as e:state.update(status='error',error=repr(e));raise
    finally:save(d/'result.json',state)


def compile_phase(root,request):
    from conv_history_qnn_adapter import load_compiler_api,observe_managers,delegation_report,final_program_report
    from conv_history_native_hooks import NativeHooks
    from conv_history_probe import Evidence
    import torch
    torch.set_num_threads(4);torch.set_num_interop_threads(1)
    store=Evidence(root/'compile/data');state={'status':'started','high_level_compile_calls':0};store.json('started.json',state)
    try:
        api=load_compiler_api();model=module(request['domains']);assert not list(model.parameters()) and not list(model.buffers())
        inputs=[torch.from_numpy(a) for a in prepared_inputs(request)]
        job=api.get_capture_program_passes();job[api.TagQuantIO][api.QCOM_PASS_ACTIVATE_KEY]=False
        specs=api.generate_qnn_executorch_compiler_spec(soc_model=api.get_soc_to_chipset_map()['SM8550'],backend_options=api.generate_htp_compiler_spec(use_fp16=False,use_multi_contexts=False),debug=True,saver=False)
        store.json('compiler-specs.json',[{'key':s.key,'value_hex':s.value.hex()} for s in specs])
        hooks=NativeHooks(store,api.introspection['dtype_table'],{'kind':'actual_host_QNN_binding','binding':api.introspection['binding']})
        passes=[*job,api.FoldQDQ,api.InsertRequantize,api.InsertIOQDQ,api.LayoutTransform,api.FuseConsecutiveCast,api.FuseConsecutiveTranspose]
        state['high_level_compile_calls']=1;t=time.monotonic()
        with hooks.install(passes,api.QnnBackend,api.binding.PyQnnTensorWrapper,api.NodeVisitor),observe_managers(api.binding,hooks,store) as counts:
            try:
                with torch.no_grad():edge=api.to_edge_transform_and_lower_to_qnn(model,tuple(inputs),specs,passes_job=job,skip_node_id_set=set(),skip_node_op_set=set(),convert_linear_to_conv2d=False)
            finally:
                store.json('capture-summary.json',hooks.summary());store.json('manager-counts.json',counts)
        state['lowering_seconds']=time.monotonic()-t
        delegation=delegation_report(api.get_delegation_info(edge.exported_program().graph_module));store.json('delegation.json',delegation)
        program=edge.to_executorch(config=api.ExecutorchBackendConfig(memory_planning_pass=api.MemoryPlanningPass(alloc_graph_input=False)))
        path=store.directory/'probe.pte'
        with path.open('xb') as f:program.write_to_file(f);f.flush();os.fsync(f.fileno())
        final=final_program_report(program.executorch_program);store.json('final-program.json',final);state['artifact']=identity(path)
        assert delegation['all_tensor_compute_delegated'] and delegation['delegated_subgraphs']==1
        assert final['zero_kernel_calls_all_delegates_qnn'] and 0<path.stat().st_size<=MAX_PTE
        verify(request);state.update(status='complete',postpins='unchanged',delegation=delegation,final_program=final)
    except BaseException as e:state.update(status='error',error=repr(e));raise
    finally:state['peak_rss_kib']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss;store.json('result.json',state)


def compare(a,ref):
    import numpy as np
    finite=np.isfinite(a);mask=finite & np.isfinite(ref);diff=np.abs(a.astype('f8')-ref.astype('f8'))
    return {'finite_values':int(finite.sum()),'total_values':int(a.size),'bitwise_equal_values':int((a.view('u4')==ref.view('u4')).sum()),
            'max_abs_fp64':float(diff[mask].max()) if mask.any() else None,'mean_abs_fp64':float(diff[mask].mean()) if mask.any() else None,
            'anchor_actual':float(a[ANCHOR]) if np.isfinite(a[ANCHOR]) else None,'anchor_reference':float(ref[ANCHOR])}


def runtime_phase(root,request):
    import numpy as np
    import torch
    torch.set_num_threads(4);torch.set_num_interop_threads(1)
    from conv_history_probe import Evidence
    from executorch.extension.pybindings.portable_lib import _load_for_executorch
    store=Evidence(root/'runtime/data');state={'status':'started','load_calls':0,'forward_calls':0};store.json('started.json',state)
    try:
        compiled=load(root/'compile/data/result.json');assert compiled['status']=='complete'
        assert identity(compiled['artifact']['path'])==compiled['artifact']
        v=prepared_inputs(request);inputs=[torch.from_numpy(a) for a in v]
        state['load_calls']=1;t=time.monotonic();m=_load_for_executorch(compiled['artifact']['path']);state['load_seconds']=time.monotonic()-t
        meta=m.method_meta('forward');assert meta.num_inputs()==4 and meta.num_outputs()==2
        abi=[]
        for info,shape in [(meta.input_tensor_meta(i),s) for i,s in enumerate(SHAPES)]+[(meta.output_tensor_meta(i),OUTPUT) for i in range(2)]:
            dtype=info.dtype();kind=int(getattr(dtype,'value',dtype));abi.append({'shape':list(info.sizes()),'et_scalar_type':kind});assert tuple(info.sizes())==shape and kind==6
        store.json('abi.json',abi);state['forward_calls']=1;t=time.monotonic();outputs=m.forward(inputs);state['forward_seconds']=time.monotonic()-t
        records=[]
        for i,a in enumerate(outputs):
            raw=a.detach().cpu().contiguous().view(torch.uint8).numpy().tobytes();info=store.raw(f'output-{i}.raw',raw)
            records.append({'shape':list(a.shape),'dtype':str(a.dtype),**info})
        store.json('raw-output-descriptors.json',records)
        assert len(outputs)==2 and all(tuple(a.shape)==OUTPUT and a.dtype==torch.float32 for a in outputs)
        comparisons=[]
        for i,a in enumerate(outputs):
            refs={label:np.fromfile(root/f'prepare/{label}-{i}.f32le',dtype='<f4').reshape(OUTPUT) for label in ('fullchain','catonly_hypothesis')}
            comparisons.append({'state_index':(3,15)[i],**{label:compare(a.numpy(),ref) for label,ref in refs.items()}})
        store.json('comparison.json',comparisons)
        for a,r in zip(v,request['inputs']):assert hashlib.sha256(a.tobytes()).hexdigest()==r['sha256']
        verify(request);state.update(status='complete',comparisons=comparisons,inputs_unchanged=True,postpins='unchanged',
            claim='one paired host QNN-x86 synthetic consumer observation; not physical HTP measurement, internal finalized-code capture or full-model/logit evidence')
    except BaseException as e:state.update(status='error',error=repr(e));raise
    finally:state['peak_rss_kib']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss;store.json('result.json',state)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('phase',choices=('prepare','compile','runtime'));ap.add_argument('--root',type=Path,required=True);ap.add_argument('--request-sha');a=ap.parse_args();root=a.root.resolve()
    assert resource.getrlimit(resource.RLIMIT_AS)[0]==4294967296 and os.sched_getaffinity(0)=={0,1,2,3}
    if a.phase=='prepare':prepare(root)
    else:
        assert identity(root/'request.json')['sha256']==a.request_sha
        request=load(root/'request.json');assert request['root']==str(root);verify(request)
        (compile_phase if a.phase=='compile' else runtime_phase)(root,request)


if __name__=='__main__':main()
