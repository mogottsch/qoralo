#!/usr/bin/env python3
"""One separately released unchanged vocoder diagnostic constructor. No forward API.

Default plan validates metadata only. Execution needs a fresh, exact request/worker-
bound release. Tests inject a fake ORT object; real ORT is imported only after gate.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import resource
import sys
import time

def tensor(name,shape):
    return {'name':name,'type':'tensor(int64)' if name=='text_ids' else 'tensor(float)','shape':shape}

SPECS={
    'text':([tensor('text_ids',[1,2048]),tensor('style_ttl',[1,50,256]),tensor('text_mask',[1,1,2048])],
            [tensor('text_emb',[1,256,2048])]),
    'vector':([tensor('noisy_latent',[1,144,2048]),tensor('text_emb',[1,256,2048]),tensor('style_ttl',[1,50,256]),
               tensor('latent_mask',[1,1,2048]),tensor('text_mask',[1,1,2048]),tensor('current_step',[1]),tensor('total_step',[1])],
              [tensor('denoised_latent',[1,144,2048])]),
    'vocoder':([tensor('latent',[1,144,2048])],[tensor('wav_tts',[1,6291456])]),
}


def io_sha256(component):
    inputs,outputs=SPECS[component]
    return hashlib.sha256(json.dumps({'inputs':inputs,'outputs':outputs},sort_keys=True,separators=(',',':')).encode()).hexdigest()
PROVIDER={'offload_graph_io_quantization':'0','htp_performance_mode':'burst','soc_model':'43'}
DIAGNOSTICS={'global_log_severity':0,'global_log_verbosity':1,'session_log_severity':0,'session_log_verbosity':1,
             'cgroup_scope':'own_process_unified_v2','capture':['before_constructor','after_exception_or_close']}


def cgroup_snapshot(proc=Path('/proc')):
    """Read only this process's cgroup v2 scope; never substitute host/root metrics."""
    result={'pid':os.getpid(),'time_ns':time.time_ns(),'scope':'own_process_unified_v2',
            'proc_self_cgroup':None,'mountinfo_line':None,'directory':None,'scope_error':None,
            'files':{name:{'raw':None,'error':'scope unresolved'} for name in ['memory.current','memory.peak','memory.max','memory.events']}}
    try:
        result['proc_self_cgroup']=(proc/'self/cgroup').read_text()
        groups=[line[3:] for line in result['proc_self_cgroup'].splitlines() if line.startswith('0::')]
        if len(groups)!=1:raise ValueError('no unique unified cgroup v2 membership')
        membership=PurePosixPath(groups[0]);mounts=[]
        for line in (proc/'self/mountinfo').read_text().splitlines():
            fields=line.split();separator=fields.index('-')
            if fields[separator+1]=='cgroup2':mounts.append((line,fields[3],fields[4]))
        if len(mounts)!=1:raise ValueError('no unique cgroup2 mount')
        line,root,mount=mounts[0]
        if '\\' in root or '\\' in mount:raise ValueError('escaped cgroup mount path unsupported; no guessed scope')
        result['mountinfo_line']=line
        if membership==PurePosixPath('/'):
            directory=Path(mount)  # own namespace root, not an assumed host hierarchy root
        else:
            directory=Path(mount)/membership.relative_to(PurePosixPath(root))
        result['directory']=str(directory)
        for name in result['files']:
            try:result['files'][name]={'raw':(directory/name).read_text(),'error':None}
            except (OSError,UnicodeError) as error:result['files'][name]={'raw':None,'error':type(error).__name__+': '+str(error)}
    except (OSError,ValueError,IndexError,UnicodeError) as error:
        result['scope_error']=type(error).__name__+': '+str(error)
    return result


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()


def write(path,value):
    with Path(path).open('x') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')


def verify_record(record):
    path=Path(record['path'])
    if path.is_symlink() or not path.is_file() or path.stat().st_size!=record['bytes'] or sha(path)!=record['sha256']:
        raise ValueError('pinned file changed: '+str(path))


def authorize(request_path,release_path):
    request=json.loads(request_path.read_text());release=json.loads(release_path.read_text())
    component=request['component']
    if component!='vocoder' or request.get('diagnostics')!=DIAGNOSTICS:raise ValueError('only unchanged vocoder diagnostic scope is eligible')
    expected={'approved':True,'permission':'one_vocoder_verbose_cgroup_constructor_no_Run',
              'request_sha256':sha(request_path),'worker_sha256':sha(__file__),
              'output_dir':request['output_dir']}
    if release!=expected or request['worker_sha256']!=sha(__file__):raise ValueError('missing/mismatched constructor-only release')
    inputs,outputs=SPECS[component]
    if request['expected_inputs']!=inputs or request['expected_outputs']!=outputs or request['io_sha256']!=io_sha256(component):
        raise ValueError('only exact T2048/L2048 component ABI is released')
    if request['ort_version']!='1.27.1' or request['qairt_version']!='2.49.0.260730' or request['provider_options']!=PROVIDER:
        raise ValueError('runtime/provider options differ')
    if request['session_run_calls_allowed']!=0 or request['constructor_calls_allowed']!=1:raise ValueError('invalid call budget')
    return request


def descriptor_contract(descriptor,binary,component):
    if not descriptor.is_file() or not 0<descriptor.stat().st_size<=1048576 or not binary.is_file() or binary.stat().st_size<=0:
        raise ValueError('missing/invalid external descriptor or context binary')
    import onnx
    model=onnx.load(str(descriptor),load_external_data=False)
    if len(model.graph.node)!=1 or model.graph.node[0].op_type!='EPContext' or model.graph.initializer:
        raise ValueError('descriptor must contain only one EPContext and no initializers')
    node=model.graph.node[0]
    if node.domain!='com.microsoft':raise ValueError('unexpected EPContext domain')
    def io(values):
        types={onnx.TensorProto.INT64:'tensor(int64)',onnx.TensorProto.FLOAT:'tensor(float)'}
        return [{'name':v.name,'type':types.get(v.type.tensor_type.elem_type),'shape':[d.dim_value if d.HasField('dim_value') else d.dim_param for d in v.type.tensor_type.shape.dim]} for v in values]
    inputs,outputs=SPECS[component]
    if io(model.graph.input)!=inputs or io(model.graph.output)!=outputs:raise ValueError('descriptor ABI differs from actual required I/O')
    attrs={a.name:onnx.helper.get_attribute_value(a) for a in node.attribute}
    if attrs.get('embed_mode')!=0:raise ValueError('embedded context is forbidden')
    cache=attrs.get('ep_cache_context')
    if not isinstance(cache,bytes):raise ValueError('missing external context reference')
    referenced=(descriptor.parent/cache.decode()).resolve()
    if referenced!=binary.resolve():raise ValueError('descriptor references an unexpected external binary')
    return {'node_domain':node.domain,'node_op':node.op_type,'embed_mode':0,'external_binary':cache.decode(),
            'descriptor':{'bytes':descriptor.stat().st_size,'sha256':sha(descriptor)},
            'binary':{'bytes':binary.stat().st_size,'sha256':sha(binary)}}


def construct_only(request,ort,output):
    """ORT dependency is injected; no forward method is referenced or invoked."""
    component=request['component'];inputs,outputs=SPECS[component]
    output.mkdir(parents=True,exist_ok=False)
    descriptor=output/f'{component}-context.onnx';binary=output/f'{component}-context_qnn.bin'
    result={'status':'started','component':component,'io_sha256':io_sha256(component),'evidence_class':'constructor_only_not_execution_or_model_quality',
            'python_InferenceSession_calls':0,'Session_Run_calls':0,'mock':bool(request.get('mock',False))}
    session=None;start=time.monotonic()
    write(output/'cgroup-before.json',cgroup_snapshot())
    try:
        if ort.__version__!=request['ort_version']:raise ValueError('actual ORT version differs')
        ort.set_default_logger_severity(0)
        ort.set_default_logger_verbosity(1)
        options=ort.SessionOptions()
        options.log_severity_level=0;options.log_verbosity_level=1
        result['diagnostics']=DIAGNOSTICS
        options.intra_op_num_threads=1;options.inter_op_num_threads=1
        options.execution_mode=ort.ExecutionMode.ORT_SEQUENTIAL
        options.graph_optimization_level=ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        config={'session.disable_cpu_ep_fallback':'1','ep.context_enable':'1','ep.context_embed_mode':'0','ep.context_file_path':str(descriptor)}
        for key,value in config.items():options.add_session_config_entry(key,value)
        provider={**PROVIDER,'backend_path':request['backend_path']}
        result.update(session_config=config,provider_options=provider,intra_op_threads=1,inter_op_threads=1)
        result['python_InferenceSession_calls']=1
        before=time.monotonic()
        session=ort.InferenceSession(request['source']['path'],sess_options=options,providers=[('QNNExecutionProvider',provider)])
        result['constructor_seconds']=time.monotonic()-before
        def rows(values):return [{'name':v.name,'type':v.type,'shape':list(v.shape)} for v in values]
        result['actual_inputs']=rows(session.get_inputs());result['actual_outputs']=rows(session.get_outputs())
        result['session_providers']=list(session.get_providers())
        # Raw receipt precedes classification; provider availability != execution.
        write(output/'constructor-receipt.json',result)
        if result['actual_inputs']!=inputs or result['actual_outputs']!=outputs:raise ValueError('actual constructor I/O differs')
        if 'QNNExecutionProvider' not in result['session_providers']:raise ValueError('QNN provider absent')
        result['external_context']=descriptor_contract(descriptor,binary,component)
        result['status']='constructor_and_artifact_gates_passed_no_execution'
    except BaseException as error:
        result.update(status='error',error={'type':type(error).__name__,'message':str(error)})
        raise
    finally:
        session=None
        write(output/'cgroup-after.json',cgroup_snapshot())
        result['elapsed_seconds']=time.monotonic()-start
        result['process_ru_maxrss_kib']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        result['retained_files']=[{'name':p.name,'bytes':p.stat().st_size} for p in sorted(output.iterdir()) if p.is_file()]
        write(output/'result.json',result)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--request',type=Path,required=True);p.add_argument('--release',type=Path)
    p.add_argument('--execute',action='store_true');a=p.parse_args()
    if not a.execute:
        request=json.loads(a.request.read_text())
        print(json.dumps({'status':'PLAN_ONLY_NO_NATIVE_IMPORT','request_sha256':sha(a.request),'component':request['component'],'source':request['source'],'output_dir':request['output_dir']},indent=2));return
    if a.release is None:p.error('--execute requires separate exact release')
    request=authorize(a.request,a.release)
    output=Path(request['output_dir'])
    if output.exists():raise FileExistsError('fresh output directory required; no resume/retry')
    verify_record(request['source'])
    for record in request['runtime_pins']:verify_record(record)
    import onnxruntime as ort
    if Path(ort.__file__).resolve()!=Path(request['ort_package_file']).resolve():raise ValueError('unexpected ORT Python package')
    result=construct_only(request,ort,output)
    verification={'status':'started'}
    try:
        verify_record(request['source'])
        for record in request['runtime_pins']:verify_record(record)
        verification['status']='all_pins_unchanged'
    except BaseException as error:
        verification.update(status='error',message=str(error));raise
    finally:write(output/'final-verification.json',verification)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
