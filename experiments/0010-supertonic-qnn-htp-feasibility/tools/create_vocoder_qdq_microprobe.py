#!/usr/bin/env python3
"""Extract the exact embed-input QDQ pair with its actual frozen CPU input."""
from __future__ import annotations
import argparse,hashlib,json,math
from pathlib import Path
import onnx
from onnx import TensorProto,helper,numpy_helper,utils
SOURCE_SHA="7fe80ba8bc96cd467dc154c5a1979a5e55706dd19a0fc1f60e762abd7d1933f2"
ACTUAL_INPUT_SHA="52d5fb09a78bb31ab5e200346e8284af58d4d55035dc05892702cad975373b8b"
INPUT="/decoder/embed/Pad_output_0";OUTPUT="/decoder/embed/Pad_output_0_DequantizeLinear_Output";SHAPE=[1,24,1434]
NODES=["/decoder/embed/Pad_output_0_QuantizeLinear","/decoder/embed/Pad_output_0_DequantizeLinear"]
def sha(p:Path)->str:
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def extract(model:onnx.ModelProto)->onnx.ModelProto:
 values={x for n in model.graph.node for x in n.output}|{x.name for x in model.graph.input};
 if INPUT not in values or OUTPUT not in values:raise ValueError('exact QDQ boundary tensors absent')
 result=utils.Extractor(model).extract_model([INPUT],[OUTPUT]);del result.graph.input[:];result.graph.input.append(helper.make_tensor_value_info(INPUT,TensorProto.FLOAT,SHAPE));del result.graph.output[:];result.graph.output.append(helper.make_tensor_value_info(OUTPUT,TensorProto.FLOAT,SHAPE));result.doc_string=(result.doc_string+'\n' if result.doc_string else '')+'Exact-real-input diagnostic microprobe for embed Pad QuantizeLinear→DequantizeLinear.';onnx.checker.check_model(result)
 if [n.name for n in result.graph.node]!=NODES:raise ValueError(f'unexpected extracted nodes: {[n.name for n in result.graph.node]}')
 return result
def run(a):
 src,actual,out,prov=map(Path.resolve,(a.input,a.actual_input,a.output,a.provenance));
 if sha(src)!=SOURCE_SHA:raise SystemExit('unexpected source hash')
 if sha(actual)!=ACTUAL_INPUT_SHA or actual.stat().st_size!=math.prod(SHAPE)*4:raise SystemExit('unexpected actual-input hash or size')
 model=onnx.load(str(src));onnx.checker.check_model(model);result=extract(model);out.parent.mkdir(parents=True,exist_ok=True);onnx.save_model(result,str(out),save_as_external_data=False);loaded=onnx.load(str(out));onnx.checker.check_model(loaded)
 init=[]
 for x in loaded.graph.initializer:
  arr=numpy_helper.to_array(x);init.append({'name':x.name,'dtype':str(arr.dtype),'shape':list(arr.shape),'values':arr.tolist(),'tensorproto_sha256':hashlib.sha256(x.SerializeToString(deterministic=True)).hexdigest()})
 report={'schema_version':1,'derivative_type':'exact-real-input-QDQ-microprobe','claim_limit':'Isolated reproduction can distinguish QDQ behavior for this exact tensor, but prefix graph-output/fusion changes remain relevant and this does not establish a general implementation defect.','source':{'sha256':SOURCE_SHA,'path':str(src)},'actual_input':{'name':INPUT,'shape':SHAPE,'bytes':actual.stat().st_size,'sha256':ACTUAL_INPUT_SHA,'path':str(actual)},'output_tensor':{'name':OUTPUT,'shape':SHAPE},'nodes':[{'name':n.name,'domain':n.domain,'op_type':n.op_type,'inputs':list(n.input),'outputs':list(n.output)} for n in loaded.graph.node],'initializers':init,'output_model':{'path':str(out),'bytes':out.stat().st_size,'sha256':sha(out)},'tool':{'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__).resolve()),'onnx':onnx.__version__},'validation':{'onnx_checker':True,'exact_nodes':True,'actual_input_hash_locked':True}}
 prov.parent.mkdir(parents=True,exist_ok=True);prov.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n');print(json.dumps(report,indent=2,sort_keys=True))
def parse():
 p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--actual-input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--provenance',type=Path,required=True);return p.parse_args()
if __name__=='__main__':run(parse())
