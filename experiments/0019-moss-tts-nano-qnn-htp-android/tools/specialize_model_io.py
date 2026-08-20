#!/usr/bin/env python3
"""Set only declared ONNX graph I/O shape metadata for one MOSS concrete call."""
import argparse,json,hashlib
from pathlib import Path
import onnx
p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--shapes',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
def sha(x):return hashlib.sha256(x.read_bytes()).hexdigest()
m=onnx.load(a.input,load_external_data=False);before=m.SerializeToString();spec=json.load(open(a.shapes))
values={x.name:x for x in list(m.graph.input)+list(m.graph.output)}
assert set(spec)==set(values),(set(spec)-set(values),set(values)-set(spec))
for name,dims in spec.items():
 shape=values[name].type.tensor_type.shape
 del shape.dim[:]
 for value in dims:shape.dim.add().dim_value=int(value)
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_bytes(m.SerializeToString())
r=onnx.load(a.output,load_external_data=False)
def proto_map(model):return {x.name:x.SerializeToString() for x in list(model.graph.input)+list(model.graph.output)}
orig=onnx.load(a.input,load_external_data=False)
report={
 'schema_version':1,'source':str(a.input),'source_sha256':sha(a.input),'output':str(a.output),'output_sha256':sha(a.output),
 'shapes':spec,'checks':{
  'ordered_nodes_byte_identical':[x.SerializeToString() for x in orig.graph.node]==[x.SerializeToString() for x in r.graph.node],
  'ordered_initializers_byte_identical':[x.SerializeToString() for x in orig.graph.initializer]==[x.SerializeToString() for x in r.graph.initializer],
  'node_count':len(r.graph.node),'initializer_count':len(r.graph.initializer),
  'input_names_identical':[x.name for x in orig.graph.input]==[x.name for x in r.graph.input],
  'output_names_identical':[x.name for x in orig.graph.output]==[x.name for x in r.graph.output],
 },
 'external_data_references':sorted({entry.value for x in r.graph.initializer for entry in x.external_data if entry.key=='location'}),
}
assert all(v for k,v in report['checks'].items() if isinstance(v,bool))
a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
