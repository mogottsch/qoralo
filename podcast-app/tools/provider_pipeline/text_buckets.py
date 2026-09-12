#!/usr/bin/env python3
"""Reusable DP/text static bucket: preserve six native-T symmetric EDGE boundaries.

No neural execution here. Other attention/constant pads and all initializer bytes
stay untouched. Runtime index arrays depend only on actual processed text length.
"""
import hashlib
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
path = ROOT/'experiments/0037-supertonic-provider-pipeline/htp/tools/materialize.py'
spec = importlib.util.spec_from_file_location('provider_case_materialize', path)
reference = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reference)


def derive(source, component, bucket):
    import onnx
    from onnx import helper
    if component not in ('duration', 'text') or not 10 <= bucket <= 1000:
        raise ValueError('Invalid component/bucket')
    model = reference.capacity.specialize(source, component, bucket, 1)
    radii = (2,) if component == 'duration' else (2, 4, 8)
    # DP prepends its learned sentence token before convnext; include it in the native EDGE span.
    prefix = 1 if component == 'duration' else 0
    if component == 'duration':
        tokens=[v for v in source.graph.initializer if v.name=='tts.dp.sentence_encoder.sentence_token']
        if len(tokens)!=1 or list(tokens[0].dims)!=[1,64,1]:raise ValueError('Unexpected DP sentence-token prefix')
    expected = [n.SerializeToString() for n in source.graph.node]
    edits=[]
    for i, node in enumerate(source.graph.node):
        if node.op_type != 'Pad' or '/convnext.' not in node.name:
            continue
        attrs={a.name:helper.get_attribute_value(a) for a in node.attribute}
        pads=reference.constant_pad_values(source,node)
        if attrs != {'mode':b'edge'} or len(node.input)!=2 or not node.name.endswith('/dwconv/Pad'):
            raise ValueError('Unrecognized frontend EDGE site')
        r=pads[2]
        if r not in radii or pads != [0,0,r,0,0,r]:
            raise ValueError('Unexpected frontend EDGE radius')
        replacement=helper.make_node('Gather',[node.input[0],f'native_text_edge_r{r}'],list(node.output),
            axis=2,name=node.name+'/native_text_boundary_Gather')
        model.graph.node[i].CopyFrom(replacement);expected[i]=replacement.SerializeToString()
        edits.append({'source':node.name,'radius':r,'replacement':replacement.name})
    if len(edits)!=6 or set(x['radius'] for x in edits)!=set(radii):
        raise ValueError('Expected exactly six native-T EDGE sites')
    for r in radii:
        name=f'native_text_edge_r{r}'
        if any(name in list(n.input)+list(n.output) for n in source.graph.node):raise ValueError('Input collision')
        model.graph.input.append(helper.make_tensor_value_info(name,onnx.TensorProto.INT32,[bucket+prefix+2*r]))
    model=onnx.shape_inference.infer_shapes(model,strict_mode=True,data_prop=False)
    onnx.checker.check_model(model,full_check=True)
    if [n.SerializeToString() for n in model.graph.node]!=expected:raise ValueError('Unapproved node delta')
    if [n.SerializeToString() for n in model.graph.initializer]!=[n.SerializeToString() for n in source.graph.initializer]:raise ValueError('Initializer delta')
    return model,{'component':component,'bucket':bucket,'edge_sites':edits,'all_initializers_byte_identical':True,
        'all_other_nodes_byte_identical':True,'sequencePrefix':prefix,
        'runtime_indices':'clip(arange(-r,bucket+prefix+r),0,actual_native_T+prefix-1).astype(int32)',
        'numeric_or_HTP_validation':False}


def runtime_edges(native_t,bucket,component):
    import numpy as np
    if not 1 <= native_t <= bucket:raise ValueError('Native T outside bucket')
    radii=(2,) if component=='duration' else (2,4,8)
    prefix=1 if component=='duration' else 0
    return {f'native_text_edge_r{r}':np.clip(np.arange(-r,bucket+prefix+r,dtype=np.int32),0,native_t+prefix-1) for r in radii}
