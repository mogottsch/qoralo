#!/usr/bin/env python3
"""Create a shape-bound text-conditioner graph without changing learned tensors."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import onnx
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def setshape(value,shape):
 dims=value.type.tensor_type.shape.dim
 if len(dims)!=len(shape):raise ValueError((value.name,len(dims),shape))
 for dim,size in zip(dims,shape):dim.ClearField('dim_param');dim.dim_value=size
def main():
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--tokens',type=int,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args();model=onnx.load(str(a.source));inputs={x.name:x for x in model.graph.input};outputs={x.name:x for x in model.graph.output};setshape(inputs['token_ids'],[1,a.tokens]);setshape(outputs['embeddings'],[1,a.tokens,1024]);model=onnx.shape_inference.infer_shapes(model,strict_mode=True);onnx.checker.check_model(model,full_check=True);a.output.parent.mkdir(parents=True,exist_ok=True);onnx.save(model,str(a.output));result={'schema_version':1,'derivative':'I/O shape specialization only','source':str(a.source),'source_sha256':sha(a.source),'tokens':a.tokens,'output':str(a.output),'output_sha256':sha(a.output),'input_shape':[1,a.tokens],'output_shape':[1,a.tokens,1024]};a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
