#!/usr/bin/env python3
"""Targeted DP source trace: saved metadata + one protobuf parse; no inference."""
import hashlib
import json
from pathlib import Path
import struct
import sys

ROOT=Path(__file__).resolve().parents[2]
REPO=ROOT.parents[3]
OUT=Path(__file__).resolve().parent


def pin(p):return {'path':str(p),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}


def save(p,value):
    with p.open('x') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')


def main():
    path=ROOT/'results/host-preparation-20260910/raw/inspect-duration-01/data/metadata.json';d=json.loads(path.read_text());nodes=d['nodes'];by={o:n for n in nodes for o in n['outputs']}
    source=REPO/'experiments/0007-mobile-podcast-preview-bakeoff/artifacts/supertonic-3/snapshot/onnx/duration_predictor.onnx';source_pin=pin(source);assert source_pin['sha256']=='c3eb91414d5ff8a7a239b7fe9e34e7e2bf8a8140d8375ffb14718b1c639325db'
    # Parse source protobuf to bind saved node interfaces and three tiny nonlearned constants.
    # Embedded learned bytes are parsed opaquely, never converted/evaluated or copied to this report.
    import onnx
    model=onnx.load(str(source),load_external_data=False)
    assert len(model.graph.node)==len(nodes)==1086 and len(model.graph.initializer)==98
    for saved,actual in zip(nodes,model.graph.node):assert (saved['name'],saved['op'],saved['inputs'],saved['outputs'])==(actual.name,actual.op_type,list(actual.input),list(actual.output))
    wanted=['/sentence_encoder/ConstantOfShape_1','/sentence_encoder/attn_encoder/attn_layers.0/Constant_88','/sentence_encoder/attn_encoder/attn_layers.1/Constant_87']
    floats=[]
    for n in model.graph.node:
        if n.name in wanted:
            t=next(a.t for a in n.attribute if a.name=='value');assert t.data_type==1 and list(t.dims) in ([],[1])
            values=list(t.float_data) if t.float_data else list(struct.unpack('<f',t.raw_data));assert len(values)==1
            floats.append({'node':n.name,'dtype':'FLOAT','shape':list(t.dims),'value':values[0],'tensor_proto_sha256':hashlib.sha256(t.SerializeToString()).hexdigest()})
    assert [x['value'] for x in floats]==[1.0,-10000.0,-10000.0]
    del model

    def expr(x):
        if not x:return None
        n=by.get(x)
        if not n:return x
        if n['op']=='Constant':return n['attributes']['value']['small_values']
        if n['op']=='Shape':return {'Shape':n['inputs'][0]}
        if n['op'] in ['Unsqueeze','Cast']:return expr(n['inputs'][0])
        if n['op'] in ['Add','Sub','Mul','Div','Clip','Gather']:return {n['op']:[expr(i) for i in n['inputs']]}
        raise ValueError('unhandled control path: '+n['name'])

    slices=[]
    for i,n in enumerate(nodes):
        if n['op']!='Slice':continue
        control=[expr(v) for v in n['inputs'][1:]]
        if control==[[-1],[-9223372036854775807],[0],[-1]]:kind='reverse padding-pair control rows; NOT a text slice'
        elif n['name']=='/sentence_encoder/Slice':kind='shape-only mask prefix seed for prepended sentence-token mask1; full text_mask still concatenated'
        elif n['name'] in ['/sentence_encoder/Slice_1','/sentence_encoder/Slice_2']:kind='read position0 sentence token/mask AFTER full encoder; NOT input-prefix clipping'
        elif n['name'].endswith(('/Slice_1','/Slice_10')):kind='relative K/V table pad/crop: axis1 [max(5-S,0):max(5-S,0)+2*S-1], S=T+1'
        elif n['name'].endswith('/Slice_4'):kind='relative-to-absolute scores: axis2 [0:S] in rearranged [B,2,S+1,2*S-1]'
        elif n['name'].endswith('/Slice_5'):kind='relative-to-absolute scores: axis3 [S-1:] yields full [B,2,S,S]'
        elif n['name'].endswith('/Slice_8'):kind='absolute-to-relative weights: axis3 [1:] in rearranged [B,2,S,2*S], yields [B,2,S,2*S-1]'
        else:raise ValueError('unclassified Slice '+n['name'])
        slices.append({'index':i,'name':n['name'],'data':n['inputs'][0],'controls_start_end_axis_step':control,'role':kind})
    assert len(slices)==31 and sum(s['role'].startswith('reverse') for s in slices)==18
    clips=[{'index':i,'node':n,'control_expression':expr(n['outputs'][0]),'role':'max(S-5,0) or max(5-S,0): relative-table padding/cropping, no maximum clamp'} for i,n in enumerate(nodes) if n['op']=='Clip'];assert len(clips)==4
    depthwise=[{'index':i,'node':n} for i,n in enumerate(nodes) if n['op']=='Conv' and '/dwconv/' in n['name']];assert len(depthwise)==6
    assert all(v['node']['attributes']=={'dilations':[1],'group':64,'kernel_shape':[5],'pads':[0,0],'strides':[1]} for v in depthwise)
    pads=[{'index':i,'node':n} for i,n in enumerate(nodes) if n['op']=='Pad'];assert len(pads)==18
    assert all(n['attributes']['strides']==[1] for n in nodes if n['op']=='Conv')
    assert not [n for n in nodes if n['op'] in ['ReduceMean','ReduceSum','AveragePool','MaxPool','GlobalAveragePool','GlobalMaxPool','Range','Trilu']]
    selected=[{'index':i,'node':n} for i,n in enumerate(nodes) if i<=29 or i>=1050 or n['op'] in ['Softmax','Where','MatMul'] or (n['name'].endswith(('/attn_encoder/Mul','/attn_encoder/Unsqueeze','/attn_encoder/Unsqueeze_1')))]
    report={'status':'SOURCE_ONLY_TRACE_NO_INFERENCE','source':source_pin,'saved_metadata':pin(path),'source_node_interfaces_match':1086,'initializers_metadata_count':98,'new_model_sessions':0,'new_model_forwards':0,'graph_mutations':0,'parser':'onnx'+onnx.__version__,'nonlearned_scalar_constants':floats,'slices':slices,'clips':clips,'depthwise':depthwise,'pads':pads,'selected_path_nodes':selected,'relevant_initializer_metadata':[v for v in d['initializers'] if any(s in v['name'] for s in ['sentence_token','emb_rel_','proj_out.net.weight','predictor.layers'])],'no_sequence_reduction_pool_ops':True,'no_strided_conv_downsampling':True,'S_definition':'T+1: full text plus one prepended learned sentence token','static_conclusion':'No fixed input-prefix/time cap in this exported DP graph. Global masked two-head/two-layer attention feeds a64-dimensional sentence-token readout; concatenate128style values,192->128->1 MLP/Exp. No explicit linear length-count/sum path into the head.','limits':'Structural full-sequence reachability does not prove nonzero learned attention/coverage or trained long-context quality; no values/attention activations evaluated; no intrinsic30s cap established.'}
    assert pin(source)==source_pin;save(OUT/'source-trace.json',report)
    pkg=REPO/'experiments/0007-mobile-podcast-preview-bakeoff/artifacts/supertonic-3/venv/lib/python3.11/site-packages/supertonic'
    files={'config.py':[(198,212),(241,244)],'pipeline.py':[(158,184),(261,269),(281,321)],'utils.py':[(154,220)],'core.py':[(451,461),(506,539)]}
    snippets=[]
    for name,ranges in files.items():
        p=pkg/name;lines=p.read_text().splitlines();snippets.append({'file':pin(p),'passages':[{'start_line':a,'end_line':b,'text':'\n'.join(lines[a-1:b])} for a,b in ranges]})
    meta=pkg.parent/'supertonic-1.3.1.dist-info/METADATA';config=REPO/'experiments/0007-mobile-podcast-preview-bakeoff/artifacts/supertonic-3/snapshot/onnx/tts.json'
    save(OUT/'upstream-source.json',{'package_metadata':pin(meta),'package_version':'1.3.1','repository':'https://github.com/supertone-inc/supertonic-py','passages':snippets,'model_config':pin(config),'DP_config':json.loads(config.read_text())['dp'],'conclusion':'Official packaged frontend documents300characters general/120Korean per chunk, then per-chunk model calls+silence+concatenation. Helper groups whole sentences so a single overlong sentence can exceed max_len.100000 is frontend request guard, not model horizon. None of these docs establishes a300character training limit or permits chunks for this whole-chapter task.'})
    print(json.dumps({'nodes':1086,'slices_classified':31,'pad_control_reverse_slices':18,'relative_alignment_slices':10,'seed_readout_slices':3,'clips':4,'source_postpin':'unchanged','ORT_imported':'onnxruntime' in sys.modules,'model_sessions':0,'model_forwards':0},indent=2))


if __name__=='__main__':main()
