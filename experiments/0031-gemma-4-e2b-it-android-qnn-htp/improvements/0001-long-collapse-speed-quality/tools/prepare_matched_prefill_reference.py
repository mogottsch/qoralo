#!/usr/bin/env python3
"""Extract a pinned final-DLC declared-policy reference; never execute graph ops."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil
import time

TRACK=Path(__file__).resolve().parents[1]
ROOT=TRACK/'.local/matched-prefill-reference'
DLC=TRACK/'.local/value-precision-full-runs/full-ar128-20260911T103001Z-01/work/dlc-cache/b9b886d49ec5e87b214da9d73cacb41ab87dea8ddf950137aaa9eca9caec4643/ar128_cl4096_1_of_1.dlc'
DLC_SHA='d9eec6585153928e2f9f2351854849abc458de42d5426788bd22b760d2633052'
CONTEXT_SHA='27e19e32ef479dfb39b53e6530cd25105c3c8e9ccf9fa4b9e9af4b5d770fabdd'


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(4*1024*1024),b''):h.update(block)
    return h.hexdigest()


def extract(output):
    import numpy as np
    from qti.aisw.dlc_utils import modeltools
    from qti.aisw.converters.common import ir_graph as ir
    from qti.aisw.dlc_utils.snpe_dlc_utils import is_scale_offset_encoding,is_axis_scale_offset_encoding
    output.mkdir(parents=True,exist_ok=False);(output/'static').mkdir();start=time.monotonic()
    if sha(DLC)!=DLC_SHA:raise ValueError('chosen final DLC identity changed')
    reader=modeltools.IrDlcReader();reader.open(str(DLC));names=sorted(reader.get_ir_graph_names())
    if len(names)!=1:raise ValueError('unexpected DLC graph count')
    graph=reader.get_ir_graph(names[0]);tensors={};operators=[];total=0
    def attrs(op):
        result={}
        for name in op.attrs.list_names():
            if op.attrs.get_attr_type(name)==ir.QNN_PARAMTYPE_TENSOR:
                data=op.attrs.get_static_tensor_data(name)
                if data.size>4096:raise ValueError('large unresolved op attribute '+name)
                result[name]=data.tolist();continue
            dt=op.attrs.get_data_type(name);method=None
            for kind in ['INT_8','INT_16','INT_32','INT_64','UINT_8','UINT_16','UINT_32','UINT_64','FLOAT_16','FLOAT_32','BOOL_8','STRING','UNDEFINED']:
                if dt==getattr(ir,'QNN_DATATYPE_'+kind):
                    method='get_'+({'FLOAT_16':'float','FLOAT_32':'float','BOOL_8':'bool','STRING':'string','UNDEFINED':'string'}.get(kind,kind.lower().replace('_','')));break
            if method is None:raise ValueError('unhandled scalar attribute '+name+' '+str(dt))
            result[name]=getattr(op.attrs,method)(name)
        return result
    def register(t):
        nonlocal total
        name=t.name()
        if name in tensors:return
        item={'name':name,'dimensions':t.dims(),'datatype':t.data_type_string(),'tensor_type':t.tensor_type(),'id':int(t.id())}
        e=t.get_encoding();item['encoding_kind']=str(e.type)
        if 'Fxp_' in item['datatype']:
            if is_scale_offset_encoding(e.type):infos=[e.encInfo];axis=None
            elif is_axis_scale_offset_encoding(e.type):infos=list(e.axisEncInfo.encInfos);axis=int(e.axisEncInfo.axis)
            else:raise ValueError('unexpressed quantization '+name+' '+str(e.type))
            item['grid']={'axis':axis,'bitwidths':[int(v.bw) for v in infos],'scale':[float(v.scale) for v in infos],'offset':[int(v.offset) for v in infos],'min':[float(v.min) for v in infos],'max':[float(v.max) for v in infos]}
        elif item['datatype'] not in ['Float_16','Float_32','Int_32','UInt_32','Int_64','UInt_64','Int_8','UInt_8','Int_16','UInt_16','Bool_8']:
            raise ValueError('unexpressed datatype '+item['datatype'])
        if t.is_static_tensor():
            data=graph.get_static_tensor(name).get_data()
            total+=data.nbytes
            if total>4*1024**3 or shutil.disk_usage(output).free<64*1024**3:raise RuntimeError('static scratch budget')
            path=output/'static'/f'{len(tensors):05d}.npy';np.save(path,data,allow_pickle=False)
            item['static']={'file':str(path.relative_to(output)),'npy_sha256':sha(path),'dtype':str(data.dtype),'dimensions':list(data.shape),'raw_bytes':int(data.nbytes)}
            del data
        tensors[name]=item
    for index,op in enumerate(graph.get_ops()):
        for t in op.inputs()+op.outputs():register(t)
        operators.append({'index':index,'name':op.name,'type':op.type,'inputs':[t.name() for t in op.inputs()],'outputs':[t.name() for t in op.outputs()],'attrs':attrs(op)})
        if index%100==0:(output/'progress.json').write_text(json.dumps({'ops':index+1,'static_bytes':total,'seconds':time.monotonic()-start})+'\n')
        if time.monotonic()-start>250:raise TimeoutError('bounded final-policy extraction')
    policy={'classification':'actual_final_DLC_declared_policy','dlc_path':str(DLC),'dlc_sha256':DLC_SHA,'compiled_context_sha256':CONTEXT_SHA,'graph_name':names[0],'tensors':tensors,'operators':operators,'input_names':[t.name() for t in graph.get_input_tensors_to_graph()],'output_names':[name for name,t in tensors.items() if t['tensor_type']=='APP_READ'],
      'reference_arithmetic':'float32 logical operator evaluation followed by each actual declared output grid; explicit Float16 boundaries round to binary16; static weights use actual DLC stored codes, not original sidecar re-quantization.',
      'rounding_boundary':'Reference uses nearest-ties-to-even and clipping for integer grids. DSP rounding/fusion/accumulation/transcendentals not claimed bit-exact.',
      'neural_forward_calls':0,'SDK_source_or_model_modified':False,'static_bytes':total}
    path=output/'policy.json';path.write_text(json.dumps(policy,separators=(',',':'))+'\n')
    summary={'dlc_sha256':DLC_SHA,'compiled_context_sha256':CONTEXT_SHA,'policy_sha256':sha(path),'operators':dict(Counter(o['type'] for o in operators)),'op_count':len(operators),'tensor_count':len(tensors),'static_bytes':total,'static_count':sum('static' in t for t in tensors.values()),'input_count':len(policy['input_names']),'output_count':len(policy['output_names']),'dtype_counts':dict(Counter(t['datatype'] for t in tensors.values())),'seconds':time.monotonic()-start,'neural_forward_calls':0}
    (output/'result.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args();out=a.output_dir.resolve()
    if not out.is_relative_to(ROOT):p.error('owned fresh private output required')
    extract(out)


if __name__=='__main__':main()
