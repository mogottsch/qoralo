#!/usr/bin/env python3
"""Expose CPU embeddings, keep last-token logits, and shard LM head in one prefill graph."""
import argparse,copy,hashlib,json
from pathlib import Path
import numpy as np,onnx
from onnx import StringStringEntryProto,TensorProto,helper,numpy_helper
EMBED='/model/embed_tokens/GatherBlockQuantized/output_0';FINAL='/model/layers.30/final_norm_layernorm/output_0';VOCAB=128000;CHUNK=6144
def ext(t):
 d={x.key:x.value for x in t.external_data};return d['location'],int(d.get('offset','0')),int(d['length'])
def exttensor(src,name,dims,loc,off,length):
 t=TensorProto();t.name=name;t.data_type=src.data_type;t.dims.extend(dims);t.data_location=TensorProto.EXTERNAL;t.external_data.extend([StringStringEntryProto(key='location',value=loc),StringStringEntryProto(key='offset',value=str(off)),StringStringEntryProto(key='length',value=str(length))]);return t
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8<<20),b''):h.update(b)
 return h.hexdigest()
def build(src,dst,sequence):
 m=onnx.load(src,load_external_data=False);producers={y:n for n in m.graph.node for y in n.output};remove=set();stack=[EMBED]
 while stack:
  y=stack.pop();n=producers.get(y)
  if n is None or id(n) in remove:continue
  remove.add(id(n));stack.extend(n.input)
 logits=next(n for n in m.graph.node if n.op_type=='MatMulNBits' and 'logits' in n.output);remove.add(id(logits));init={x.name:x for x in m.graph.initializer};weight=init[logits.input[1]];scales=init[logits.input[2]];wl,wo,_=ext(weight);sl,so,_=ext(scales)
 starts='__prefill_last_starts';ends='__prefill_last_ends';axes='__prefill_last_axes';steps='__prefill_last_steps';last='__prefill_last_hidden'
 added=[numpy_helper.from_array(np.asarray([sequence-1],dtype=np.int64),starts),numpy_helper.from_array(np.asarray([sequence],dtype=np.int64),ends),numpy_helper.from_array(np.asarray([1],dtype=np.int64),axes),numpy_helper.from_array(np.asarray([1],dtype=np.int64),steps)];nodes=[n for n in m.graph.node if id(n) not in remove];nodes.append(helper.make_node('Slice',[FINAL,starts,ends,axes,steps],[last],name='/lm_head/prefill_last_token'))
 outputs=[];cursor=0;chunk=0;head_inits=[]
 while cursor<VOCAB:
  rem=VOCAB-cursor;width=4096 if rem==5120 else min(CHUNK,rem);wb=width*64*16;sb=width*64*4;wn=f'{weight.name}_vocab_{cursor}_{cursor+width}';sn=f'{scales.name}_vocab_{cursor}_{cursor+width}';out=f'logits_vocab_{cursor}_{cursor+width}';nodes.append(helper.make_node('MatMulNBits',[last,wn,sn],[out],name=f'/lm_head/chunk_{chunk}',domain='com.microsoft',K=2048,N=width,bits=4,block_size=32,accuracy_level=4));head_inits += [exttensor(weight,wn,[width,64,16],wl,wo,wb),exttensor(scales,sn,[width,64],sl,so,sb)];outputs.append(helper.make_tensor_value_info(out,TensorProto.FLOAT,[1,1,width]));wo+=wb;so+=sb;cursor+=width;chunk+=1
 used={x for n in nodes for x in n.input};kept=[x for x in m.graph.initializer if x.name in used and x.name not in {weight.name,scales.name,logits.input[3]}];kept+=added+head_inits;state_outputs=[copy.deepcopy(x) for x in m.graph.output if x.name.startswith('present')];ins=[copy.deepcopy(x) for x in m.graph.input if x.name!='input_ids'];ins.insert(0,helper.make_tensor_value_info(EMBED,TensorProto.FLOAT,[1,sequence,2048]));g=helper.make_graph(nodes,'lfm2_chunk_prefill_monolith',ins,state_outputs+outputs,kept,value_info=[copy.deepcopy(x) for x in m.graph.value_info]);out=helper.make_model(g,ir_version=m.ir_version,opset_imports=[copy.deepcopy(x) for x in m.opset_import],producer_name='0034-build-prefill-monolith');dst.parent.mkdir(parents=True,exist_ok=True);onnx.save(out,dst);onnx.checker.check_model(str(dst),full_check=False)
 return {'schema_version':1,'classification':'ordinary_chunk_prefill_monolith','source':str(src),'source_sha256':sha(src),'destination':str(dst),'destination_sha256':sha(dst),'sequence_length':sequence,'node_count':len(nodes),'initializer_count':len(kept),'input_count':len(ins),'state_output_count':len(state_outputs),'logit_chunk_count':len(outputs),'embedding_boundary':'CPU selected-row Q4 dequantization for each chunk token','head_behavior':'Only final chunk position enters 22 symmetric Q4 LM-head chunks; CPU global argmax','shared_resource_format':False,'context_streaming':False,'onnx_checker':'passed'}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('destination',type=Path);p.add_argument('--sequence-length',type=int,required=True);a=p.parse_args();print(json.dumps(build(a.source,a.destination,a.sequence_length),indent=2,sort_keys=True))
