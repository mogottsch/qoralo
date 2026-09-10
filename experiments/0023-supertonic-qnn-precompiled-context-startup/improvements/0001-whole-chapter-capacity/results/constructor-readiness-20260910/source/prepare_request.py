#!/usr/bin/env python3
"""Read/hash existing files and emit NOT_APPROVED constructor request; no runtime import."""
import hashlib
import json
from pathlib import Path

TRACK=Path(__file__).resolve().parents[3]
REPO=TRACK.parents[3]
SDK=Path('/home/moritz/opt/qairt/2.49.0.260730')
BUILD=REPO/'experiments/0010-supertonic-qnn-htp-feasibility/.local/ort-v1.27.1-qnn-2.49.0-host-patched-a08e17/Release'
CAPI=BUILD/'onnxruntime/capi'
PHASE=TRACK/'.local/constructor-duration-t2048-attempt-01'


def record(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return {'path':str(path),'bytes':path.stat().st_size,'sha256':h.hexdigest()}


def main():
    source=TRACK/'.local/materialization-20260910/attempt-01/duration/data/duration.onnx'
    inputs=[{'name':'text_ids','type':'tensor(int64)','shape':[1,2048]},{'name':'style_dp','type':'tensor(float)','shape':[1,8,16]},{'name':'text_mask','type':'tensor(float)','shape':[1,1,2048]}]
    library_names=['libQnnHtp.so','libHtpPrepare.so','libQnnHtpQemu.so','libQnnSystem.so']
    pins=[record(BUILD/'onnxruntime/__init__.py')]
    pins += [record(CAPI/n) for n in ['onnxruntime_pybind11_state.so','libonnxruntime.so.1.27.1','libonnxruntime_providers_qnn.so','libonnxruntime_providers_shared.so',*library_names]]
    pins += [record(SDK/'lib/x86_64-linux-clang'/n) for n in library_names]
    request={'status':'NOT_APPROVED_NO_CONSTRUCTOR_EXECUTED','component':'duration','source':record(source),
        'expected_inputs':inputs,'expected_outputs':[{'name':'duration','type':'tensor(float)','shape':[1]}],
        'ort_version':'1.27.1','qairt_version':'2.49.0.260730','provider_options':{'offload_graph_io_quantization':'0','htp_performance_mode':'burst','soc_model':'43'},
        'backend_path':str(SDK/'lib/x86_64-linux-clang/libQnnHtp.so'),'sdk_root':str(SDK),
        'ort_package_file':str(BUILD/'onnxruntime/__init__.py'),'runtime_pins':pins,
        'pin_scope':'Prospective selected runtime/import/search-path files, not a complete dynamic dependency inventory or retroactive binary proof.',
        'session_run_calls_allowed':0,'constructor_calls_allowed':1,'mock':False,
        'phase_dir':str(PHASE),'output_dir':str(PHASE/'data'),'approval_path':str(TRACK/'.local/approvals/duration-context.json'),
        'container_name':'supertonic-chapter-duration-context-attempt-01',
        'docker_image_id':'sha256:b170f55a61548cc3a78eb667837934e0f2f8659bf7cd0db7a71ec40e90d2f321',
        'docker_image_observation':'Existing image ID from read-only docker image inspect; no container started during readiness.',
        'worker_sha256':record(TRACK/'tools/compile_duration_context.py')['sha256'],
        'launcher_sha256':record(TRACK/'tools/run_duration_constructor.py')['sha256'],
        'guard_sha256':record(REPO/'experiments/0032-qwen-3.5-2b-android-qnn-htp/tools/qwen_host_guard.py')['sha256'],
        'environment':{'HOME':'/tmp','TMPDIR':str(PHASE/'scratch'),'PYTHONDONTWRITEBYTECODE':'1',
            'PYTHONPATH':str(BUILD),'LD_LIBRARY_PATH':':'.join(map(str,[BUILD,CAPI,SDK/'lib/x86_64-linux-clang'])),
            'OMP_NUM_THREADS':'4','MKL_NUM_THREADS':'4','OPENBLAS_NUM_THREADS':'4','NUMEXPR_NUM_THREADS':'4'},
        'bounds':{'worker_seconds':520,'TERM_grace_seconds':20,'total_expected_bound_seconds':600,'Docker_memory_bytes':8589934592,'Docker_swap_extra_bytes':0,'cpus':4,'network':False,'retries':0},
        'profiling':'disabled; constructor/actualI/O/external-artifact gates only, not neural execution evidence',
        'borrowed_option_source':record(REPO/'experiments/0023-supertonic-qnn-precompiled-context-startup/tools/qnn_context_component.py'),
        'not_inherited':['historical239/238 SPECS','forced Session.run','inference profiling/pass claims'],
        'phone_or_pack_replacement_allowed':False}
    request_file=TRACK/'protocol/next-constructor-request.json'
    with request_file.open('x') as f:json.dump(request,f,indent=2);f.write('\n')
    release={'approved':False,'permission':'one_duration_EPContext_constructor_no_Run','request_sha256':record(request_file)['sha256'],'worker_sha256':request['worker_sha256'],'output_dir':request['output_dir']}
    with (TRACK/'protocol/next-constructor-release.NOT_APPROVED.json').open('x') as f:json.dump(release,f,indent=2);f.write('\n')
    print(json.dumps({'request':record(request_file),'runtime_pin_count':len(pins),'SDK_or_ORT_imports':0,'constructor_calls':0},indent=2))


if __name__=='__main__':main()
