#!/usr/bin/env python3
"""Read only ValueInfo protobufs from existing ONNX files; skip graph payloads/weights.

No ModelProto/GraphProto load, shape inference, model runtime or graph mutation.
Full-file identities are streamed; initializer/Constant payloads are never decoded.
"""
import hashlib
import json
import math
from pathlib import Path
import sys


def varint(f):
    value=0
    for shift in range(0,70,7):
        b=f.read(1)
        if not b:raise ValueError('truncated protobuf varint')
        value|=(b[0]&127)<<shift
        if b[0]<128:return value
    raise ValueError('oversized protobuf varint')


def spans(f,end):
    while f.tell()<end:
        tag=varint(f);field,wire=tag>>3,tag&7
        if field==0:raise ValueError('invalid protobuf field')
        if wire==2:size=varint(f);start=f.tell()
        elif wire==0:
            start=f.tell();varint(f);size=f.tell()-start
        elif wire in (1,5):start=f.tell();size=8 if wire==1 else 4
        else:raise ValueError('unsupported protobuf wire type')
        if start+size>end:raise ValueError('protobuf span out of bounds')
        yield field,wire,start,size
        f.seek(start+size)
    if f.tell()!=end:raise ValueError('protobuf boundary mismatch')


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def inspect(path,expected):
    if sha(path)!=expected:raise ValueError('model file identity changed')
    from onnx import ValueInfoProto  # only leaf metadata messages; no model loader
    widths={1:4,2:1,3:1,4:2,5:2,6:4,7:8,9:1,10:2,11:8,12:4,13:8,14:8,15:16,16:2}
    rows=[];counts={};metadata_bytes=0
    with path.open('rb') as f:
        graphs=[(start,size) for field,wire,start,size in spans(f,path.stat().st_size) if field==7 and wire==2]
        if len(graphs)!=1:raise ValueError('one existing graph required')
        start,size=graphs[0];f.seek(start)
        for field,wire,offset,length in spans(f,start+size):
            counts[str(field)]=counts.get(str(field),0)+1
            if field not in (11,12,13):continue
            if wire!=2 or length>65536:raise ValueError('unexpected/oversized ValueInfo')
            f.seek(offset);value=ValueInfoProto();value.ParseFromString(f.read(length));metadata_bytes+=length
            tensor=value.type.tensor_type
            shape=[d.dim_value if d.HasField('dim_value') else d.dim_param or None for d in tensor.shape.dim] if tensor.HasField('shape') else None
            elements=math.prod(shape) if shape is not None and all(type(d) is int and d>=0 for d in shape) else None
            width=widths.get(tensor.elem_type);logical=None if elements is None or width is None else elements*width
            rows.append({'name':value.name,'kind':{11:'input',12:'output',13:'value_info'}[field],'dtype':tensor.elem_type,'shape':shape,'elements':elements,'logical_bytes':logical,'bytes_reason':None if logical is not None else 'Unresolved shape or unsupported element width.'})
    if sha(path)!=expected:raise ValueError('source changed during metadata inspection')
    return {'path':str(path),'bytes':path.stat().st_size,'sha256':expected,'metadata_payload_bytes_decoded':metadata_bytes,'graph_field_counts':counts,'ModelProto_or_GraphProto_loads':0,'initializer_or_Constant_payloads_decoded':0,'model_or_QNN_runtime_calls':0,'rows':rows}


def liveness_hint(rows,nodes):
    sizes={v['name']:v['logical_bytes'] for v in rows};last={};live={};peak=0;at=None;unknown=set()
    for index,node in enumerate(nodes):
        for name in node['inputs']:last[name]=index
    for v in rows:
        if v['kind']=='output':last[v['name']]=len(nodes)
        if v['kind']=='input' and v['logical_bytes'] is not None:live[v['name']]=v['logical_bytes']
    for index,node in enumerate(nodes):
        for name in node['outputs']:
            if sizes.get(name) is None:unknown.add(name)
            else:live[name]=sizes[name]
        current=sum(live.values())
        if current>peak:peak=current;at=node['name']
        for name in list(live):
            if last.get(name,index)<=index:del live[name]
    return {'logical_schedule_peak_bytes':peak,'peak_node':at,'unknown_output_names':sorted(unknown),
            'assumptions':'Source node order; materialize each named output before retiring last-used inputs; no alias/in-place/fusion; initializer weights excluded. Not actual compiler liveness, scratch workspace, target VTCM or host peak.'}


def main():
    root=Path(__file__).resolve().parents[1];repo=root.parents[3];out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False)
    sources=[('L238',repo/'experiments/0023-supertonic-qnn-precompiled-context-startup/.local/clean-setup-campaign/source-package/vocoder.onnx','35b90eeae4a01d06f82dccc903a63d23c95eb2d9095ffa0d62f2cf151817c7c7'),
             ('L2048',root/'.local/materialization-20260910/attempt-01/vocoder/data/vocoder.onnx','539f8ef7850292b3b5add1b9b29012e6bff86c13caebad06ef802cec261df792')]
    original=json.loads((root/'results/host-preparation-20260910/raw/inspect-vocoder-01/data/metadata.json').read_text())
    results={}
    for label,path,expected in sources:
        result=inspect(path,expected);result['logical_liveness_hint']=liveness_hint(result['rows'],original['nodes'])
        result['largest_tensors']=sorted([v for v in result['rows'] if v['logical_bytes'] is not None],key=lambda v:v['logical_bytes'],reverse=True)[:30]
        with (out/(label+'.json')).open('x') as f:json.dump(result,f,indent=2);f.write('\n')
        results[label]={'sha256':expected,'rows':len(result['rows']),'metadata_payload_bytes_decoded':result['metadata_payload_bytes_decoded'],'largest':result['largest_tensors'][:3],'liveness':result['logical_liveness_hint']}
    with (out/'summary.json').open('x') as f:json.dump(results,f,indent=2);f.write('\n')
    print(json.dumps(results,indent=2))


if __name__=='__main__':main()
