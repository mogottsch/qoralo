#!/usr/bin/env python3
"""Lower fixed-width chunked LFM2 RotaryEmbedding/GQA to standard HTP ops."""
import argparse,json
from pathlib import Path
import numpy as np,onnx
from onnx import TensorProto,helper,numpy_helper
def setshape(v,d):
 s=v.type.tensor_type.shape
 if len(s.dim)!=len(d):raise ValueError(f'rank mismatch {v.name}')
 for x,n in zip(s.dim,d):x.ClearField('dim_param');x.dim_value=n
def lower(src,dst,sequence,capacity):
 past=capacity-sequence;m=onnx.load(src,load_external_data=False);prod={y:n for n in m.graph.node for y in n.output};remove=set();repl={}
 vals={'__attn_shape_q':[1,sequence,32,64],'__attn_shape_kv':[1,sequence,8,64],'__attn_shape_q_3d':[1,sequence,2048],'__attn_shape_kv_3d':[1,sequence,512],'__attn_shape_key_repeat':[1,32,64,capacity],'__attn_shape_value_repeat':[1,32,capacity,64],'__attn_shape_output':[1,sequence,2048],'__attn_unsqueeze_head_axis':[2],'__attn_tile_heads':[1,1,4,1,1],'__rope_split':[32,32],'__rope_unsqueeze_head_axis':[2]}
 for n,v in vals.items():m.graph.initializer.append(numpy_helper.from_array(np.asarray(v,dtype=np.int64),n))
 m.graph.initializer.append(numpy_helper.from_array(np.asarray(.125,dtype=np.float32),'__attn_scale'))
 def rotary(inp,out,heads,p):
  sn='__attn_shape_q' if heads==32 else '__attn_shape_kv';on='__attn_shape_q_3d' if heads==32 else '__attn_shape_kv_3d';q=lambda s:f'{p}/{s}'
  return [helper.make_node('Reshape',[inp,sn],[q('reshape')],name=q('reshape')),helper.make_node('Gather',['cos_cache','position_ids'],[q('cos_half')],name=q('cos_half'),axis=0),helper.make_node('Gather',['sin_cache','position_ids'],[q('sin_half')],name=q('sin_half'),axis=0),helper.make_node('Concat',[q('cos_half'),q('cos_half')],[q('cos_full')],name=q('cos_full'),axis=-1),helper.make_node('Concat',[q('sin_half'),q('sin_half')],[q('sin_full')],name=q('sin_full'),axis=-1),helper.make_node('Unsqueeze',[q('cos_full'),'__rope_unsqueeze_head_axis'],[q('cos')],name=q('cos')),helper.make_node('Unsqueeze',[q('sin_full'),'__rope_unsqueeze_head_axis'],[q('sin')],name=q('sin')),helper.make_node('Split',[q('reshape'),'__rope_split'],[q('first_half'),q('second_half')],name=q('split'),axis=3),helper.make_node('Neg',[q('second_half')],[q('negative_second_half')],name=q('negative_second_half')),helper.make_node('Concat',[q('negative_second_half'),q('first_half')],[q('rotated_half')],name=q('rotated_half'),axis=3),helper.make_node('Mul',[q('reshape'),q('cos')],[q('scaled')],name=q('scaled')),helper.make_node('Mul',[q('rotated_half'),q('sin')],[q('rotated_scaled')],name=q('rotated_scaled')),helper.make_node('Add',[q('scaled'),q('rotated_scaled')],[q('result4')],name=q('result4')),helper.make_node('Reshape',[q('result4'),on],[out],name=p)]
 count=0
 for n in m.graph.node:
  if n.op_type!='GroupQueryAttention' or n.domain!='com.microsoft':continue
  count+=1;qr=prod[n.input[0]];kr=prod[n.input[1]]
  if qr.op_type!='RotaryEmbedding' or kr.op_type!='RotaryEmbedding':raise ValueError('unexpected rotary producer')
  remove.update((id(qr),id(kr)));p=f'{n.name}/htp_chunk';q=lambda s:f'{p}/{s}';xs=[];xs+=rotary(qr.input[0],qr.output[0],32,q('q_rotary'));xs+=rotary(kr.input[0],kr.output[0],8,q('k_rotary'))
  xs += [helper.make_node('Reshape',[qr.output[0],'__attn_shape_q'],[q('q_shape')],name=q('q_shape')),helper.make_node('Transpose',[q('q_shape')],[q('query')],name=q('query'),perm=[0,2,1,3]),helper.make_node('Reshape',[kr.output[0],'__attn_shape_kv'],[q('k_shape')],name=q('k_shape')),helper.make_node('Transpose',[q('k_shape')],[n.output[1]],name=q('key_new'),perm=[0,2,3,1]),helper.make_node('Reshape',[n.input[2],'__attn_shape_kv'],[q('v_shape')],name=q('v_shape')),helper.make_node('Transpose',[q('v_shape')],[n.output[2]],name=q('value_new'),perm=[0,2,1,3]),helper.make_node('Concat',[n.input[3],n.output[1]],[q('all_key')],name=q('all_key'),axis=3),helper.make_node('Concat',[n.input[4],n.output[2]],[q('all_value')],name=q('all_value'),axis=2),helper.make_node('Unsqueeze',[q('all_key'),'__attn_unsqueeze_head_axis'],[q('key_u')],name=q('key_u')),helper.make_node('Unsqueeze',[q('all_value'),'__attn_unsqueeze_head_axis'],[q('value_u')],name=q('value_u')),helper.make_node('Tile',[q('key_u'),'__attn_tile_heads'],[q('key_t')],name=q('key_t')),helper.make_node('Tile',[q('value_u'),'__attn_tile_heads'],[q('value_t')],name=q('value_t')),helper.make_node('Reshape',[q('key_t'),'__attn_shape_key_repeat'],[q('key_r')],name=q('key_r')),helper.make_node('Reshape',[q('value_t'),'__attn_shape_value_repeat'],[q('value_r')],name=q('value_r')),helper.make_node('MatMul',[q('query'),q('key_r')],[q('scores')],name=q('scores')),helper.make_node('Mul',[q('scores'),'__attn_scale'],[q('scaled_scores')],name=q('scaled_scores')),helper.make_node('Add',[q('scaled_scores'),'attention_mask'],[q('masked_scores')],name=q('masked_scores')),helper.make_node('Softmax',[q('masked_scores')],[q('probabilities')],name=q('probabilities'),axis=-1),helper.make_node('MatMul',[q('probabilities'),q('value_r')],[q('attended')],name=q('attended')),helper.make_node('Transpose',[q('attended')],[q('attended_bsnh')],name=q('attended_bsnh'),perm=[0,2,1,3]),helper.make_node('Reshape',[q('attended_bsnh'),'__attn_shape_output'],[n.output[0]],name=n.name)]
  repl[id(n)]=xs
 if count!=8:raise ValueError(f'expected 8 GQA got {count}')
 out=[]
 for n in m.graph.node:
  if id(n) in remove:continue
  out.extend(repl.get(id(n),[n]))
 del m.graph.node[:];m.graph.node.extend(out);ins=[v for v in m.graph.input if v.name!='seqlens_k'];del m.graph.input[:];m.graph.input.extend(ins);m.graph.input.append(helper.make_tensor_value_info('attention_mask',TensorProto.FLOAT,[1,1,sequence,capacity]))
 for v in m.graph.input:
  if v.name.startswith('past_key_values.') and v.name.endswith('.key'):setshape(v,[1,8,64,past])
  elif v.name.startswith('past_key_values.') and v.name.endswith('.value'):setshape(v,[1,8,past,64])
 for v in m.graph.output:
  if v.name.startswith('present.') and v.name.endswith('.key'):setshape(v,[1,8,64,sequence])
  elif v.name.startswith('present.') and v.name.endswith('.value'):setshape(v,[1,8,sequence,64])
 keep=[x for x in m.graph.initializer if x.name!='__max_sequence_length_i32'];del m.graph.initializer[:];m.graph.initializer.extend(keep);dst.parent.mkdir(parents=True,exist_ok=True);onnx.save(m,dst);onnx.checker.check_model(str(dst),full_check=False)
 return {'schema_version':1,'classification':'chunk_attention_standard_htp_lowering','sequence_length':sequence,'capacity':capacity,'past_cache_length':past,'gqa_nodes_lowered':count,'attention_mask_shape':[1,1,sequence,capacity],'new_k_shape':[1,8,64,sequence],'new_v_shape':[1,8,sequence,64],'caller_cache_update':f'write returned slices into left-aligned cache positions base:base+{sequence}','onnx_checker':'passed'}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('destination',type=Path);p.add_argument('--sequence-length',type=int,required=True);p.add_argument('--capacity',type=int,default=4096);a=p.parse_args();print(json.dumps(lower(a.source,a.destination,a.sequence_length,a.capacity),indent=2,sort_keys=True))
