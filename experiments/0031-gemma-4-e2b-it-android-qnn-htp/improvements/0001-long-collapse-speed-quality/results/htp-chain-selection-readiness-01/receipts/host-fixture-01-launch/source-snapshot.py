#!/usr/bin/env python3
"""Actual host qnn-net-run named selection on tiny authored CPU graphs, not a model."""
import argparse
import hashlib
import json
from pathlib import Path
import os
import shutil
import subprocess
import time

TRACK=Path(__file__).resolve().parents[1]
SDK=Path('/home/moritz/opt/qairt/2.49.40.260810')
GRAPHS=['selection_power','selection_chain','selection_exposed']


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(out):
    import numpy as np
    import onnx
    import qairt
    from onnx import helper as h,TensorProto as T,numpy_helper as n
    start=time.monotonic();out.mkdir(parents=True,exist_ok=False);os.umask(0o077);dlcs=[];lists=[]
    for index,name in enumerate(GRAPHS):
        folder=out/name;folder.mkdir();model=h.make_model(h.make_graph([h.make_node('Add',['value','one'],['sum'],name='authored_add_one')],name,[h.make_tensor_value_info('value',T.FLOAT,[1])],[h.make_tensor_value_info('sum',T.FLOAT,[1])],[n.from_array(np.array([1],np.float32),'one')]),opset_imports=[h.make_opsetid('',13)]);model.ir_version=8;onnx.checker.check_model(model);path=folder/(name+'.onnx');onnx.save(model,path)
        converted=qairt.convert(path,backend='CPU',float_precision=32,float_bias_precision=32,input_tensor_config=[{'name':'value','layout':'NONTRIVIAL'}]);dlc=folder/(name+'.dlc');shutil.copyfile(converted.module.path,dlc);dlcs.append(dlc)
        value=folder/'input.float32';np.array([10**index],dtype='<f4').tofile(value);listing=folder/'input-list.txt';listing.write_text('value:='+str(value)+'\n');lists.append(listing)
    records=[];env={'PATH':'/usr/bin:/bin','HOME':str(out),'LD_LIBRARY_PATH':str(TRACK.parents[1]/'.local/host-libs')+':'+str(SDK/'lib/x86_64-linux-clang')}
    for selected in [1,2]:
        target=GRAPHS[selected];folder=out/('execute-'+target);folder.mkdir();input_lists=['__','__','__'];input_lists[selected]=str(lists[selected]);output=folder/'outputs'
        cmd=[str(SDK/'bin/x86_64-linux-clang/qnn-net-run'),'--model',str(SDK/'lib/x86_64-linux-clang/libQnnModelDlc.so'),'--dlc_path',','.join(map(str,dlcs)),'--backend',str(SDK/'lib/x86_64-linux-clang/libQnnCpu.so'),'--input_list',','.join(input_lists),'--output_dir',str(output),'--num_inferences','1','--use_native_input_files','--use_native_output_files','--log_level','info']
        (folder/'command.json').write_text(json.dumps({'argv':cmd,'CPU_client_buffers_only_for_selection_fixture':True,'HTP_memory_mode_not_tested_here':True},indent=2)+'\n');p=subprocess.run(cmd,env=env,capture_output=True,timeout=30,close_fds=True);(folder/'stdout').write_bytes(p.stdout);(folder/'stderr').write_bytes(p.stderr)
        raw=sorted(output.rglob('*.raw')) if output.exists() else [];row={'selected_graph':target,'runner_exit':p.returncode,'raw_files':[str(x.relative_to(output)) for x in raw]};records.append(row);(out/'progress.json').write_text(json.dumps(records,indent=2)+'\n')
        if p.returncode!=0:raise ValueError('authored named selection runner failed; retain receipts')
        if len(raw)!=1 or target not in str(raw[0].relative_to(output)):raise ValueError('unselected graph executed or outputs ambiguous')
        data=np.fromfile(raw[0],dtype='<f4');expected=float(10**selected+1)
        if data.tolist()!=[expected]:raise ValueError('wrong named-graph output')
        import yaml
        meta=yaml.safe_load((output/'execution_metadata.yaml').read_text())
        if meta['inferences_completed']!=1:raise ValueError('exact one execution per invocation required')
        row.update(inferences_completed=meta['inferences_completed'],expected_value=expected,actual_value=float(data[0]),output_sha256=sha(raw[0]),Power_executed=False)
    result={'classification':'actual_host_qnn_net_run_named_selection_passed','graphs_loaded_each':3,'selected_graph_invocations':records,'selection_contract':'three input-list positions; __ skips unselected graph; selected list has one row and num_inferences1; separate invocations','same_runner_version_family':'v2.49.40.260810104044','host_runner_sha256':sha(SDK/'bin/x86_64-linux-clang/qnn-net-run'),'CPU_backend_sha256':sha(SDK/'lib/x86_64-linux-clang/libQnnCpu.so'),'model_DLC_loader_sha256':sha(SDK/'lib/x86_64-linux-clang/libQnnModelDlc.so'),'authored_DLC_bindings':[{'path':str(p),'sha256':sha(p)} for p in dlcs],'full_model_or_phone_executed':False,'actual_HTP_pole_or_memory_policy_tested':False,'Android_binary_source_equivalence_assumed':False,'seconds':time.monotonic()-start};(out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args();out=a.output_dir.resolve()
    if not out.is_relative_to(TRACK/'.local/htp-chain-selection'):p.error('owned fresh selection fixture root required')
    prepare(out)
