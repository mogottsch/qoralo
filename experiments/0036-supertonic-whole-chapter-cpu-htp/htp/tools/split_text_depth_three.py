#!/usr/bin/env python3
"""Partition TEXT by network depth, never by text positions or audio duration.

Every original operator and learned initializer remains byte-identical. Both
parts operate at full T3200. Only an existing hidden-state edge becomes a public
inter-part tensor; common mask/style remain original inputs. No runtime imports.
"""
import argparse
import hashlib
import json
from pathlib import Path
import resource
import time
from materialize import sha

SOURCE_SHA='a392eab0764baa31ce60229afc5c6ed007beaffadfc4b63e4f0a39359a6117f7'
CUT0='/text_encoder/attn_encoder/norm_layers_2.0/Transpose_1_output_0'
CUT2='/text_encoder/attn_encoder/norm_layers_2.2/Transpose_1_output_0'
RESIDUAL='/text_encoder/convnext/convnext.5/Mul_3_output_0'
BOUNDARY=(CUT0,CUT2,RESIDUAL)


def split(source):
    import onnx
    from onnx.utils import Extractor
    # Pin the complete original input/output contract before extracting anything.
    def shapes(values):
        return {v.name:[d.dim_value if d.HasField('dim_value') else d.dim_param for d in v.type.tensor_type.shape.dim] for v in values}
    if shapes(source.graph.input)!={'text_ids':[1,3200],'style_ttl':[1,50,256],'text_mask':[1,1,3200]} or shapes(source.graph.output)!={'text_emb':[1,256,3200]}:
        raise ValueError('only complete T3200 text graph allowed')
    producers={v:n for n in source.graph.node for v in n.output}
    if any(name not in producers or producers[name].op_type!='Transpose' for name in (CUT0,CUT2)):raise ValueError('source cut edge missing')
    a=Extractor(source).extract_model(['text_ids','text_mask'],[CUT0,RESIDUAL])
    b=Extractor(source).extract_model([CUT0,'text_mask'],[CUT2])
    c=Extractor(source).extract_model([CUT2,RESIDUAL,'style_ttl','text_mask'],['text_emb'])
    models={'text3_a':a,'text3_b':b,'text3_c':c}
    # Original annotations have a symbolic batch on this edge. Batch1 and T3200
    # are inherited from the exact public source ABI, then verified by CPU proof.
    for model in models.values():
        for v in [*model.graph.input,*model.graph.output,*model.graph.value_info]:
            if v.name in BOUNDARY:
                v.CopyFrom(onnx.helper.make_tensor_value_info(v.name,onnx.TensorProto.FLOAT,[1,256,3200]))
        onnx.checker.check_model(model,full_check=True)
    original_nodes={n.name:n.SerializeToString() for n in source.graph.node}
    original_init={v.name:v.SerializeToString() for v in source.graph.initializer}
    seen_nodes={};seen_init={}
    for label,model in models.items():
        for n in model.graph.node:
            if n.name not in original_nodes or n.SerializeToString()!=original_nodes[n.name]:raise ValueError('changed computation node')
            seen_nodes.setdefault(n.name,[]).append(label)
        for v in model.graph.initializer:
            if v.name not in original_init or v.SerializeToString()!=original_init[v.name]:raise ValueError('changed learned/constant initializer')
            seen_init.setdefault(v.name,[]).append(label)
    if set(seen_nodes)!=set(original_nodes):raise ValueError('partition dropped original nodes')
    if set(seen_init)!=set(original_init):raise ValueError('partition dropped original initializers')
    # Any shared upstream work must be nonlearned mask/control arithmetic only.
    duplicates=[n for n in source.graph.node if len(seen_nodes[n.name])>1]
    allowed={'Constant','Mul','Unsqueeze','Equal','Not','Cast','Shape','Gather','Concat','Reshape','Transpose'}
    for n in duplicates:
        if n.op_type not in allowed or any(v in original_init for v in n.input):raise ValueError('shared learned computation would be recomputed')
    report={'source_nodes':len(original_nodes),'source_initializers':len(original_init),
            'all_original_nodes_covered':True,'all_original_node_bytes_unchanged':True,
            'all_original_initializer_bytes_unchanged':True,'all_original_initializers_covered':True,
            'shared_nonlearned_nodes':[{'name':n.name,'op':n.op_type} for n in duplicates],
            'boundaries':[{'name':name,'shape':[1,256,3200],'bytes_float32':1*256*3200*4} for name in BOUNDARY],
            'sequence_extent_unchanged':3200,'operator_algebra_changed':False,'model_forwards':0,
            'parts':{label:{'nodes':len(model.graph.node),'initializers':len(model.graph.initializer),'inputs':shapes(model.graph.input),'outputs':shapes(model.graph.output)} for label,model in models.items()}}
    return models,report


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if '.local' not in a.output.parts:raise ValueError('private graph output required')
    if sha(a.source)!=SOURCE_SHA:raise ValueError('wrong source graph')
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
    start=time.monotonic();a.output.mkdir(parents=True,exist_ok=False)
    import onnx
    models,report=split(onnx.load(str(a.source),load_external_data=False))
    report['source_sha256']=SOURCE_SHA
    for label,model in models.items():
        part=a.output/label;part.mkdir();path=part/(label+'.onnx');path.write_bytes(model.SerializeToString())
        result={'component':label,'inputs':report['parts'][label]['inputs'],'outputs':report['parts'][label]['outputs'],
                'derivative':{'path':str(path.resolve()),'bytes':path.stat().st_size,'sha256':sha(path)}}
        (part/'result.json').write_text(json.dumps(result,indent=2)+'\n');report['parts'][label]['derivative']=result['derivative']
    report.update(elapsed_seconds=time.monotonic()-start,maxrss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    (a.output/'structural-proof.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
