#!/usr/bin/env python3
"""Specialize the exact dynamic LFM2 export to fixed-width chunked prefill."""
import argparse,json
from pathlib import Path
import numpy as np,onnx
from onnx import TensorProto,helper,numpy_helper
MASK_PREFIX='/model/attn_mask_reformat/attn_mask_subgraph/'
def shape(v,dims):
 s=v.type.tensor_type.shape
 if len(s.dim)!=len(dims):raise ValueError(f'rank mismatch {v.name}')
 for x,n in zip(s.dim,dims):x.ClearField('dim_param');x.dim_value=n
def run(src,dst,sequence,capacity):
 if not 1<sequence<capacity:raise ValueError('sequence must be in (1, capacity)')
 past=capacity-sequence;m=onnx.load(src,load_external_data=False);gqa=0
 for n in m.graph.node:
  if n.op_type=='GroupQueryAttention' and n.domain=='com.microsoft':
   n.input[5]='seqlens_k';n.input[6]='__max_sequence_length_i32';gqa+=1
 if gqa!=8:raise ValueError(f'expected 8 GQA, got {gqa}')
 kept=[n for n in m.graph.node if not n.name.startswith(MASK_PREFIX)];removed=len(m.graph.node)-len(kept);del m.graph.node[:];m.graph.node.extend(kept)
 kept=[v for v in m.graph.input if v.name!='attention_mask'];del m.graph.input[:];m.graph.input.extend(kept);m.graph.input.append(helper.make_tensor_value_info('seqlens_k',TensorProto.INT32,[1]));m.graph.initializer.append(numpy_helper.from_array(np.asarray(capacity,dtype=np.int32),'__max_sequence_length_i32'))
 for v in m.graph.input:
  if v.name=='input_ids':v.type.tensor_type.elem_type=TensorProto.INT32;shape(v,[1,sequence])
  elif v.name=='position_ids':shape(v,[1,sequence])
  elif v.name=='seqlens_k':shape(v,[1])
  elif v.name.startswith('past_key_values.'):shape(v,[1,8,past,64])
  elif v.name.startswith('past_conv.'):shape(v,[1,2048,3])
 for v in m.graph.output:
  if v.name=='logits':shape(v,[1,sequence,128000])
  elif v.name.startswith('present.'):shape(v,[1,8,capacity,64])
  elif v.name.startswith('present_conv.'):shape(v,[1,2048,3])
 repl={'batch_size':1,'sequence_length':sequence,'past_sequence_length':past,'total_sequence_length':capacity}
 for v in m.graph.value_info:
  for x in v.type.tensor_type.shape.dim:
   if x.dim_param in repl:n=repl[x.dim_param];x.ClearField('dim_param');x.dim_value=n
 dst.parent.mkdir(parents=True,exist_ok=True);onnx.save(m,dst);onnx.checker.check_model(str(dst),full_check=False)
 return {'schema_version':1,'classification':'fixed_chunk_prefill_profile','source':str(src),'destination':str(dst),'sequence_length':sequence,'capacity':capacity,'past_cache_length':past,'gqa_nodes_rewired':gqa,'mask_nodes_removed':removed,'explicit_state':'22 convolution and 8 K/V pairs','onnx_checker':'passed','external_data_loaded_or_copied':False}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('destination',type=Path);p.add_argument('--sequence-length',type=int,required=True);p.add_argument('--capacity',type=int,default=4096);a=p.parse_args();print(json.dumps(run(a.source,a.destination,a.sequence_length,a.capacity),indent=2,sort_keys=True))
