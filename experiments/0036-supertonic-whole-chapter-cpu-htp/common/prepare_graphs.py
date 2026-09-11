#!/usr/bin/env python3
"""Derive sufficient source graph shapes, never change learned weights."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import resource

ROOT = Path(__file__).resolve().parents[3]
CAP = ROOT/'experiments/0023-supertonic-qnn-precompiled-context-startup/improvements/0001-whole-chapter-capacity/tools/onnx_capacity.py'
SOURCE = ROOT/'experiments/0007-mobile-podcast-preview-bakeoff/artifacts/supertonic-3/snapshot/onnx'
PINNED = {'duration':('duration_predictor.onnx','c3eb91414d5ff8a7a239b7fe9e34e7e2bf8a8140d8375ffb14718b1c639325db'),'text':('text_encoder.onnx','c7befd5ea8c3119769e8a6c1486c4edc6a3bc8365c67621c881bbb774b9902ff'),'vector':('vector_estimator.onnx','883ac868ea0275ef0e991524dc64f16b3c0376efd7c320af6b53f5b780d7c61c'),'vocoder':('vocoder.onnx','085de76dd8e8d5836d6ca66826601f615939218f90e519f70ee8a36ed2a4c4ba')}

def digest(b): return hashlib.sha256(b).hexdigest()

def prepare(component, length, output):
    import onnx
    from onnx import numpy_helper
    import numpy as np
    spec=importlib.util.spec_from_file_location('capacity',CAP);cap=importlib.util.module_from_spec(spec);spec.loader.exec_module(cap)
    name,pinned=PINNED[component];data=(SOURCE/name).read_bytes()
    if digest(data)!=pinned:raise ValueError('source graph pin mismatch')
    source=onnx.load_from_string(data);del data
    cap.reject_external(source)
    derived=onnx.ModelProto();derived.CopyFrom(source)
    if component=='vector':
        cap.require_position_capacity(source,1000,1000)
        i=next(i for i,v in enumerate(derived.graph.initializer) if v.name==cap.INCREMENTS)
        extent=max(3200,length)
        derived.graph.initializer[i].CopyFrom(numpy_helper.from_array(np.arange(extent,dtype=np.int64).reshape(1,extent,1),cap.INCREMENTS))
        old=numpy_helper.to_array(source.graph.initializer[i]);new=numpy_helper.to_array(derived.graph.initializer[i])
        if not np.array_equal(old,new[:,:1000]):raise ValueError('position prefix changed')
    ins,outs=cap.io_shapes(component,3200,length)
    if [v.name for v in derived.graph.input]!=list(ins) or [v.name for v in derived.graph.output]!=list(outs):raise ValueError('ABI names/order mismatch')
    for values,shapes in ((derived.graph.input,ins),(derived.graph.output,outs)):
        for value in values:
            for dim,size in zip(value.type.tensor_type.shape.dim,shapes[value.name]):dim.ClearField('dim_param');dim.dim_value=size
    derived=onnx.shape_inference.infer_shapes(derived,strict_mode=True,data_prop=False)
    if component=='vector':derived=cap.stable_softplus(derived)
    onnx.checker.check_model(derived,full_check=True)
    old_nodes=list(source.graph.node);expected=old_nodes
    if component=='vector':
        i=next(i for i,n in enumerate(old_nodes) if n.name==cap.SOFTPLUS)
        expected=old_nodes[:i]+cap.replacement_nodes()+old_nodes[i+1:]
    if [n.SerializeToString() for n in expected]!=[n.SerializeToString() for n in derived.graph.node]:raise ValueError('unexpected computation change')
    rows=[]
    for old,new in zip(source.graph.initializer,derived.graph.initializer):
        if old.name!=new.name:raise ValueError('initializer ordering change')
        allowed=component=='vector' and old.name==cap.INCREMENTS
        if not allowed and old.SerializeToString()!=new.SerializeToString():raise ValueError('weight/control change')
        rows.append({'name':old.name,'source_sha256':digest(old.SerializeToString()),'derivative_sha256':digest(new.SerializeToString()),'position_extent_only':allowed})
    if len(derived.graph.initializer)!=len(source.graph.initializer)+int(component=='vector'):raise ValueError('extra initializers')
    output.mkdir(parents=True,exist_ok=True);path=output/(component+'.onnx');blob=derived.SerializeToString()
    if path.exists() and path.read_bytes()!=blob:raise ValueError('refuse overwrite different graph')
    path.write_bytes(blob)
    result={'component':component,'source':name,'source_sha256':pinned,'derivative_sha256':digest(blob),'derivative_bytes':len(blob),'inputs':ins,'outputs':outs,'learned_initializer_bytes_unchanged':True,'position_prefix_and_theta_unchanged':True if component=='vector' else None,'position_extent':max(3200,length) if component=='vector' else None,'operator_changes':'Softplus->Relu(x)+Log(1+Exp(-Abs(x)))' if component=='vector' else None,'initializer_audit':rows,'checker_passed':True,'host_neural_forwards':0}
    (output/(component+'-provenance.json')).write_text(json.dumps(result,indent=2)+'\n')
    print(component,digest(blob),len(blob),'maxrss_kib',resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--component',choices=list(PINNED),required=True);p.add_argument('--latent-extent',type=int,default=1);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if not 1<=a.latent_extent<=10000:p.error('invalid extent')
    resource.setrlimit(resource.RLIMIT_AS,(6*1024**3,6*1024**3))
    prepare(a.component,a.latent_extent,a.output)
