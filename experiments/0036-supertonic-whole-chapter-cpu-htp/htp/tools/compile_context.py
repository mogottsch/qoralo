#!/usr/bin/env python3
"""One bounded fresh QNN constructor/export, zero Run calls, no CPU fallback.

Uses the known0023 host runtime pins, not its consumed per-attempt approvals.
All generated artifacts/logs live in0036/htp/.local. Cleanup targets immutable CID.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time
from materialize import REPO, OLD, sha

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = OLD / 'protocol/next-constructor-request-disk-scratch.json'


def save(path, data):
    with path.open('x') as stream:
        json.dump(data, stream, indent=2, allow_nan=False)
        stream.write('\n')


def verify(record):
    p = Path(record['path'])
    if not p.is_file() or p.stat().st_size != record['bytes'] or sha(p) != record['sha256']:
        raise ValueError('file pin mismatch: '+str(p))


def ios(values):
    return [{'name':v.name, 'type':v.type, 'shape':list(v.shape)} for v in values]


def worker(request, phase):
    import onnx
    rt = json.loads(RUNTIME.read_text())
    verify(request['source'])
    for pin in rt['runtime_pins']:
        verify(pin)
    import onnxruntime as ort
    if ort.__version__ != '1.27.1' or Path(ort.__file__).resolve() != Path(rt['ort_package_file']).resolve():
        raise ValueError('runtime identity differs')
    output = phase / 'data'
    output.mkdir()
    component = request['component']
    descriptor = output / (component+'-context.onnx')
    binary = output / (component+'-context_qnn.bin')
    result = {'status':'started', 'component':component, 'session_Run_calls':0,
              'profiling_enabled':False, 'constructor_calls':0, 'mock':False,
              'runtime_version':ort.__version__, 'source':request['source']}
    started = time.monotonic()
    session = None
    try:
        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        config = {'session.disable_cpu_ep_fallback':'1', 'ep.context_enable':'1',
                  'ep.context_embed_mode':'0', 'ep.context_file_path':str(descriptor)}
        for key,value in config.items():
            options.add_session_config_entry(key,value)
        provider = {**rt['provider_options'], 'backend_path':rt['backend_path']}
        result.update(session_config=config, provider_options=provider)
        result['constructor_calls'] = 1
        before = time.monotonic()
        session = ort.InferenceSession(request['source']['path'], sess_options=options,
                                       providers=[('QNNExecutionProvider',provider)])
        result['constructor_seconds'] = time.monotonic()-before
        result.update(inputs=ios(session.get_inputs()), outputs=ios(session.get_outputs()),
                      providers=session.get_providers())
        save(output/'constructor-receipt.json',result)
        def expected(shapes):
            return [{'name':n,'type':'tensor(int64)' if n=='text_ids' else 'tensor(float)', 'shape':s} for n,s in shapes.items()]
        if result['inputs']!=expected(request['inputs']) or result['outputs']!=expected(request['outputs']):
            raise ValueError('actual QNN ABI differs')
        if 'QNNExecutionProvider' not in result['providers']:
            raise ValueError('QNN provider missing')
        model=onnx.load(str(descriptor),load_external_data=False)
        if len(model.graph.node)!=1 or model.graph.node[0].op_type!='EPContext' or model.graph.node[0].domain!='com.microsoft' or model.graph.initializer:
            raise ValueError('not a single QNN EPContext')
        attrs={a.name:onnx.helper.get_attribute_value(a) for a in model.graph.node[0].attribute}
        if attrs.get('embed_mode')!=0 or (descriptor.parent/attrs['ep_cache_context'].decode()).resolve()!=binary.resolve():
            raise ValueError('external context reference differs')
        result['artifacts']={p.name:{'bytes':p.stat().st_size,'sha256':sha(p)} for p in (descriptor,binary)}
        for pin in rt['runtime_pins']:
            verify(pin)
        verify(request['source'])
        result.update(status='constructor_export_passed_not_execution_proof',all_pins_reverified=True)
    except BaseException as error:
        result.update(status='error',error=str(error))
        raise
    finally:
        session=None
        result.update(elapsed_seconds=time.monotonic()-started,
                      process_ru_maxrss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        for field in ('memory.peak','memory.events','memory.max'):
            p=Path('/sys/fs/cgroup')/field
            result[field]=p.read_text() if p.exists() else None
        save(output/'result.json',result)
    print(component+': '+result['status'],flush=True)


def launch(args):
    if not args.phase.resolve().is_relative_to((ROOT/'.local').resolve()):
        raise ValueError('phase must be private0036 htp/.local')
    rt=json.loads(RUNTIME.read_text())
    graph=json.loads(args.graph_result.read_text())
    verify(graph['derivative'])
    phase=args.phase.resolve()
    phase.mkdir(parents=True,exist_ok=False)
    (phase/'scratch').mkdir()
    request={key:graph[key] for key in ('component','inputs','outputs')}
    request['source']=graph['derivative']
    request['worker_sha256']=sha(__file__)
    save(phase/'request.json',request)
    environment=dict(rt['environment'])
    for k in ('TMPDIR','QAIRT_TMP_DIR','TMP','TEMP'):
        environment[k]=str(phase/'scratch')
    argv=['docker','create','--init','--pull=never','--network=none','--memory=8g','--memory-swap=8g',
          '--cpus=4','--pids-limit=128','--user',f'{os.getuid()}:{os.getgid()}',
          '--label','experiment=0036-supertonic-htp','--workdir',str(phase)]
    for root,readonly in ((REPO,True),(Path(rt['sdk_root']),True),(phase,False)):
        argv+=['--mount',f'type=bind,src={root},dst={root}'+(',readonly' if readonly else '')]
    for key,value in environment.items():
        argv+=['--env',key+'='+value]
    argv += [rt['docker_image_id'],'python3',str(Path(__file__).resolve()),'--worker','--phase',str(phase)]
    save(phase/'command.json',{'argv':argv,'bounds':{'cpus':4,'memory_bytes':8*1024**3,'extra_swap':0,'worker_seconds':520,'cleanup_seconds':20}})
    cid=None
    started=time.monotonic()
    result={'status':'started'}
    with (REPO/'artifacts/locks/heavy-ram.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:
            create=subprocess.run(argv,capture_output=True,text=True,check=True,timeout=20)
            cid=create.stdout.strip()
            if len(cid)!=64 or any(c not in '0123456789abcdef' for c in cid):
                raise ValueError('Docker did not return a full immutable CID')
            (phase/'container-id.txt').write_text(cid+'\n')
            with (phase/'stdout.log').open('xb') as out,(phase/'stderr.log').open('xb') as err:
                execution=subprocess.run(['nice','-n','15','docker','start','-a',cid],stdout=out,stderr=err,timeout=520)
            result.update(exit_code=execution.returncode,status='passed' if execution.returncode==0 else 'failed')
        except BaseException as error:
            result.update(status='error',error=str(error))
            raise
        finally:
            if cid:
                before=subprocess.run(['docker','container','inspect',cid],capture_output=True,text=True,timeout=10)
                (phase/'container-final-inspect.json').write_text(before.stdout or '{}')
                removal=subprocess.run(['docker','rm','-f',cid],capture_output=True,text=True,timeout=10)
                absent=subprocess.run(['docker','container','inspect',cid],capture_output=True,text=True,timeout=10)
                result.update(removed=removal.returncode==0,container_absent=absent.returncode!=0 and 'No such' in absent.stderr)
            result['elapsed_seconds']=time.monotonic()-started
            save(phase/'launcher-result.json',result)
    if result['status']!='passed' or not result.get('container_absent'):
        raise RuntimeError('constructor or owned-container cleanup failed; inspect private retained evidence')
    print(request['component']+': constructor/export passed; container absent',flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--worker',action='store_true')
    p.add_argument('--phase',type=Path,required=True)
    p.add_argument('--graph-result',type=Path)
    args=p.parse_args()
    if args.worker:
        request=json.loads((args.phase/'request.json').read_text())
        if request['worker_sha256']!=sha(__file__):
            raise ValueError('worker drift')
        worker(request,args.phase)
    else:
        if args.graph_result is None:
            p.error('--graph-result is required for host launch')
        launch(args)


if __name__=='__main__':
    main()
