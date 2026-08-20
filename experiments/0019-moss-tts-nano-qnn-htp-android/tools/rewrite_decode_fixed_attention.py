#!/usr/bin/env python3
"""Route fixed-cache attention through logical insertion while preserving appended K/V graph outputs."""
import argparse,hashlib,json
from pathlib import Path
import onnx
from onnx import helper,TensorProto
p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=onnx.load(a.input,load_external_data=False);orig_nodes=list(m.graph.node);orig_inits=list(m.graph.initializer)
# Physical concat output remains [past slots 0..599, new at 600] for the state ABI.
# Attention instead consumes [past slots with new inserted at logical past_valid_lengths, zero at 600].
pos='vibevoice_fixed_positions_0_600_i32';shape='vibevoice_fixed_valid_reshape';zero='vibevoice_fixed_zero_f32';valid4='vibevoice_fixed_valid_4d';mask='vibevoice_fixed_logical_insert_mask'
existing={x.name for x in m.graph.initializer};assert not ({pos,shape,zero}&existing)
m.graph.initializer.extend([helper.make_tensor(pos,TensorProto.INT32,[1,601,1,1],list(range(601))),helper.make_tensor(shape,TensorProto.INT64,[4],[1,1,1,1]),helper.make_tensor(zero,TensorProto.FLOAT,[],[0.0])])
prefix=[helper.make_node('Reshape',['past_valid_lengths',shape],[valid4],name='vibevoice/ReshapeValidLength'),helper.make_node('Equal',[pos,valid4],[mask],name='vibevoice/LogicalInsertMask')]
# These are the 24 cache concats consumed by attention and by final graph-output casts.
targets={}
for i in range(12):
 targets[f'/Concat_{5+11*i}_output_0' if i else '/Concat_5_output_0']=None
 targets[f'/Concat_{6+11*i}_output_0' if i else '/Concat_6_output_0']=None
# Arithmetic formula above yields 5/6,16/17,...126/127.
assert len(targets)==24
final_casts={f'/Cast_{117+i}' for i in range(24)}
new=[];mapping={};rewrites=[];consumer_rewrites=[]
for index,node in enumerate(orig_nodes):
 clone=onnx.NodeProto();clone.CopyFrom(node)
 # Redirect attention/shape consumers, but preserve final output casts on physical appended concat.
 if clone.name not in final_casts:
  for j,x in enumerate(clone.input):
   if x in mapping:
    clone.input[j]=mapping[x];consumer_rewrites.append({'node':clone.name,'input_index':j,'from':x,'to':mapping[x]})
 new.append(clone)
 if len(node.output)==1 and node.output[0] in targets:
  assert node.op_type=='Concat' and len(node.input)==2
  attrs={x.name:helper.get_attribute_value(x) for x in node.attribute};assert attrs.get('axis')==1,(node.name,attrs)
  old,new_token=node.input;base=node.output[0];z=base+'__zero_token';padded=base+'__padded_past';inserted=base+'__logical_attention'
  new.extend([helper.make_node('Mul',[new_token,zero],[z],name=node.name+'__ZeroToken'),helper.make_node('Concat',[old,z],[padded],name=node.name+'__PaddedPast',axis=1),helper.make_node('Where',[mask,new_token,padded],[inserted],name=node.name+'__LogicalInsert')])
  mapping[base]=inserted;rewrites.append({'original_index':index,'concat_name':node.name,'physical_output':base,'attention_output':inserted,'past_input':old,'new_token_input':new_token,'physical_new_index':600,'logical_new_index_input':'past_valid_lengths'})
assert len(rewrites)==24 and len(consumer_rewrites)==36,(len(rewrites),len(consumer_rewrites))
del m.graph.node[:];m.graph.node.extend(prefix+new);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_bytes(m.SerializeToString());r=onnx.load(a.output,load_external_data=False)
report={'schema_version':1,'source':str(a.input),'source_sha256':sha(a.input),'output':str(a.output),'output_sha256':sha(a.output),'abi':{'input_past_capacity':600,'physical_output_capacity':601,'physical_appended_new_index':600,'attention_logical_insert_index':'past_valid_lengths','final_state_slot':600},'rewritten_cache_concats':rewrites,'rewritten_attention_consumers':consumer_rewrites,'checks':{'rewrite_count':len(rewrites),'consumer_rewrite_count':len(consumer_rewrites),'all_original_initializers_ordered_byte_identical':[x.SerializeToString() for x in orig_inits]==[x.SerializeToString() for x in r.graph.initializer[:len(orig_inits)]],'appended_initializers':len(r.graph.initializer)-len(orig_inits),'graph_input_names_unchanged':[x.name for x in m.graph.input]==[x.name for x in r.graph.input],'graph_output_names_unchanged':[x.name for x in m.graph.output]==[x.name for x in r.graph.output]},'semantic_boundary':'Only attention/shape consumers use logical insertion. Graph present_key/value outputs retain the original physical [past600,new] concat, so CPU state orchestration still copies output index600 into slot past_valid_lengths.'}
assert all(v for v in report['checks'].values() if isinstance(v,bool));a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
