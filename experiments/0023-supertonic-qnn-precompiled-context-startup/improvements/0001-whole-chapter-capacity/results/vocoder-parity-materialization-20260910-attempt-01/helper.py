#!/usr/bin/env python3
"""One gated structural vocoder derivative: exactly two batch1 parity replacements.

No ORT/QNN/Torch import or model forward. Embedded initializer protobuf bytes are
parsed/copied, never evaluated; only bounded integer Pad controls are decoded.
"""
import argparse
import collections
import copy
import hashlib
import json
from pathlib import Path
import resource
import sys
import time

SOURCE_SHA='539f8ef7850292b3b5add1b9b29012e6bff86c13caebad06ef802cec261df792'
TARGETS=[f'/decoder/convnext.{i}/dwconv/net/Conv' for i in (1,4)]
PREFIX='__whole_chapter_vocoder_parity_'
CONTROL_VALUES={'start_even':[0],'start_odd':[1],'end':[12300],'axis':[2],'step':[2],'unsqueeze_axes':[3],'output_shape':[1,512,12288]}
EXPECTED_ATTRS={'dilations':[2],'group':512,'kernel_shape':[7],'pads':[0,0],'strides':[1]}


def digest(data):return hashlib.sha256(data).hexdigest()


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def write(path,value):
    with Path(path).open('x') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')


def attributes(node):
    import onnx
    return {a.name:onnx.helper.get_attribute_value(a) for a in node.attribute}


def controls():
    import onnx
    return [onnx.helper.make_tensor(PREFIX+name,onnx.TensorProto.INT64,[len(values)],values) for name,values in CONTROL_VALUES.items()]


def pad_value(model,name):
    """Evaluate only the tiny non-learned integer Pad-builder DAG, max32 values."""
    import numpy as np
    import onnx
    by_output={out:n for n in model.graph.node for out in n.output};cache={};active=set()
    def integer_tensor(value):
        if value.data_type not in (onnx.TensorProto.INT64,onnx.TensorProto.INT32) or value.external_data or value.data_location==onnx.TensorProto.EXTERNAL or np.prod(value.dims)>32:
            raise ValueError('only bounded embedded integer control tensors')
        return onnx.numpy_helper.to_array(value).copy()
    def evaluate(key):
        if key in cache:return cache[key]
        if key in active or key not in by_output:raise ValueError('Pad control must be an acyclic Constant-only DAG')
        active.add(key);node=by_output[key];a=attributes(node)
        if node.op_type=='Constant':value=integer_tensor(a['value'])
        else:
            args=[evaluate(v) for v in node.input]
            if node.op_type=='ConstantOfShape':
                fill=integer_tensor(a['value']);shape=tuple(int(v) for v in args[0]);
                if any(v<0 for v in shape) or np.prod(shape)>32:raise ValueError('oversized control shape')
                value=np.full(shape,fill.item(),dtype=fill.dtype)
            elif node.op_type=='Concat':value=np.concatenate(args,axis=int(a['axis']))
            elif node.op_type=='Reshape':value=args[0].reshape(tuple(int(v) for v in args[1]))
            elif node.op_type=='Transpose':value=args[0].transpose(a['perm'])
            elif node.op_type=='Cast':
                if a['to'] not in (onnx.TensorProto.INT64,onnx.TensorProto.INT32):raise ValueError('noninteger Pad control cast')
                value=args[0].astype(np.int64 if a['to']==onnx.TensorProto.INT64 else np.int32)
            elif node.op_type=='Slice':
                slices=[slice(None)]*args[0].ndim
                for start,end,axis,step in zip(args[1],args[2],args[3],args[4]):slices[int(axis)]=slice(int(start),int(end),int(step))
                value=args[0][tuple(slices)]
            else:raise ValueError('unsupported Pad control op: '+node.op_type)
        if value.size>32 or value.dtype.kind not in 'iu':raise ValueError('invalid Pad control result')
        cache[key]=value;active.remove(key);return value
    return evaluate(name).tolist()


def validate_source(model):
    import onnx
    if [(o.domain,o.version) for o in model.opset_import]!=[('',19)]:raise ValueError('expected standard opset19')
    if model.functions or model.graph.sparse_initializer:raise ValueError('unexpected model functions/sparse data')
    initializers={v.name:v for v in model.graph.initializer}
    if len(initializers)!=len(model.graph.initializer):raise ValueError('duplicate initializer names')
    for v in initializers.values():
        if v.external_data or v.data_location==onnx.TensorProto.EXTERNAL:raise ValueError('external data forbidden')
    def abi(values):return [(v.name,v.type.tensor_type.elem_type,[d.dim_value if d.HasField('dim_value') else d.dim_param for d in v.type.tensor_type.shape.dim]) for v in values]
    if abi(model.graph.input)!=[('latent',1,[1,144,2048])] or abi(model.graph.output)!=[('wav_tts',1,[1,6291456])]:raise ValueError('public ABI differs')
    names=[n.name for n in model.graph.node]
    if len(names)!=len(set(names)):raise ValueError('duplicate node names')
    all_names=names+[v.name for v in model.graph.initializer]+[o for n in model.graph.node for o in n.output]
    if any(PREFIX in v or '/parity_' in v for v in all_names):raise ValueError('parity namespace collision/already transformed')
    nodes={n.name:n for n in model.graph.node};report=[]
    for i,target in zip((1,4),TARGETS):
        if target not in nodes:raise ValueError('target missing')
        n=nodes[target];base=f'/decoder/convnext.{i}/dwconv';weight=f'tts.ae.decoder.convnext.{i}.dwconv.net.weight';bias=f'tts.ae.decoder.convnext.{i}.dwconv.net.bias'
        if n.op_type!='Conv' or n.domain or attributes(n)!=EXPECTED_ATTRS or list(n.input)!=[base+'/Pad_output_0',weight,bias] or list(n.output)!=[target+'_output_0']:raise ValueError('target Conv differs')
        for name,shape in [(weight,[512,1,7]),(bias,[512])]:
            if name not in initializers or initializers[name].data_type!=1 or list(initializers[name].dims)!=shape:raise ValueError('weight/bias metadata differs')
        pad=nodes.get(base+'/Pad')
        if pad is None or pad.op_type!='Pad' or pad.domain or attributes(pad)!={'mode':b'edge'} or len(pad.input)!=2 or list(pad.output)!=[n.input[0]]:raise ValueError('existing edge Pad differs')
        values=pad_value(model,pad.input[1])
        if values!=[0,0,12,0,0,0]:raise ValueError('existing causal Pad vector differs')
        report.append({'node':target,'pad':pad.name,'pad_values':values,'weight':weight,'bias':bias})
    return report


def replacement(node):
    import onnx
    h=onnx.helper;nodes=[];infos=[];outputs=[]
    for parity,start in [('even','start_even'),('odd','start_odd')]:
        sliced=node.name+'/parity_'+parity+'_input';convout=node.name+'/parity_'+parity+'_conv';expanded=node.name+'/parity_'+parity+'_expanded'
        nodes.append(h.make_node('Slice',[node.input[0],PREFIX+start,PREFIX+'end',PREFIX+'axis',PREFIX+'step'],[sliced],name=node.name+'/parity_'+parity+'_slice'))
        conv=copy.deepcopy(node);conv.name=node.name+'/parity_'+parity+'_conv';conv.input[0]=sliced;conv.output[0]=convout
        next(a for a in conv.attribute if a.name=='dilations').ints[0]=1;nodes.append(conv)
        nodes.append(h.make_node('Unsqueeze',[convout,PREFIX+'unsqueeze_axes'],[expanded],name=node.name+'/parity_'+parity+'_unsqueeze'))
        for name,shape in [(sliced,[1,512,6150]),(convout,[1,512,6144]),(expanded,[1,512,6144,1])]:infos.append(h.make_tensor_value_info(name,1,shape))
        outputs.append(expanded)
    interleaved=node.name+'/parity_interleaved'
    nodes.append(h.make_node('Concat',outputs,[interleaved],name=node.name+'/parity_concat',axis=3))
    nodes.append(h.make_node('Reshape',[interleaved,PREFIX+'output_shape'],list(node.output),name=node.name+'/parity_restore'))
    infos.append(h.make_tensor_value_info(interleaved,1,[1,512,6144,2]))
    return nodes,infos


def isolated_shape_proof(node,new_nodes):
    """Strict shape inference on plumbing with independently bound padded ABI; no W values."""
    import onnx
    h=onnx.helper
    inputs=[h.make_tensor_value_info(node.input[0],1,[1,512,12300]),h.make_tensor_value_info(node.input[1],1,[512,1,7]),h.make_tensor_value_info(node.input[2],1,[512])]
    output=h.make_tensor_value_info(node.output[0],1,[1,512,12288])
    probe=h.make_model(h.make_graph(new_nodes,'parity_shape_only',inputs,[output],controls()),opset_imports=[h.make_opsetid('',19)])
    inferred=onnx.shape_inference.infer_shapes(probe,check_type=True,strict_mode=True,data_prop=False);onnx.checker.check_model(inferred,full_check=True)
    values={v.name:v for v in list(inferred.graph.value_info)+list(inferred.graph.output)}
    _,expected=replacement(node)
    for v in expected+[output]:
        actual=values[v.name].type.tensor_type
        if actual.elem_type!=1 or [d.dim_value for d in actual.shape.dim]!=[d.dim_value for d in v.type.tensor_type.shape.dim]:raise ValueError('plumbing shape proof mismatch')
    return {'node':node.name,'input_shape':[1,512,12300],'output_shape':[1,512,12288],'new_tensor_shapes_independently_inferred':True,'weights_evaluated':False}


def transform(model):
    import onnx
    pads=validate_source(model);derived=copy.deepcopy(model);nodes=[];infos=[];proofs=[]
    for n in model.graph.node:
        if n.name in TARGETS:
            new,new_infos=replacement(n);proofs.append(isolated_shape_proof(n,new));nodes.extend(new);infos.extend(new_infos)
        else:nodes.append(copy.deepcopy(n))
    del derived.graph.node[:];derived.graph.node.extend(nodes);derived.graph.initializer.extend(controls());derived.graph.value_info.extend(infos)
    onnx.checker.check_model(derived,full_check=True)
    return derived,{'pads':pads,'isolated_shape_proofs':proofs,'full_model_checker':True,'full_model_inference_claim':'Checker validation only; original stored symbolic intermediate annotations are preserved, not replaced with invented concrete shapes.'}


def structural_delta(source,derived):
    validate_source(source)
    expected_nodes=[];expected_infos=[]
    for n in source.graph.node:
        if n.name in TARGETS:
            nodes,infos=replacement(n);expected_nodes.extend(nodes);expected_infos.extend(infos)
        else:expected_nodes.append(n)
    def blobs(values):return [v.SerializeToString() for v in values]
    if blobs(derived.graph.node)!=blobs(expected_nodes):raise ValueError('unapproved node bytes/order mutation')
    if blobs(derived.graph.initializer)!=blobs(source.graph.initializer)+blobs(controls()):raise ValueError('original weight/control initializer mutation')
    if blobs(derived.graph.value_info)!=blobs(source.graph.value_info)+blobs(expected_infos):raise ValueError('unexpected value_info mutation')
    restored=copy.deepcopy(derived);restored.graph.CopyFrom(source.graph)
    if restored.SerializeToString()!=source.SerializeToString():raise ValueError('model-level metadata mutation')
    graph=copy.deepcopy(derived.graph)
    for field in ['node','initializer','value_info']:
        del getattr(graph,field)[:];getattr(graph,field).extend(getattr(source.graph,field))
    if graph.SerializeToString()!=source.graph.SerializeToString():raise ValueError('public IO or other graph metadata mutation')
    return {'status':'exact_allowed_delta','source_nodes':len(source.graph.node),'derivative_nodes':len(derived.graph.node),'replaced_source_nodes':TARGETS,
            'source_initializers':len(source.graph.initializer),'derivative_initializers':len(derived.graph.initializer),
            'all_original_initializer_bytes_and_order_unchanged':True,'all_non_target_node_bytes_and_order_unchanged':True,'original_value_info_and_public_IO_bytes_unchanged':True,
            'original_initializers':[{'name':v.name,'sha256':digest(v.SerializeToString())} for v in source.graph.initializer],
            'added_integer_control_initializers':[{'name':v.name,'sha256':digest(v.SerializeToString()),'values':list(v.int64_data)} for v in controls()],
            'original_nodes':[{'name':v.name,'op':v.op_type,'sha256':digest(v.SerializeToString()),'replaced':v.name in TARGETS} for v in source.graph.node],
            'derived_nodes':[{'name':v.name,'op':v.op_type,'sha256':digest(v.SerializeToString())} for v in derived.graph.node],
            'operator_counts_before':dict(collections.Counter(v.op_type for v in source.graph.node)),
            'operator_counts_after':dict(collections.Counter(v.op_type for v in derived.graph.node))}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--release',type=Path);p.add_argument('--execute',action='store_true');a=p.parse_args()
    if not a.execute:print(json.dumps({'status':'PLAN_ONLY_NO_MODEL_PARSE','source_sha256':SOURCE_SHA,'helper_sha256':sha(__file__),'output_dir':str(a.output_dir.resolve())},indent=2));return
    if a.release is None:p.error('separate exact release required')
    expected={'approved':True,'permission':'one_two_site_vocoder_parity_materialization','source_sha256':SOURCE_SHA,'helper_sha256':sha(__file__),'output_dir':str(a.output_dir.resolve())}
    if json.loads(a.release.read_text())!=expected:raise ValueError('release mismatch')
    if a.output_dir.exists() or sha(a.source)!=SOURCE_SHA:raise ValueError('fresh output and exact immutable source required')
    a.output_dir.mkdir(parents=True);started=time.monotonic();result={'status':'started','materializations':1,'model_forwards':0,'SDK_calls':0,'source_sha256':SOURCE_SHA,'helper_sha256':sha(__file__)}
    try:
        import onnx
        model=onnx.load(str(a.source),load_external_data=False);derived,proof=transform(model);delta=structural_delta(model,derived)
        if len(model.graph.node)!=401 or len(model.graph.initializer)!=103:raise ValueError('real source inventory mismatch')
        write(a.output_dir/'shape-proof.json',proof);write(a.output_dir/'structural-delta.json',delta)
        output=a.output_dir/'vocoder-parity.onnx'
        with output.open('xb') as f:f.write(derived.SerializeToString())
        if sha(a.source)!=SOURCE_SHA:raise ValueError('source changed during structural materialization')
        result.update(status='structurally_complete_not_QNN_validated',derivative={'path':str(output.resolve()),'bytes':output.stat().st_size,'sha256':sha(output)},source_nodes=401,derivative_nodes=len(derived.graph.node),original_initializers_unchanged=103,new_integer_controls=7)
    except BaseException as error:result.update(status='error',error={'type':type(error).__name__,'message':str(error)});raise
    finally:
        result['elapsed_seconds']=time.monotonic()-started;result['process_ru_maxrss_kib']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        result['prohibited_modules_imported']=[name for name in ['onnxruntime','torch','executorch'] if name in sys.modules]
        write(a.output_dir/'result.json',result)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
