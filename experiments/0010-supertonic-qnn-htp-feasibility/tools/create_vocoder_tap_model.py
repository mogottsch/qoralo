#!/usr/bin/env python3
"""Create deterministic single-output prefix taps of the explicit-GELU vocoder.

The tool is intentionally locked to the accepted experiment-0010 derivative.
It preserves the exact selected tensor name and extracts only its dependency
prefix from the frozen one-input model. Tap results are diagnostic: extraction
and graph-output changes may alter QNN fusion and do not alone prove causality.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
from typing import NamedTuple
import onnx
from onnx import TensorProto, helper, utils

EXPECTED_SOURCE_SHA256="7fe80ba8bc96cd467dc154c5a1979a5e55706dd19a0fc1f60e762abd7d1933f2"
class Tap(NamedTuple): tensor:str; shape:tuple[int,...]; boundary:str
TAPS:dict[str,Tap]={
 "predecoder_affine":Tap("/Add_output_0",(1,24,1428),"decoder affine input before embed Pad/QDQ/Conv"),
 "embed_pad":Tap("/decoder/embed/Pad_output_0",(1,24,1434),"embed Pad output before input QDQ"),
 "embed_pad_qdq":Tap("/decoder/embed/Pad_output_0_DequantizeLinear_Output",(1,24,1434),"embed Pad output after input QDQ"),
 "embed_conv":Tap("/decoder/embed/net/Conv_output_0",(1,512,1428),"embed Conv output before activation QDQ"),
 "embed_qdq":Tap("/decoder/embed/net/Conv_output_0_DequantizeLinear_Output",(1,512,1428),"embed Conv output after activation QDQ"),
 "convnext3_add":Tap("/decoder/convnext.3/Add_output_0",(1,512,1428),"residual output after ConvNeXt block 3"),
 "convnext7_add":Tap("/decoder/convnext.7/Add_output_0",(1,512,1428),"residual output after ConvNeXt block 7"),
 "convnext9_add":Tap("/decoder/convnext.9/Add_output_0",(1,512,1428),"residual output after float-weight ConvNeXt block 9"),
 "final_norm":Tap("/decoder/final_norm/BatchNormalization_output_0",(1,512,1428),"decoder final normalization"),
 "head_layer2":Tap("/decoder/head/layer2/Conv_output_0",(1,512,1428),"final folded-float-weight head Conv before reshape"),
 "waveform":Tap("wav_tts",(1,731136),"final waveform"),
}
for i in range(8):
 p=f"/decoder/convnext.{i}"
 TAPS.update({
  f"c{i}_dwconv_qdq":Tap(f"{p}/dwconv/net/Conv_output_0_DequantizeLinear_Output",(1,512,1428),f"block {i} depthwise Conv after output QDQ"),
  f"c{i}_norm":Tap(f"{p}/norm/Transpose_1_output_0",(1,512,1428),f"block {i} normalization before QDQ"),
  f"c{i}_norm_qdq":Tap(f"{p}/norm/Transpose_1_output_0_DequantizeLinear_Output",(1,512,1428),f"block {i} normalization after QDQ"),
  f"c{i}_pwconv1":Tap(f"{p}/pwconv1/Conv_output_0",(1,2048,1428),f"block {i} pointwise Conv 1 before QDQ"),
  f"c{i}_pwconv1_qdq":Tap(f"{p}/pwconv1/Conv_output_0_DequantizeLinear_Output",(1,2048,1428),f"block {i} pointwise Conv 1 after QDQ"),
  f"c{i}_gelu":Tap(f"{p}/act/Mul_1_output_0",(1,2048,1428),f"block {i} explicit com.microsoft.Gelu before QDQ"),
  f"c{i}_gelu_qdq":Tap(f"{p}/act/Mul_1_output_0_DequantizeLinear_Output",(1,2048,1428),f"block {i} explicit Gelu after QDQ"),
  f"c{i}_pwconv2":Tap(f"{p}/pwconv2/Conv_output_0",(1,512,1428),f"block {i} pointwise Conv 2 before QDQ"),
  f"c{i}_pwconv2_qdq":Tap(f"{p}/pwconv2/Conv_output_0_DequantizeLinear_Output",(1,512,1428),f"block {i} pointwise Conv 2 after QDQ"),
  f"c{i}_add":Tap(f"{p}/Add_output_0",(1,512,1428),f"block {i} residual output"),
 })
# The coarse registry names are canonical for these two boundaries.
TAPS.pop("c3_add")
TAPS.pop("c7_add")
def sha(p:Path)->str:
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def extract_tap(model:onnx.ModelProto,tap_id:str)->onnx.ModelProto:
 tap=TAPS[tap_id]
 all_values={x for n in model.graph.node for x in n.output}|{x.name for x in model.graph.input}
 if tap.tensor not in all_values:raise ValueError(f"tap tensor absent: {tap.tensor}")
 extracted=utils.Extractor(model).extract_model(["latent"],[tap.tensor])
 del extracted.graph.output[:]
 extracted.graph.output.append(helper.make_tensor_value_info(tap.tensor,TensorProto.FLOAT,list(tap.shape)))
 extracted.doc_string=(extracted.doc_string+"\n" if extracted.doc_string else "")+f"Diagnostic prefix tap {tap_id}: {tap.tensor}. Graph-output changes may alter QNN fusion."
 onnx.checker.check_model(extracted)
 return extracted

def run(a:argparse.Namespace)->None:
 src,out,prov=a.input.resolve(),a.output.resolve(),a.provenance.resolve(); source_hash=sha(src)
 if source_hash!=EXPECTED_SOURCE_SHA256:raise SystemExit(f"unexpected source hash: {source_hash}")
 tap=TAPS[a.tap_id]; model=onnx.load(str(src)); onnx.checker.check_model(model)
 try: extracted=extract_tap(model,a.tap_id)
 except ValueError as e: raise SystemExit(str(e)) from e
 out.parent.mkdir(parents=True,exist_ok=True);onnx.save_model(extracted,str(out),save_as_external_data=False)
 loaded=onnx.load(str(out));onnx.checker.check_model(loaded)
 if len(loaded.graph.input)!=1 or loaded.graph.input[0].name!="latent" or len(loaded.graph.output)!=1 or loaded.graph.output[0].name!=tap.tensor:raise SystemExit("saved tap IO validation failed")
 report={"schema_version":1,"derivative_type":"diagnostic-prefix-tap","claim_limit":"Adding a graph output and cutting a prefix may alter QNN fusion/partitioning; this localizes evidence but does not prove operator causality.","tap":{"id":a.tap_id,"tensor":tap.tensor,"shape":list(tap.shape),"elements":__import__('math').prod(tap.shape),"boundary":tap.boundary},"source":{"path":str(src),"bytes":src.stat().st_size,"sha256":source_hash,"nodes":len(model.graph.node)},"output":{"path":str(out),"bytes":out.stat().st_size,"sha256":sha(out),"nodes":len(loaded.graph.node)},"validation":{"onnx_checker_before":True,"onnx_checker_after_reload":True,"exact_input_name":"latent","exact_output_name":tap.tensor,"concrete_output_shape":list(tap.shape)},"tool":{"path":str(Path(__file__).resolve()),"sha256":sha(Path(__file__).resolve()),"onnx":onnx.__version__}}
 prov.parent.mkdir(parents=True,exist_ok=True);prov.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n");print(json.dumps(report,indent=2,sort_keys=True))
def parse()->argparse.Namespace:
 p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--tap-id',choices=sorted(TAPS),required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--provenance',type=Path,required=True);return p.parse_args()
if __name__=='__main__':run(parse())
