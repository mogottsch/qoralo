import json,time
from pathlib import Path
from qti.aisw.dlc_utils import modeltools
from qti.aisw.converters.common import ir_graph as ir
ROOT=Path(__file__).resolve().parent
DLC=ROOT.parents[2]/'value-precision-full-runs/full-ar128-20260911T103001Z-01/work/dlc-cache/b9b886d49ec5e87b214da9d73cacb41ab87dea8ddf950137aaa9eca9caec4643/ar128_cl4096_1_of_1.dlc'
# ROOT is .local/matched-prefill-reference/dlc-probe-01
DLC=ROOT.parent.parent/'value-precision-full-runs/full-ar128-20260911T103001Z-01/work/dlc-cache/b9b886d49ec5e87b214da9d73cacb41ab87dea8ddf950137aaa9eca9caec4643/ar128_cl4096_1_of_1.dlc'
r=modeltools.IrDlcReader();r.open(str(DLC));names=sorted(r.get_ir_graph_names());g=r.get_ir_graph(names[0]);seen={};encs={};sample=None
for op in g.get_ops():
 if op.type not in seen:
  attrs={}
  for name in op.attrs.list_names():
   typ=op.attrs.get_attr_type(name);dt=op.attrs.get_data_type(name)
   if typ==ir.QNN_PARAMTYPE_TENSOR:
    v=op.attrs.get_static_tensor_data(name);attrs[name]={'shape':list(v.shape),'dtype':str(v.dtype),'values':v.tolist() if v.size<=64 else None};continue
   fn=None
   for k,method in [('INT_8','get_int8'),('INT_16','get_int16'),('INT_32','get_int32'),('INT_64','get_int64'),('UINT_8','get_uint8'),('UINT_16','get_uint16'),('UINT_32','get_uint32'),('UINT_64','get_uint64'),('FLOAT_16','get_float'),('FLOAT_32','get_float'),('BOOL_8','get_bool'),('STRING','get_string')]:
    if dt==getattr(ir,'QNN_DATATYPE_'+k):fn=method;break
   attrs[name]={'type':str(dt),'value':getattr(op.attrs,fn)(name) if fn else None}
  seen[op.type]={'name':op.name,'attrs':attrs,'inputs':[{'name':t.name(),'dims':t.dims(),'type':t.data_type_string()} for t in op.inputs()],'outputs':[{'name':t.name(),'dims':t.dims(),'type':t.data_type_string()} for t in op.outputs()]}
 for t in op.inputs()+op.outputs():
  e=t.get_encoding();encs[str(e.type)]=encs.get(str(e.type),0)+1
  if sample is None and t.is_static_tensor() and 'weight' in t.name():
   data=g.get_static_tensor(t.name()).get_data();sample={'name':t.name(),'dims':t.dims(),'declared':t.data_type_string(),'numpy_dtype':str(data.dtype),'shape':list(data.shape),'bytes':data.nbytes,'min_code':int(data.min()),'max_code':int(data.max()),'encoding_type':str(e.type),'encoding_dir':[x for x in dir(e) if not x.startswith('_')]}
  if sample is not None and len(seen)==15:break
x={'graphs':names,'op_types':seen,'encoding_types':encs,'one_static_data_metadata':sample,'ir_constants':{n:int(getattr(ir,n)) for n in dir(ir) if n.startswith(('QNN_OP_ELEMENT_WISE_BINARY_OPERATION','QNN_OP_ELEMENT_WISE_NEURON_OPERATION','QNN_OP_REDUCE_OPERATION'))},'neural_forward_calls':0};(ROOT/'result.json').write_text(json.dumps(x,indent=2)+'\n');print(json.dumps(x,indent=2))
