#!/usr/bin/env python3
"""Apply only provenance-gated algebraic rewrites for observed MOSS QNN blockers."""
import argparse,hashlib,json
from pathlib import Path
import onnx
from onnx import helper,TensorProto
p=argparse.ArgumentParser();p.add_argument('--kind',choices=['prefill','decode','codec'],required=True);p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
def sha(x):return hashlib.sha256(x.read_bytes()).hexdigest()
m=onnx.load(a.input,load_external_data=False);orig_nodes=list(m.graph.node);orig_inits=list(m.graph.initializer);new=[];rewrites=[]
axes_name='vibevoice_qnn_einsum_unsqueeze_axes'
if a.kind in {'prefill','decode'}:
 assert all(x.name!=axes_name for x in orig_inits)
 m.graph.initializer.append(helper.make_tensor(axes_name,TensorProto.INT64,[1],[2]))
for index,node in enumerate(orig_nodes):
 if node.op_type=='Einsum':
  attrs={x.name:helper.get_attribute_value(x) for x in node.attribute}
  assert attrs=={'equation':b'bs,d->bsd'},(node.name,attrs)
  temp=node.output[0]+'__unsqueezed_for_qnn'
  new.extend([helper.make_node('Unsqueeze',[node.input[0],axes_name],[temp],name=node.name+'__Unsqueeze'),helper.make_node('Mul',[temp,node.input[1]],list(node.output),name=node.name+'__Mul')])
  rewrites.append({'original_index':index,'name':node.name,'op_type':'Einsum','equation':'bs,d->bsd','replacement':['Unsqueeze(axis=2)','Mul with [d] broadcast']})
 elif a.kind=='prefill' and node.name=='/Slice':
  assert node.op_type=='Slice' and list(node.input)==['/Cast_18_output_0','/Unsqueeze_16_output_0','/Constant_52_output_0','/Constant_50_output_0','/Constant_53_output_0']
  new.append(helper.make_node('Identity',[node.input[0]],list(node.output),name=node.name+'__Identity'))
  rewrites.append({'original_index':index,'name':node.name,'op_type':'Slice','replacement':['Identity'],'proof_contract':'For fixed attention_mask [1,226], original axis-1 slice is [-226:INT64_MAX:1], exactly the full tensor.'})
 elif a.kind=='codec' and node.name=='/Xor':
  assert node.op_type=='Xor' and len(node.input)==2 and len(node.output)==1
  base=node.output[0]
  nota,notb,left,right=[base+x for x in ['__not_a','__not_b','__a_and_not_b','__not_a_and_b']]
  new.extend([
   helper.make_node('Not',[node.input[0]],[nota],name=node.name+'__NotA'),
   helper.make_node('Not',[node.input[1]],[notb],name=node.name+'__NotB'),
   helper.make_node('And',[node.input[0],notb],[left],name=node.name+'__AndLeft'),
   helper.make_node('And',[nota,node.input[1]],[right],name=node.name+'__AndRight'),
   helper.make_node('Or',[left,right],list(node.output),name=node.name+'__Or')])
  rewrites.append({'original_index':index,'name':node.name,'op_type':'Xor','replacement':['Not(a)','Not(b)','And(a,Not(b))','And(Not(a),b)','Or'],'proof':'Canonical Boolean exclusive-or expansion.'})
 else:new.append(node)
expected={'prefill':13,'decode':12,'codec':1}[a.kind];assert len(rewrites)==expected,(len(rewrites),expected)
del m.graph.node[:];m.graph.node.extend(new);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_bytes(m.SerializeToString())
r=onnx.load(a.output,load_external_data=False)
targets={x['original_index'] for x in rewrites}
report={'schema_version':1,'kind':a.kind,'source':str(a.input),'source_sha256':sha(a.input),'output':str(a.output),'output_sha256':sha(a.output),'rewrites':rewrites,
 'checks':{'expected_rewrite_count':expected,'actual_rewrite_count':len(rewrites),'all_original_initializers_ordered_byte_identical':[x.SerializeToString() for x in orig_inits]==[x.SerializeToString() for x in r.graph.initializer[:len(orig_inits)]],'appended_initializers':len(r.graph.initializer)-len(orig_inits),'untargeted_original_nodes_ordered_byte_identical':[x.SerializeToString() for i,x in enumerate(orig_nodes) if i not in targets]==[x.SerializeToString() for x in r.graph.node if not any(x.name.startswith(t['name']+'__') for t in rewrites)]}}
assert all(v for v in report['checks'].values() if isinstance(v,bool));a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
