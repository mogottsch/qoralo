#!/usr/bin/env python3
"""Offline QDQ metadata + five pinned saved output bundles. Never loads a model.

metadata: stdlib/zstd file reads only. observe: weights_only tensor deserialization
and NumPy arithmetic only; no export, compiler, native runtime or forward API.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import math
from pathlib import Path
import struct
import subprocess
import sys

EXP = Path(__file__).resolve().parents[1]
AUDIT = EXP/'results/conv-history-encoding-audit-20260910'
PAIR = EXP/'results/controlled-position1-paired-qnn-20260910'
PREFIX = EXP/'results/host-qnn-trajectory-prefix-000-003-20260910'
GRAPH_SHA = '2d879235c4d4a47643378e3ec3739bd587d4b0a68b23097b8ba64092ce20ad86'
Q = 'torch.ops.quantized_decomposed.quantize_per_tensor.default'
DQ = 'torch.ops.quantized_decomposed.dequantize_per_tensor.default'


def sha(data): return hashlib.sha256(data).hexdigest()
def read(path): return json.loads(Path(path).read_text())
def f32(x): return struct.unpack('<f', struct.pack('<f', x))[0]
def identity(path):
    p = Path(path); return {'path': str(p.absolute()), 'bytes': p.stat().st_size, 'sha256': sha(p.read_bytes())}
def save(root, name, obj):
    with (root/name).open('x') as out: json.dump(obj,out,indent=2,allow_nan=False);out.write('\n')


def retained(path):
    """Bind a retained file to its owning exact manifest, without native imports."""
    path = Path(path)
    root = next(p for p in path.parents if (p/'SHA256SUMS').is_file())
    entries = {n:h for h,n in (line.split('  ',1) for line in (root/'SHA256SUMS').read_text().splitlines())}
    data = path.read_bytes()
    if sha(data) != entries[str(path.relative_to(root))]: raise ValueError('Retained file changed: '+str(path))
    return data


def refs(value):
    if isinstance(value,dict):
        if 'as_tensor' in value: yield value['as_tensor']['name']
        elif 'as_tensors' in value:
            for tensor in value['as_tensors']: yield tensor['name']
        else:
            for item in value.values(): yield from refs(item)
    elif isinstance(value,list):
        for item in value: yield from refs(item)


def indexes(graph):
    owners = {}; users = {}
    for node in graph['nodes']:
        for output in node['outputs']:
            if 'as_tensor' in output: owners[output['as_tensor']['name']] = node
        for arg in node['inputs']:
            for name in set(refs(arg['arg'])): users.setdefault(name,[]).append((node,arg['name']))
    return owners,users


def snippet(node): return {k:node[k] for k in ('name','target','inputs','outputs')}


def encoding(node):
    if node['target'] not in (Q,DQ): return {'status':'absent','reason':'Not an explicit supported per-tensor Q/DQ node.','domain':None}
    fields = {}
    for arg in node['inputs']:
        for tag in ('as_float','as_int','as_scalar_type'):
            if tag in arg['arg']: fields[arg['name']] = arg['arg'][tag]
    required = {'scale','zero_point','quant_min','quant_max','dtype'}
    if not required <= set(fields): return {'status':'ambiguous','reason':'Dynamic/missing scalar encoding argument.','domain':None}
    scale,zero,low,high = (fields[k] for k in ('scale','zero_point','quant_min','quant_max'))
    if not math.isfinite(scale) or scale <= 0 or low >= high:
        return {'status':'ambiguous','reason':'Invalid/unsupported scalar domain.','domain':None}
    domain = {k:fields[k] for k in sorted(required)}
    domain.update(scale_f32le_hex=struct.pack('<f',scale).hex(),
                  decoded_min_fp32=f32((low-zero)*scale),decoded_max_fp32=f32((high-zero)*scale))
    return {'status':'explicit_per_tensor','reason':None,'domain':domain}


def first_tensor(node): return next(refs(node['inputs'][0]['arg']),None)


def input_boundary(name, owners, users):
    quantizers = []; other = []; shape = []
    for node,arg in users.get(name,[]):
        if node['target'] == 'torch.ops.aten.expand_as.default' and arg == 'other':
            shape.append({'node':node['name'],'argument':arg,'reason':'expand_as.other supplies shape, not state values.'})
        elif node['target'] == Q and arg == 'input':
            q = encoding(node); outputs = list(refs(node['outputs'])); branches = []
            for tensor in outputs:
                for dq,_ in users.get(tensor,[]):
                    if dq['target'] == DQ:
                        de = encoding(dq)
                        consumers = [{'node':c['name'],'target':c['target'],'argument':a}
                                     for o in refs(dq['outputs']) for c,a in users.get(o,[])]
                        branches.append({'dq_node':dq['name'],'encoding':de,'q_dq_domains_equal':q['domain']==de['domain'],
                                         'value_consumers':consumers,'source':snippet(dq)})
                    else:
                        branches.append({'dq_node':None,'encoding':{'status':'ambiguous','domain':None,'reason':'Quantized value used without direct DQ.'},'consumer':dq['name']})
            quantizers.append({'q_node':node['name'],'encoding':q,'branches':branches,'source':snippet(node)})
        else:
            other.append({'node':node['name'],'target':node['target'],'argument':arg,
                          'encoding':None,'reason':'Value-use not preceded by a direct per-tensor input Q; not guessed through arithmetic/plumbing.'})
    domains = [q['encoding']['domain'] for q in quantizers]
    unique = {json.dumps(d,sort_keys=True) for d in domains if d is not None}
    complete = bool(quantizers) and not other and all(q['encoding']['domain'] is not None and q['branches'] and
        all(b.get('q_dq_domains_equal',False) for b in q['branches']) for q in quantizers)
    status = 'unique' if complete and len(unique)==1 else ('per_consumer' if complete else 'ambiguous' if quantizers or other else 'absent')
    return {'status':status,'unique_domain':domains[0] if status=='unique' else None,
            'reason':None if complete else 'Missing/unresolved value-use or unequal Q/DQ domain; see individual consumers.',
            'quantizers':quantizers,'other_value_uses':other,'shape_only_uses':shape}


def output_boundary(name, owners, users):
    node = owners.get(name)
    if node is None or node['target'] != DQ:
        return {'status':'absent','domain':None,'reason':'Graph output is not a direct supported DQ.','source':None if node is None else snippet(node)}
    de = encoding(node); q = owners.get(first_tensor(node)); qe = None if q is None else encoding(q)
    matched = bool(qe and q['target']==Q and de['domain'] is not None and qe['domain']==de['domain'])
    producer = None if q is None else first_tensor(q)
    branches = []
    for consumer,arg in users.get(producer,[]):
        branches.append({'node':consumer['name'],'target':consumer['target'],'argument':arg,
                         'encoding':encoding(consumer), 'is_selected_output_quantizer':consumer is q})
    distinct = {json.dumps(b['encoding']['domain'],sort_keys=True) for b in branches if b['encoding']['domain'] is not None}
    return {'status':'explicit_paired' if matched else 'ambiguous','domain':de['domain'] if matched else None,
            'reason':None if matched else 'Missing/unequal output Q/DQ; no unique boundary asserted.',
            'q_node':None if q is None else q['name'],'dq_node':node['name'],'producer_tensor':producer,
            'producer_consumer_domains':branches,'producer_has_multiple_explicit_domains':len(distinct)>1,
            'source':{'q':None if q is None else snippet(q),'dq':snippet(node)}}


def compatibility(output_domain,input_domain):
    if output_domain is None or input_domain is None: return {'status':'unknown','reason':'Unresolved input/output domain.'}
    return {'status':'known_saved_qdq_domains',
        'decoded_output_interval_contained_in_input':output_domain['decoded_min_fp32']>=input_domain['decoded_min_fp32'] and output_domain['decoded_max_fp32']<=input_domain['decoded_max_fp32'],
        'lower_decoded_overhang':max(0.,input_domain['decoded_min_fp32']-output_domain['decoded_min_fp32']),
        'upper_decoded_overhang':max(0.,output_domain['decoded_max_fp32']-input_domain['decoded_max_fp32']),
        'same_encoding':all(output_domain[k]==input_domain[k] for k in ('scale','zero_point','quant_min','quant_max','dtype')),
        'code_clipping_note':'Decoded endpoints are not clipping onsets; exact code-grid simulation is separate.'}


def map_states(program, params):
    gm=program['graph_module']; graph=gm['graph']; owners,users=indexes(graph)
    inputs=[s['user_input']['arg']['as_tensor']['name'] for s in gm['signature']['input_specs'] if 'user_input' in s]
    if len(inputs)!=51 or len(graph['outputs'])!=73 or params['n_layers']!=24: raise ValueError('Wrong diagnostic/state ABI')
    if params['layer_types']!=['linear_attention','linear_attention','linear_attention','full_attention']*6:
        raise ValueError('Wrong pinned layer-type sequence')
    rows=[]
    for i in range(48):
        name=inputs[i+3];output=graph['outputs'][i+1]['as_tensor']['name']
        if name!=f'states_{i}':raise ValueError('Unexpected state order')
        layer=i%24;linear=params['layer_types'][layer]=='linear_attention'
        kind=('recurrent' if i<24 else 'convolution') if linear else ('key_cache_update' if i<24 else 'value_cache_update')
        inp=input_boundary(name,owners,users);out=output_boundary(output,owners,users)
        def shape(t):return [s['as_int'] for s in graph['tensor_values'][t]['sizes']]
        expected_shapes={'recurrent':([1,16,128,128],[1,16,128,128]),
            'convolution':([1,6144,1,4],[1,6144,1,4]),
            'key_cache_update':([1,2,256,4095],[1,2,256,1]),
            'value_cache_update':([1,2,4095,256],[1,2,1,256])}
        if (shape(name),shape(output))!=expected_shapes[kind]:raise ValueError('Wrong carry/update geometry')
        if graph['tensor_values'][name]['dtype']!=7 or graph['tensor_values'][output]['dtype']!=7:
            raise ValueError('Expected serialized logical FLOAT32 dtype7, not quantized integer carrier')
        rows.append({'state_index':i,'layer':layer,'kind':kind,'input_index':i+3,'output_index':i+1,
            'input_name':name,'output_name':output,'input_shape':shape(name),'output_shape':shape(output),
            'input_tensor_metadata':graph['tensor_values'][name],'output_tensor_metadata':graph['tensor_values'][output],
            'carry_transport':'clone_replace' if linear else 'write_new_token_at_position_axis_'+('3' if i<24 else '2'),
            'input':inp,'output':out,'theoretical_compatibility_per_quantizer':[
                {'q_node':q['q_node'],**compatibility(out['domain'],q['encoding']['domain'])} for q in inp['quantizers']],
            'native_finalized_encodings':None,'native_encoding_reason':'Saved QDQ metadata only, not native finalized/fused tensors or all48 native wrappers.'})
    return {'evidence_class':'saved_qdq_persistent_state_metadata','graph_nodes':len(graph['nodes']),'state_count':48,'states':rows,
            'graph_member_sha256':GRAPH_SHA,'no_weights_or_model_archive_reads':True,
            'scalar_carrier_note':'Graph scalar dtype4 is INT32 carrying codes0..65535, not W4 weight precision or native QNN datatype.'}


def metadata(root):
    compressed=retained(AUDIT/'raw/graph-model.json.zst')
    data=subprocess.run(['zstd','-d','-c'],input=compressed,stdout=subprocess.PIPE,check=True).stdout
    if len(data)!=32499235 or sha(data)!=GRAPH_SHA:raise ValueError('Graph member identity mismatch')
    params_raw=retained(PREFIX/'raw/params.json'); result=map_states(json.loads(data),json.loads(params_raw))
    result['sources']=[identity(AUDIT/'raw/graph-model.json.zst'),identity(PREFIX/'raw/params.json'),
                       identity(EXP/'tools/qwen35_qnn_model.py'),identity(EXP/'tools/replay_saved_qdq.py'),identity(__file__)]
    result['model_code_read_not_imported']=True
    save(root,'metadata.json',result)
    return {'state_count':48,'input_statuses':{k:sum(r['input']['status']==k for r in result['states']) for k in ('unique','per_consumer','ambiguous','absent')},
            'output_statuses':{k:sum(r['output']['status']==k for r in result['states']) for k in ('explicit_paired','ambiguous','absent')},
            'shape_only_uses':sum(len(r['input']['shape_only_uses']) for r in result['states']),
            'different_output_producer_consumer_domains':sum(r['output'].get('producer_has_multiple_explicit_domains',False) for r in result['states'])}


def roundtrip(array,domain):
    import numpy as np
    a=np.asarray(array,dtype=np.float32)
    scaled=np.multiply(a,np.float32(1.0/domain['scale']),dtype=np.float32)
    code=np.add(np.rint(scaled),np.float32(domain['zero_point']),dtype=np.float32)
    clipped=np.clip(code,domain['quant_min'],domain['quant_max'])
    decoded=np.multiply(np.subtract(clipped,np.float32(domain['zero_point']),dtype=np.float32),np.float32(domain['scale']),dtype=np.float32)
    return code,decoded


def coverage(array,domain):
    import numpy as np
    if domain is None:return {'status':'unknown','reason':'No resolved domain.'}
    a=np.asarray(array,dtype=np.float32).reshape(-1);finite=np.isfinite(a);f=a[finite]
    if not f.size:return {'status':'no_finite_values','reason':'No finite values to simulate.'}
    code,decoded=roundtrip(f,domain);mask=(code<domain['quant_min'])|(code>domain['quant_max']);indices=np.flatnonzero(finite)
    first=[]
    for j in np.flatnonzero(mask)[:8]:
        first.append({'flat_index':int(indices[j]),'input_fp32':float(f[j]),'unclamped_code':float(code[j]),'scalar_decoded_fp32':float(decoded[j])})
    return {'status':'simulated_fp32_qdq_on_saved_values','finite_values':int(f.size),
        'below_decoded_minimum':int(np.count_nonzero(f<domain['decoded_min_fp32'])),
        'above_decoded_maximum':int(np.count_nonzero(f>domain['decoded_max_fp32'])),
        'lower_code_clipped':int(np.count_nonzero(code<domain['quant_min'])),
        'upper_code_clipped':int(np.count_nonzero(code>domain['quant_max'])),
        'code_clipped_total':int(np.count_nonzero(mask)),
        'decoded_bit_changes':int(np.count_nonzero(f.view(np.uint32)!=decoded.view(np.uint32))),
        'max_abs_roundtrip_change_fp64':float(np.max(np.abs(f.astype(np.float64)-decoded.astype(np.float64)))),
        'first_clipped_examples':first}


def bundle_specs():
    header=json.loads(retained(PAIR/'raw/pack-header.json'))
    old=header['source_qdq_outputs']
    specs=[{'id':'qdq_p0','position':0,'route':'QDQ','state_origin':'initial_zero_states',
            'path':str(EXP/old['path']),'raw_bytes':old['bytes'],'raw_sha256':old['sha256'],'compressed':False}]
    pre=json.loads(retained(PREFIX/'compression-manifest.json'))['files']
    pair=json.loads(retained(PAIR/'compression-manifest.json'))['files']
    for name,position,route,origin,owner,record in [
        ('qnn_p0',0,'QNN','initial_zero_states',PREFIX,next(e for e in pre if e['kind']=='qnn_73_outputs' and e['position']==0)),
        ('qdq_p1_same_inputs',1,'QDQ','QDQ_p0_origin',PAIR,next(e for e in pair if e['kind']=='qdq_control_73')),
        ('qnn_p1_same_inputs',1,'QNN','QDQ_p0_origin',PAIR,next(e for e in pair if e['kind']=='qnn_control_73')),
        ('qnn_p1_own_state',1,'QNN','QNN_p0_origin',PAIR,next(e for e in pair if e['kind']=='own_qnn_73'))]:
        specs.append({'id':name,'position':position,'route':route,'state_origin':origin,'path':str(owner/record['compressed_path']),
            'raw_bytes':record['raw_bytes'],'raw_sha256':record['raw_sha256'],'compressed':True,
            'compressed_bytes':record['compressed_bytes'],'compressed_sha256':record['compressed_sha256']})
    return specs


def read_bundle_bytes(spec):
    path=Path(spec['path'])
    if spec['raw_bytes']>24*1024*1024 or path.stat().st_size>24*1024*1024:raise ValueError('Not a bounded saved output bundle')
    data=path.read_bytes()
    if spec['compressed']:
        if len(data)!=spec['compressed_bytes'] or sha(data)!=spec['compressed_sha256']:raise ValueError('Compressed bundle identity changed')
        data=subprocess.run(['zstd','-d','-c'],input=data,stdout=subprocess.PIPE,check=True).stdout
    if len(data)!=spec['raw_bytes'] or sha(data)!=spec['raw_sha256']:raise ValueError('Raw bundle identity changed')
    return data


def observe(metadata_path,root):
    import numpy as np
    import torch
    torch.set_num_threads(4)
    meta=read(metadata_path)
    if meta['graph_member_sha256']!=GRAPH_SHA or len(meta['states'])!=48:raise ValueError('Wrong state metadata')
    for source in meta['sources']:
        if identity(source['path'])!=source:raise ValueError('Audit source changed after metadata pass')
    states=meta['states'];status={'saved_tensor_loads':0,'model_loads':0,'model_forwards':0,'native_loads':0,'compile_calls':0,'completed':[]}
    try:
        specs=bundle_specs();save(root,'bundle-sources.json',specs)
        theory=[]
        for state in states:
            domain=state['output']['domain']
            if domain is None:theory.append({'state_index':state['state_index'],'status':'unknown'});continue
            codes=np.arange(domain['quant_min'],domain['quant_max']+1,dtype=np.float32)
            grid=np.multiply(codes-np.float32(domain['zero_point']),np.float32(domain['scale']),dtype=np.float32)
            theory.append({'state_index':state['state_index'],'output_grid_values':int(grid.size),
                'next_input_quantizers':[{'q_node':q['q_node'],'coverage':coverage(grid,q['encoding']['domain'])} for q in state['input']['quantizers']]})
        save(root,'theory-grid.json',theory)
        for spec in specs:
            data=read_bundle_bytes(spec)
            if spec['id']=='qdq_p0':
                compressed=subprocess.run(['zstd','-3','-T1','-c'],input=data,stdout=subprocess.PIPE,check=True).stdout
                (root/'qdq-p0.outputs.pt.zst').write_bytes(compressed)
                save(root,'qdq-p0-compression.json',{'raw_bytes':len(data),'raw_sha256':sha(data),'compressed_bytes':len(compressed),'compressed_sha256':sha(compressed)})
            status['saved_tensor_loads']+=1
            outputs=torch.load(io.BytesIO(data),map_location='cpu',weights_only=True)
            if not isinstance(outputs,(tuple,list)) or len(outputs)!=73 or not all(isinstance(x,torch.Tensor) for x in outputs):raise ValueError('Expected73 saved output tensors only')
            rows=[]
            for state in states:
                t=outputs[state['output_index']]
                if t.dtype!=torch.float32 or list(t.shape)!=state['output_shape']:raise ValueError('Saved output shape/dtype differs from graph')
                array=t.detach().contiguous().numpy().reshape(-1);finite=np.isfinite(array);v=array[finite];u=array.view(np.uint32)
                rows.append({'state_index':state['state_index'],'kind':state['kind'],'layer':state['layer'],'shape':list(t.shape),
                    'values':int(array.size),'finite_values':int(finite.sum()),'tensor_f32le_sha256':sha(array.tobytes()),
                    'min_fp32':float(v.min()) if v.size else None,'max_fp32':float(v.max()) if v.size else None,
                    'positive_zero_count':int(np.count_nonzero(u==0)),'negative_zero_count':int(np.count_nonzero(u==0x80000000)),
                    'own_output_domain':coverage(array,state['output']['domain']),
                    'next_input_quantizers':[{'q_node':q['q_node'],'coverage':coverage(array,q['encoding']['domain'])} for q in state['input']['quantizers']],
                    'scope':'Returned state/update values. Attention rows are new-token slices, not the entire4095-position cache; next-call QDQ is a simulation, not observed SDK clipping.'})
                row=rows[-1]
                row['carry_transport']=state['carry_transport']
                row['insert_position']=spec['position'] if 'cache_update' in state['kind'] else None
                row['hypothetical_next_call_position']=spec['position']+1
                for branch in row['next_input_quantizers']:
                    for example in branch['coverage'].get('first_clipped_examples',[]):
                        coordinate=[int(x) for x in np.unravel_index(example['flat_index'],state['output_shape'])]
                        mapped=list(coordinate)
                        if state['kind']=='key_cache_update':mapped[3]=spec['position']
                        if state['kind']=='value_cache_update':mapped[2]=spec['position']
                        example.update(output_coordinate=coordinate,next_input_coordinate=mapped)
            save(root,spec['id']+'.json',{'source':spec,'states':rows})
            status['completed'].append(spec['id'])
            del outputs,data,rows,t,array,v,u
        status.update(status='complete',numpy_version=np.__version__,torch_version=torch.__version__,math_threads=torch.get_num_threads(),
                      metadata_file=identity(metadata_path),audit_source=identity(__file__),
                      no_executorch_imports=not any(k.startswith('executorch') for k in sys.modules))
    except BaseException as error:
        status.update(status='error',error={'type':type(error).__name__,'message':str(error)});raise
    finally:save(root,'result.json',status)
    return status


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=('metadata','observe'))
    p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--metadata',type=Path)
    a=p.parse_args();a.output_dir.mkdir(parents=True,exist_ok=False)
    if a.mode=='metadata': result=metadata(a.output_dir)
    else:
        if a.metadata is None:p.error('--metadata required')
        result=observe(a.metadata,a.output_dir)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
