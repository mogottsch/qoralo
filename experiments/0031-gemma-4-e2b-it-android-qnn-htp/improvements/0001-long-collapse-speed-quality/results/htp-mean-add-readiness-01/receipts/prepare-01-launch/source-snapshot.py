#!/usr/bin/env python3
"""HOST-ONLY two single-output same-grid controls; no Power, LLM or phone execution."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

TRACK=Path(__file__).resolve().parents[1]
SDK=Path('/home/moritz/opt/qairt/2.49.40.260810')
POLICY=TRACK/'.local/matched-prefill-reference/policy-01/policy.json'
POLICY_SHA='7fffebe9208bc5e2b92d80ed6ed01b7b57263e8f23d188188588682754c18b59'
NAMES=['mean_edge','epsilon_add']


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def create(folder,name,policy):
    import numpy as np
    import onnx
    from onnx import helper as h,TensorProto as T,numpy_helper as n
    from prepare_htp_power_discriminator import encoding
    t=policy['tensors'];folder.mkdir();output_grid=t['mean_445']['grid'];output_shape=[1,128,1]
    if name=='mean_edge':
        shape=[1,128,1536];input_grid=t['pow_605']['grid'];raw=np.zeros(shape,dtype=np.uint16)
        for row in range(128):
            if row%4==1:raw[0,row,0]=1
            elif row%4==2:raw[0,row,:]=1
            elif row%4==3:raw[0,row,:]=20
        nodes=[h.make_node('ReduceMean',['x'],['y'],name='isolated_actual_grid_mean',axes=[2],keepdims=1)];initializers=[];params=[];calibration=np.full(shape,input_grid['scale'][0],dtype='<f4');patterns=['all_zero','one_code1_other1535zero','all_code1','all_code20'];expected=[0,0,22,434];attrs={'axes':[2],'keep_dims':True,'reduce_type':'ReduceMean'}
    elif name=='epsilon_add':
        shape=[1,128,1];input_grid=output_grid;raw=np.resize(np.array([0,1,22,434],dtype=np.uint16),128).reshape(shape)
        nodes=[h.make_node('Add',['x','epsilon'],['y'],name='isolated_actual_grid_epsilon_add')];initializers=[n.from_array(np.array([1e-6],dtype=np.float32),'epsilon')];params=[encoding('epsilon',t['val_54']['grid'])];calibration=np.full(shape,22*input_grid['scale'][0],dtype='<f4');patterns=['code0','code1','code22','code434'];expected=[0,1,22,434];attrs={'operation':0}
    else:raise ValueError('at most the two reviewed controls')
    model=h.make_model(h.make_graph(nodes,name,[h.make_tensor_value_info('x',T.FLOAT,shape)],[h.make_tensor_value_info('y',T.FLOAT,output_shape)],initializers),opset_imports=[h.make_opsetid('',13)],producer_name='authored-same-grid-mean-add-control');model.ir_version=8;onnx.checker.check_model(model);onnx.save(model,folder/(name+'.onnx'))
    (folder/'encodings.json').write_text(json.dumps({'version':'1.0.0','activation_encodings':[encoding('x',input_grid),encoding('y',output_grid)],'param_encodings':params},indent=2)+'\n');raw.astype('<u2').tofile(folder/'input.uint16le');calibration.tofile(folder/'finite-calibration.float32');(folder/'calibration.txt').write_text('x:='+str(folder/'finite-calibration.float32')+'\n')
    result={'graph':name,'input_name':'x','input_shape':shape,'input_grid':input_grid,'output_name':'y','output_shape':output_shape,'output_grid':output_grid,'expected_operator_type':'Reduce' if name=='mean_edge' else 'Eltwise_Binary','expected_attributes':attrs,'row_patterns':patterns,'repeats_each':32,'literal_float32_nearest_even_expected_codes':expected,'expected_codes_are_comparison_not_HTP_policy_assertion':True,'input_bytes':raw.nbytes,'input_sha256':sha(folder/'input.uint16le'),'single_output_eliminates_same_graph_multi_output_file_alias_question':True,'inter_operator_chain_fusion_not_present_in_authored_graph':True,'no_Power_no_learned_weights_no_model_inputs':True,'synthetic_calibration_samples':1,'all_encodings_overridden':True};(folder/'authored.json').write_text(json.dumps(result,indent=2)+'\n');return result


def inspect(dlc,desc):
    import numpy as np
    from qti.aisw.dlc_utils import modeltools
    from qti.aisw.dlc_utils.snpe_dlc_utils import is_scale_offset_encoding
    reader=modeltools.IrDlcReader();reader.open(str(dlc));names=sorted(reader.get_ir_graph_names())
    if names!=[desc['graph']]:raise ValueError('exact unique graph name required')
    graph=reader.get_ir_graph(names[0]);ops=list(graph.get_ops());tensors={}
    if len(ops)!=1 or ops[0].type!=desc['expected_operator_type']:raise ValueError('single requested operation not retained')
    op=ops[0];attrs={'operation':int(op.attrs.get_uint32('operation'))} if op.type=='Eltwise_Binary' else {'axes':op.attrs.get_static_tensor_data('axes').tolist(),'keep_dims':bool(op.attrs.get_bool('keep_dims')),'reduce_type':op.attrs.get_string('reduce_type')}
    if attrs!=desc['expected_attributes']:raise ValueError('actual operator attrs changed')
    for t in op.inputs()+op.outputs():
        e=t.get_encoding()
        if t.data_type_string()!='uFxp_16' or not is_scale_offset_encoding(e.type):raise ValueError('only exact UF16 scale-offset tensors allowed')
        entry={'datatype':t.data_type_string(),'dimensions':t.dims(),'tensor_type':t.tensor_type(),'grid':{'scale':float(e.encInfo.scale),'offset':int(e.encInfo.offset),'bitwidth':int(e.encInfo.bw)}}
        if t.is_static_tensor():entry['raw_scalar']=graph.get_static_tensor(t.name()).get_data().tolist()
        tensors[t.name()]=entry
    for name,shape,grid in [('x',desc['input_shape'],desc['input_grid']),('y',desc['output_shape'],desc['output_grid'])]:
        v=tensors[name]
        if v['dimensions']!=shape or v['grid']['offset']!=grid['offset'][0] or v['grid']['bitwidth']!=16 or np.float32(v['grid']['scale'])!=np.float32(grid['scale'][0]):raise ValueError('actual IO contract changed')
    if desc['graph']=='epsilon_add':
        p=json.loads(POLICY.read_text());g=p['tensors']['val_54']['grid'];v=tensors['epsilon']
        if v['raw_scalar']!=[655] or v['grid']['offset']!=0 or np.float32(v['grid']['scale'])!=np.float32(g['scale'][0]):raise ValueError('exact epsilon grid/code changed')
    return {'name':names[0],'operator_name':op.name,'operator_type':op.type,'attrs':attrs,'tensors':tensors,'passed':True,'HTP_execution_or_rounding_policy_proven':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output-dir',type=Path,required=True);a=parser.parse_args();out=a.output_dir.resolve()
    if not out.is_relative_to(TRACK/'.local/htp-mean-add-controls'):parser.error('owned fresh host-only root required')
    if sha(POLICY)!=POLICY_SHA or shutil.disk_usage(TRACK).free<64*1024**3:raise ValueError('frozen policy/disk headroom check')
    out.mkdir(parents=True,exist_ok=False,mode=0o700);os.umask(0o077);start=time.monotonic();result={'classification':'started_two_single_output_HTP_controls','full_model_reference_or_phone_execution':False,'authored_tiny_calibration_may_execute':True,'graphs':[],'Power_graph_included':False}
    def retain():result['seconds']=time.monotonic()-start;(out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    retain()
    try:
        import qairt
        from qairt.api.converter.converter_config import CalibrationConfig
        policy=json.loads(POLICY.read_text());models=[]
        for name in NAMES:
            folder=out/name;desc=create(folder,name,policy);row={'authored':desc};result['graphs'].append(row);retain();calibration=CalibrationConfig(dataset=str(folder/'calibration.txt'),num_of_samples=1,act_precision=16,weights_precision=16,bias_precision=32,per_channel_quantization=False)
            converted=qairt.convert(folder/(name+'.onnx'),encodings=folder/'encodings.json',calibration_config=calibration,backend='HTP',float_precision=32,float_bias_precision=32,input_tensor_config=[{'name':'x','layout':'NONTRIVIAL'}],use_quantize_v2=False)
            dlc=folder/(name+'.dlc');shutil.copyfile(converted.module.path,dlc);row['dlc']={'path':str(dlc),'bytes':dlc.stat().st_size,'sha256':sha(dlc)};retain();row['inspection']=inspect(dlc,desc);models.append(qairt.Model.load(dlc));retain()
        config_path=TRACK/'results/global-value-fp16-context-attempt-01/raw/compiler-config.json'
        if sha(config_path)!='36c3f95dae0cfa8f2b9da510b24cfd9a2b4278a777ba602a9ed351bc4d63225e':raise ValueError('frozen compiler recipe changed')
        config=json.loads(config_path.read_text());template=copy.deepcopy(config['graph_custom_configs'][0]);template.pop('use_high_precision_fp16_sigmoid',None);config['graph_custom_configs']=[{**copy.deepcopy(template),'name':m.name} for m in models];result['compiler_config']=config;retain();compiled=qairt.compile(models,config=qairt.CompileConfig(**config));context=out/'mean-add-context.bin';shutil.copyfile(compiled.module.path,context);result['context']={'path':str(context),'bytes':context.stat().st_size,'sha256':sha(context)};retain()
        command=[str(SDK/'bin/x86_64-linux-clang/qnn-context-binary-utility'),'--context_binary',str(context),'--json_file',str(out/'context-info.json')];p=subprocess.run(command,capture_output=True,timeout=30,close_fds=True);(out/'context-info-command.json').write_text(json.dumps({'argv':command,'exit':p.returncode})+'\n');(out/'context-info.stdout').write_bytes(p.stdout);(out/'context-info.stderr').write_bytes(p.stderr)
        if p.returncode:raise ValueError('context metadata utility failed')
        info=json.loads((out/'context-info.json').read_text())['info']
        if info['backendId']!=6 or info['socModel']!=43 or [g['info']['graphName'] for g in info['graphs']]!=NAMES:raise ValueError('two-graph HTP SoC43 context mismatch')
        for graph,row in zip(info['graphs'],result['graphs']):
            for side,name in [('graphInputs','x'),('graphOutputs','y')]:
                ts=graph['info'][side]
                if len(ts)!=1:raise ValueError('single input/output contract violated')
                v=ts[0]['info'];old=row['inspection']['tensors'][name];grid=v['quantizeParams']['scaleOffset']
                if v['name']!=name or v['dataType']!='QNN_DATATYPE_UFIXED_POINT_16' or v['dataFormat']!='QNN_TENSOR_DATA_FORMAT_FLAT_BUFFER' or v['dimensions']!=old['dimensions'] or grid!={'scale':old['grid']['scale'],'offset':old['grid']['offset']}:raise ValueError('compiled IO identity differs')
        result['classification']='two_same_grid_single_output_HTP_controls_compiled';result['context_IO_verified']=True;result['phone_executed']=False;retain();return 0
    except Exception as error:result['classification']='host_only_control_preparation_error';result['error']={'type':type(error).__name__,'message':str(error)};retain();raise


if __name__=='__main__':raise SystemExit(main())
