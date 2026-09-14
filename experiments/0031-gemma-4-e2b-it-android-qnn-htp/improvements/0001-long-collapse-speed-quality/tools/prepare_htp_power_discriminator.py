#!/usr/bin/env python3
"""HOST-ONLY tiny HTP prep; authored calibration only, no phone/reference/LLM run."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import time

TRACK=Path(__file__).resolve().parents[1]
POLICY=TRACK/'.local/matched-prefill-reference/policy-01/policy.json'
POLICY_SHA='7fffebe9208bc5e2b92d80ed6ed01b7b57263e8f23d188188588682754c18b59'
CONFIG=TRACK/'results/global-value-fp16-context-attempt-01/raw/compiler-config.json'
CONFIG_SHA='36c3f95dae0cfa8f2b9da510b24cfd9a2b4278a777ba602a9ed351bc4d63225e'
GRAPHS=['power_edge','normalization_chain','normalization_exposed']


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()


def encoding(name,grid):
    if grid['axis'] is not None or grid['bitwidths']!=[16]:raise ValueError('only exact actual per-tensor16 grids')
    return {'name':name,'enc_type':'PER_TENSOR','dtype':'INT','bw':16,'is_sym':False,'scale':grid['scale'],'offset':[float(grid['offset'][0])]}


def create(root,kind,policy):
    import numpy as np
    import onnx
    from onnx import helper as h,TensorProto as T,numpy_helper as n
    t=policy['tensors'];root.mkdir()
    grids={'x':t['opt/conv2d_475/simplify//Reshape_out']['grid'],'squared':t['pow_605']['grid'],'mean':t['mean_445']['grid'],'denom':t['add_27410']['grid'],'inverse':t['pow_606']['grid'],'normalized':t['mul_32740']['grid'],'epsilon':t['val_54']['grid'],'exponent':t['val_55']['grid']}
    base_shape=[1,128,1];x_shape=[1,128,1536]
    exponent=n.from_array(np.array([-.5],dtype=np.float32),'exponent')
    if kind=='power_edge':
        nodes=[h.make_node('Pow',['base','exponent'],['inverse'],name='actual_grid_power')];inputs=[h.make_tensor_value_info('base',T.FLOAT,base_shape)];outputs=[h.make_tensor_value_info('inverse',T.FLOAT,base_shape)];initializers=[exponent];active={'base':grids['denom'],'inverse':grids['inverse']};params={'exponent':grids['exponent']}
        raw=np.resize(np.array([0,1,2,65535],dtype=np.uint16),128).reshape(base_shape);description={'row_patterns_codes':[0,1,2,65535],'pattern_repetitions':32,'input':'base','logical_shape':base_shape,'operators_requested':1}
    else:
        nodes=[h.make_node('Mul',['x','x'],['squared'],name='actual_grid_square'),h.make_node('ReduceMean',['squared'],['mean'],name='actual_grid_mean',axes=[2],keepdims=1),h.make_node('Add',['mean','epsilon'],['denom'],name='actual_grid_add_epsilon'),h.make_node('Pow',['denom','exponent'],['inverse'],name='actual_grid_power'),h.make_node('Mul',['x','inverse'],['normalized'],name='actual_grid_normalize')]
        inputs=[h.make_tensor_value_info('x',T.FLOAT,x_shape)];output_names=['normalized'] if kind=='normalization_chain' else ['normalized','squared','mean','denom','inverse'];outputs=[h.make_tensor_value_info(name,T.FLOAT,x_shape if name in ['normalized','squared'] else base_shape) for name in output_names];initializers=[exponent,n.from_array(np.array([1e-6],dtype=np.float32),'epsilon')];active={name:grids[name] for name in ['x','squared','mean','denom','inverse','normalized']};params={name:grids[name] for name in ['epsilon','exponent']}
        codes=np.resize(np.array([58263,58264,58519,59287],dtype=np.uint16),128);raw=np.broadcast_to(codes.reshape(1,128,1),x_shape).copy();description={'row_patterns_codes':[58263,58264,58519,59287],'pattern_repetitions':32,'input':'x','logical_shape':x_shape,'operators_requested':5,'intermediates_exposed':kind=='normalization_exposed','changed_fusion_opportunity':kind=='normalization_exposed','learned_gamma_or_Gemma_weights_included':False,'scope':'Exact-shape/grid square/mean/epsilon/power/multiply fragment only, not whole layer/model.'}
    model=h.make_model(h.make_graph(nodes,kind,inputs,outputs,initializers),opset_imports=[h.make_opsetid('',13)],producer_name='authored-HTP-power-edge-fixture');model.ir_version=8;onnx.checker.check_model(model);onnx.save(model,root/(kind+'.onnx'))
    enc={'version':'1.0.0','activation_encodings':[encoding(name,g) for name,g in active.items()],'param_encodings':[encoding(name,g) for name,g in params.items()]};(root/'fixture.encodings').write_text(json.dumps(enc,indent=2)+'\n');raw.astype('<u2').tofile(root/'input.uint16le')
    description.update(graph=kind,active_grids=active,parameter_grids=params,input_bytes=raw.nbytes,input_sha256=sha(root/'input.uint16le'),expected_output_shapes={o.name:[d.dim_value for d in o.type.tensor_type.shape.dim] for o in outputs},no_model_inputs_or_checkpoint_weights=True)
    # One finite AUTHORED calibration sample disables qairt.convert's forced
    # float_fallback-without-dataset path. Every actual grid is still overridden/verified.
    input_grid=active[description['input']];calibration_code=43 if kind=='power_edge' else 58583
    calibration_value=np.float32((calibration_code+input_grid['offset'][0])*input_grid['scale'][0]);calibration=root/'finite-calibration.float32'
    np.full(description['logical_shape'],calibration_value,dtype='<f4').tofile(calibration)
    (root/'calibration.txt').write_text(description['input']+':='+str(calibration)+'\n')
    description['synthetic_calibration']={'samples':1,'code':calibration_code,'float_value':float(calibration_value),'bytes':calibration.stat().st_size,'sha256':sha(calibration),'LLM_or_captured_model_inputs':False,'all_grids_overridden':True}
    (root/'authored.json').write_text(json.dumps(description,indent=2)+'\n');return description


def expected_cases(description):
    """Freeze contrasting formulas; never assign a guessed integer code to a pole."""
    import numpy as np
    grids=description['active_grids'];params=description['parameter_grids'];rows=[]
    def dequant(code,g):return np.float32((np.float32(code)+np.float32(g['offset'][0]))*np.float32(g['scale'][0]))
    def quant(value,g):
        if not np.isfinite(value):return None
        return int(np.clip(np.rint(np.float32(value)/np.float32(g['scale'][0])-np.float32(g['offset'][0])),0,65535))
    for code in description['row_patterns_codes']:
        row={'input_code':code}
        if description['graph']=='power_edge':
            value=dequant(code,grids['base']);row['decoded_base']=float(value)
            if value==0:row.update(literal_power='+Inf pole',expected_native_code=None)
            else:
                inverse=np.float32(np.power(value,np.float32(-.5)));row.update(literal_power=float(inverse),finite_nearest_even_code=quant(inverse,grids['inverse']))
        else:
            x=dequant(code,grids['x']);epsilon=dequant(655,params['epsilon']);square=quant(np.float32(x*x),grids['squared']);mean=quant(dequant(square,grids['squared']),grids['mean']);denom=quant(np.float32(dequant(mean,grids['mean'])+epsilon),grids['denom']);d=dequant(denom,grids['denom'])
            row.update(decoded_x=float(x),literal_squared_code=square,literal_mean_code=mean,literal_denom_code=denom)
            if d==0:row.update(literal_inverse='+Inf pole',literal_inverse_code=None,literal_normalized_code=None)
            else:
                inverse=quant(np.float32(np.power(d,np.float32(-.5))),grids['inverse']);row.update(literal_inverse_code=inverse,literal_normalized_code=quant(np.float32(x*dequant(inverse,grids['inverse'])),grids['normalized']))
            fused=np.float32(x/np.sqrt(np.float32(x*x+epsilon)));row['contrasting_fused_RMS_formula_code']=quant(fused,grids['normalized'])
        rows.append(row)
    return {'graph':description['graph'],'rows':rows,'finite_reference_rounding':'Float32 arithmetic and nearest-even grid rounding; comparison descriptor, not HTP kernel claim','pole_integer_output_policy':'UNSPECIFIED; preserve observed native codes','fused_formula_is_hypothesis_not_backend_proof':True,'exposed_intermediates_change_fusion_opportunity':description.get('intermediates_exposed',False)}


def inspect(dlc,description):
    import numpy as np
    from qti.aisw.dlc_utils import modeltools
    from qti.aisw.dlc_utils.snpe_dlc_utils import is_scale_offset_encoding
    reader=modeltools.IrDlcReader();reader.open(str(dlc));names=sorted(reader.get_ir_graph_names())
    if len(names)!=1:raise ValueError('one graph per tiny DLC expected')
    graph=reader.get_ir_graph(names[0]);values={}
    for op in graph.get_ops():
        for t in op.inputs()+op.outputs():
            if t.name() in values:continue
            e=t.get_encoding();item={'datatype':t.data_type_string(),'dimensions':t.dims(),'tensor_type':t.tensor_type(),'encoding_kind':str(e.type)}
            if is_scale_offset_encoding(e.type):item['grid']={'bitwidths':[int(e.encInfo.bw)],'scale':[float(e.encInfo.scale)],'offset':[int(e.encInfo.offset)],'axis':None}
            if t.is_static_tensor():
                a=graph.get_static_tensor(t.name()).get_data();item['static']={'dtype':str(a.dtype),'shape':list(a.shape),'bytes':int(a.nbytes),'sha256':hashlib.sha256(a.tobytes()).hexdigest()}
                if a.size<=4:item['static']['values']=a.tolist()
            values[t.name()]=item
    inputs=[t.name() for t in graph.get_input_tensors_to_graph()];outputs=[name for name,v in values.items() if v['tensor_type']=='APP_READ']
    if inputs!=[description['input']]:raise ValueError('tiny input name/order changed')
    if set(outputs)!=set(description['expected_output_shapes']):raise ValueError('requested output instrumentation changed')
    for name in inputs+outputs:
        wanted=description['active_grids'][name];v=values[name]
        shape=description['logical_shape'] if name in inputs else description['expected_output_shapes'][name]
        if v['datatype']!='uFxp_16' or v['dimensions']!=shape or v.get('grid',{}).get('bitwidths')!=[16] or v['grid']['offset']!=wanted['offset'] or np.float32(v['grid']['scale'][0])!=np.float32(wanted['scale'][0]):raise ValueError('actual graph IO grid/dtype/shape differs '+name)
    for name,wanted in {**description['active_grids'],**description['parameter_grids']}.items():
        v=values.get(name,{})
        if v.get('datatype')!='uFxp_16' or v.get('grid',{}).get('bitwidths')!=[16] or v['grid']['offset']!=wanted['offset'] or np.float32(v['grid']['scale'][0])!=np.float32(wanted['scale'][0]):raise ValueError('actual internal/scalar grid differs or was optimized away '+name)
    if 'epsilon' in description['parameter_grids'] and values['epsilon']['static'].get('values')!=[655]:raise ValueError('actual epsilon code not retained')
    ops=[]
    for o in graph.get_ops():
        attrs={}
        if o.type=='Eltwise_Binary':attrs['operation']=int(o.attrs.get_uint32('operation'))
        if o.type=='Reduce':attrs={'axes':o.attrs.get_static_tensor_data('axes').tolist(),'keep_dims':bool(o.attrs.get_bool('keep_dims')),'reduce_type':o.attrs.get_string('reduce_type')}
        ops.append({'name':o.name,'type':o.type,'inputs':[t.name() for t in o.inputs()],'outputs':[t.name() for t in o.outputs()],'attrs':attrs})
    if description['graph']=='power_edge':
        if len(ops)!=1 or ops[0]['type']!='Eltwise_Binary' or ops[0]['attrs']!={'operation':16}:raise ValueError('isolated actual Power not retained')
        v=values['exponent'];g=description['parameter_grids']['exponent']
        if v['datatype']!='uFxp_16' or v['grid']['offset']!=g['offset'] or np.float32(v['grid']['scale'][0])!=np.float32(g['scale'][0]) or v['static'].get('values')!=[0]:raise ValueError('actual exponent grid/raw code not retained')
    else:
        expected=[('Eltwise_Binary',{'operation':13}),('Reduce',{'axes':[2],'keep_dims':True,'reduce_type':'ReduceMean'}),('Eltwise_Binary',{'operation':0}),('Eltwise_Binary',{'operation':16}),('Eltwise_Binary',{'operation':13})]
        if [(o['type'],o['attrs']) for o in ops]!=expected:raise ValueError('same-grid normalization fragment operators/attrs changed')
    return {'graph_name':names[0],'inputs':inputs,'outputs':outputs,'tensors':values,'operators':ops,'converter_RmsNorm_fusion_present':any(o['type']=='RmsNorm' for o in ops),'actual_IO_contract_passed':True,'actual_operator_attributes_passed':True,'physical_execution_proven':False}


def verify_context_contract(context,graphs):
    info=context['info']
    if info['backendId']!=6 or info['socModel']!=43 or info['numGraphs']!=3:raise ValueError('three-graph HTP/SM8550 context required')
    expected={g['graph_name']:g for g in graphs}
    if [g['info']['graphName'] for g in info['graphs']]!=GRAPHS:raise ValueError('frozen graph order changed')
    for graph in info['graphs']:
        actual=graph['info'];source=expected[actual['graphName']]
        for side,role in [('graphInputs','inputs'),('graphOutputs','outputs')]:
            tensors={t['info']['name']:t['info'] for t in actual[side]}
            if set(tensors)!=set(source[role]):raise ValueError('compiled graph IO names changed')
            for name,v in tensors.items():
                old=source['tensors'][name];q=v['quantizeParams']
                if v['dataFormat']!='QNN_TENSOR_DATA_FORMAT_FLAT_BUFFER' or v['dataType']!='QNN_DATATYPE_UFIXED_POINT_16' or v['dimensions']!=old['dimensions'] or q['quantizationEncoding']!='QNN_QUANTIZATION_ENCODING_SCALE_OFFSET' or q['scaleOffset']!={'scale':old['grid']['scale'][0],'offset':old['grid']['offset'][0]}:raise ValueError('compiled native IO contract differs '+name)
    return {'backend_id':6,'soc_model':43,'graphs':GRAPHS,'native_IO_grids_shapes_dtypes_preserved':True,'physical_execution_or_HTP_fusion_proven':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output-dir',type=Path,required=True);a=parser.parse_args();out=a.output_dir.resolve()
    if not out.is_relative_to(TRACK/'.local/htp-power-discriminator'):parser.error('owned fresh host-only preparation root required')
    if sha(POLICY)!=POLICY_SHA or sha(CONFIG)!=CONFIG_SHA:raise ValueError('actual grid/compiler recipe source changed')
    if shutil.disk_usage(TRACK).free<64*1024**3:raise ValueError('existing disk headroom floor')
    out.mkdir(parents=True,exist_ok=False,mode=0o700);os.umask(0o077);started=time.monotonic();policy=json.loads(POLICY.read_text());result={'classification':'host_only_tiny_HTP_preparation_started','graphs':[],'full_model_or_phone_inference':False,'authored_tiny_calibration_may_execute':True,'policy_sha256':POLICY_SHA,'compiler_recipe_sha256':CONFIG_SHA,'max_authored_graphs':3,'full_reference_or_LLM_loaded':False}
    def save():result['seconds']=time.monotonic()-started;(out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    save()
    try:
        import qairt
        from qairt.api.converter.converter_config import CalibrationConfig
        models=[]
        for name in GRAPHS:
            folder=out/name;desc=create(folder,name,policy);result['graphs'].append({'authored':desc});save()
            calibration=CalibrationConfig(dataset=str(folder/'calibration.txt'),num_of_samples=1,act_precision=16,weights_precision=16,bias_precision=32,per_channel_quantization=False)
            result['graphs'][-1]['calibration_config']=calibration.model_dump(mode='json');save()
            converted=qairt.convert(folder/(name+'.onnx'),encodings=folder/'fixture.encodings',calibration_config=calibration,backend='HTP',float_precision=32,float_bias_precision=32,input_tensor_config=[{'name':desc['input'],'layout':'NONTRIVIAL'}],output_tensor_config=[],use_quantize_v2=False)
            dlc=folder/(name+'.dlc');shutil.copyfile(converted.module.path,dlc);result['graphs'][-1]['dlc']={'path':str(dlc),'bytes':dlc.stat().st_size,'sha256':sha(dlc)};save()
            gate=inspect(dlc,desc);(folder/'inspection.json').write_text(json.dumps(gate,indent=2)+'\n');result['graphs'][-1]['inspection']=gate;models.append(qairt.Model.load(dlc));save()
        if len({m.name for m in models})!=3:raise ValueError('unique actual graph names required')
        config=json.loads(CONFIG.read_text());template=config['graph_custom_configs'][0]
        removed=template.pop('use_high_precision_fp16_sigmoid',None)
        result['inactive_unsupported_graph_config_key_removed']={'use_high_precision_fp16_sigmoid':removed,'Sigmoid_ops_in_fixture':0}
        config['graph_custom_configs']=[{**copy.deepcopy(template),'name':m.name} for m in models];result['compiler_config']=config;result['float_fallback_requested']=False;result['synthetic_calibration_may_execute_tiny_host_graph']=True;save()
        compiled=qairt.compile(models,config=qairt.CompileConfig(**config));context=out/'power-edge-context.bin';shutil.copyfile(compiled.module.path,context);result['context']={'path':str(context),'bytes':context.stat().st_size,'sha256':sha(context)};result['classification']='tiny_HTP_context_compiled_pending_runtime_bundle';save();return 0
    except Exception as e:
        result['classification']='host_only_tiny_HTP_preparation_error';result['error']={'type':type(e).__name__,'message':str(e)};save();raise


if __name__=='__main__':raise SystemExit(main())
