#!/usr/bin/env python3
"""Bounded SAVED/STATIC audit. No neural graph, operator replay, phone or repair."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import time

import numpy as np

TRACK=Path(__file__).resolve().parents[1]
EXP=TRACK.parents[1]
POLICY=TRACK/'.local/matched-prefill-reference/policy-01/policy.json'
POLICY_SHA='7fffebe9208bc5e2b92d80ed6ed01b7b57263e8f23d188188588682754c18b59'
FLOAT_GRAPH=EXP/'.local/checkpoint/extracted/gemma_4_e2b_it_w4a16/model_dynamic.onnx'
GRAPH_SHA='51d4e8183a6734a8c7bbd24ebc072768f080e54b011725ae645dfa32498bf0d0'
FLOAT_DATA=FLOAT_GRAPH.parent/'model.data'
DATA_SHA='e156c33d176273555003039959ecb0ae0ddc8a328eceeec1e8f4a6255840e072'
HEAD_REGION_SHA='eb7ac2b168bd4446daba2aabf0df0d3a0f7b25dfea5afbcffad375e61e4146fc'
HEADER=Path('/home/moritz/opt/qairt/2.49.40.260810/include/QNN/QnnTypes.h')
WEIGHTS=['model.lm_head.weight','model.model.layers.0.self_attn.q_proj_sha.0.weight','val_42']


def sha(path,offset=0,length=None):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        f.seek(offset)
        while length is None or length>0:
            block=f.read(4*1024*1024 if length is None else min(length,4*1024*1024))
            if not block:break
            h.update(block)
            if length is not None:length-=len(block)
    if length not in (None,0):raise ValueError('short region read')
    return h.hexdigest()


def signed_low_bits(values,bits):
    q=np.asarray(values,dtype=np.int32)&((1<<bits)-1)
    return np.where(q>=(1<<(bits-1)),q-(1<<bits),q)


def metrics(candidate,source,scales):
    delta=candidate.astype(np.float64)-source.astype(np.float64);a=np.abs(delta)
    steps=a/scales.astype(np.float64);norm=float(np.linalg.norm(candidate.astype(np.float64))*np.linalg.norm(source.astype(np.float64)))
    return {'values':int(source.size),'mean_absolute_error':float(a.mean()),'max_absolute_error':float(a.max()),'RMSE':float(np.sqrt(np.mean(delta**2))),'cosine_to_known_float_weights':float(np.sum(candidate.astype(np.float64)*source.astype(np.float64))/norm) if norm else None,'within_half_scale_fraction':float(np.mean(steps<=.5001)),'max_error_scale_units':float(steps.max()),'nonzero_sign_disagreements':int(np.count_nonzero((source!=0)&(candidate!=0)&(np.signbit(source)!=np.signbit(candidate)))),'known_zero_values':int(np.count_nonzero(source==0)),'known_zero_nonzero_decodes':int(np.count_nonzero((source==0)&(candidate!=0)))}


def audit(out):
    import onnx
    started=time.monotonic();out.mkdir(parents=True,exist_ok=False)
    if sha(POLICY)!=POLICY_SHA or sha(FLOAT_GRAPH)!=GRAPH_SHA or sha(FLOAT_DATA)!=DATA_SHA:raise ValueError('frozen policy or known float export changed')
    (out/'source-verification.json').write_text(json.dumps({'policy_sha256':POLICY_SHA,'float_graph_sha256':GRAPH_SHA,'float_data_sha256':DATA_SHA,'seconds':time.monotonic()-started,'model_or_operator_forward_calls':0},indent=2)+'\n')
    policy=json.loads(POLICY.read_text());graph=onnx.load(str(FLOAT_GRAPH),load_external_data=False);initializers={t.name:t for t in graph.graph.initializer}
    header=HEADER.read_text();required=["all bits above the specified bitwidth will be ignored","signed bit is the most","0b00001101"]
    if not all(text in header for text in required):raise ValueError('expected documented BW storage contract missing')
    groups=Counter()
    for tensor in policy['tensors'].values():
        if tensor['datatype']=='sFxp_8' and 'static' in tensor:
            g=tensor['grid'];groups[(tensor['encoding_kind'],tuple(sorted(set(g['bitwidths']))),tuple(sorted(set(g['offset']))))]+=1
    result={'classification':'saved_static_reference_contract_audit','model_or_operator_forward_calls':0,'phone_calls':0,'reference_implementation_changed':False,'policy_sha256':POLICY_SHA,'known_float_graph_sha256':GRAPH_SHA,'known_float_data_sha256':DATA_SHA,'storage_contract':{'header_path':str(HEADER),'header_sha256':sha(HEADER),'line_ranges':[[529,563],[593,631]],'documented_rule':'For BW scale-offset and BW per-axis encodings, use low specified bits; ignore upper container bits; signed bit is the most significant effective bit (example0x0d and0xfd bothmean-3 atBW4).','actual_signed_static_encoding_groups':[{'encoding':k[0],'bits':list(k[1]),'offsets':list(k[2]),'tensors':n} for k,n in groups.items()]},'weights':[]}
    for name in WEIGHTS:
        t=policy['tensors'][name];g=t['grid'];init=initializers[name];ext={v.key:v.value for v in init.external_data};dims=list(init.dims);offset=int(ext['offset']);length=int(ext['length'])
        if ext['location']!='model.data' or init.data_type!=onnx.TensorProto.FLOAT or length!=int(np.prod(dims))*4:raise ValueError('known external float weight contract mismatch')
        known=np.memmap(FLOAT_DATA,dtype='<f4',mode='r',offset=offset,shape=tuple(dims));raw_path=POLICY.parent/t['static']['file']
        if sha(raw_path)!=t['static']['npy_sha256']:raise ValueError('actual DLC static codes changed')
        raw=np.load(raw_path,mmap_mode='r',allow_pickle=False)
        if len(dims)==4 and dims[2:]==[1,1]:
            known_matrix=known[:,:,0,0];code_matrix=raw[0,0].T;expected_axis=3;layout='OIHW float -> HWIO DLC; canonical comparison rows=output channels'
        elif name=='val_42':
            known_matrix=known.T;code_matrix=raw;expected_axis=0;layout='known val_42 transpose -> FullyConnected OI rows'
        else:raise ValueError('unreviewed static layout')
        if list(raw.shape)!=t['dimensions'] or code_matrix.shape!=known_matrix.shape or g['axis']!=expected_axis or set(g['bitwidths'])!={4} or set(g['offset'])!={0}:raise ValueError('static shape/axis/BW/offset mismatch')
        rows=np.unique(np.linspace(0,known_matrix.shape[0]-1,min(1024,known_matrix.shape[0]),dtype=np.int64))
        source=np.asarray(known_matrix[rows],dtype=np.float32);codes=np.asarray(code_matrix[rows],dtype=np.int8)
        scales=np.asarray(g['scale'],dtype=np.float32)[rows,None];offsets=np.asarray(g['offset'],dtype=np.float32)[rows,None]
        interpretations={'documented_signed_BW4':signed_low_bits(codes,4),'signed_int8_container_without_BW_interpretation':codes.astype(np.int32),'diagnostic_unsigned_nibble_minus8':(codes.astype(np.int32)&15)-8}
        candidates={key:metrics((q.astype(np.float32)+offsets)*scales,source,scales) for key,q in interpretations.items()}
        predicted=np.clip(np.rint(source/scales-offsets),-8,7).astype(np.int32);doc=interpretations['documented_signed_BW4']
        region_sha=sha(FLOAT_DATA,offset,length)
        if name=='model.lm_head.weight' and region_sha!=HEAD_REGION_SHA:raise ValueError('previously proven float head region changed')
        result['weights'].append({'name':name,'encoding':t['encoding_kind'],'IR_datatype':t['datatype'],'container_dtype':str(raw.dtype),'IR_dimensions':t['dimensions'],'known_float_dimensions':dims,'channel_axis':g['axis'],'bitwidth':4,'offsets':[0],'layout':layout,'sampled_output_channels':len(rows),'sampled_values':int(source.size),'code_histogram':[int(np.count_nonzero(codes==v)) for v in range(16)],'raw_npy_sha256':sha(raw_path),'float_region':{'offset':offset,'bytes':length,'sha256':region_sha},'min_scale_units':float(g['min'][0]/g['scale'][0]),'max_scale_units':float(g['max'][0]/g['scale'][0]),'source_values_outside_signed_grid':int(np.count_nonzero((source/scales-offsets < -8)|(source/scales-offsets > 7))),'documented_codes_matching_requantized_known_float':int(np.count_nonzero(doc==predicted)),'candidates':candidates})
        (out/'progress.json').write_text(json.dumps(result,indent=2)+'\n')
        del source,codes,known,raw,known_matrix,code_matrix
        if time.monotonic()-started>270:raise TimeoutError('static audit work budget')
    result['seconds']=time.monotonic()-started;result['finding_scope']='Storage interpretation checked against the documented ACTUAL BW encoding and known float weights, not fitted to QNN logits. This does not validate all graph operator/cache semantics.'
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


def audit_controls(out):
    """Actual policy metadata plus tiny synthetic math; no model operands evaluated."""
    import math
    import struct
    from html.parser import HTMLParser
    from declared_dlc_reference import decode,encode,logical_op,policy_preflight
    started=time.monotonic()
    if sha(POLICY)!=POLICY_SHA:raise ValueError('frozen policy changed')
    p=json.loads(POLICY.read_text());t=p['tensors'];preflight=policy_preflight(p)
    if not preflight['passed']:raise ValueError('policy topology/shape contract failed')
    doc=HEADER.parents[2]/'docs/QAIRT-Docs/QNN/OpDef/MasterOpDef.html'
    class Text(HTMLParser):
        def __init__(self):super().__init__();self.rows=[]
        def handle_data(self,data):
            if data.strip():self.rows.append(data.strip())
    parser=Text();parser.feed(doc.read_text());text=' '.join(parser.rows)
    required=['quantization parameters as specified with Qnn_QuantizeParams_t are obeyed','innermost two dimensions','Root Mean Square normalization']
    if not all(s in text for s in required):raise ValueError('expected operator contract passage missing')
    inventory={}
    for typ in ['Cast','Convert','MatMul','Softmax','RmsNorm','Reduce','Transpose','Conv2d','FullyConnected']:
        groups=Counter((tuple(t[n]['datatype'] for n in op['inputs']),tuple(t[n]['datatype'] for n in op['outputs']),json.dumps(op['attrs'],sort_keys=True)) for op in p['operators'] if op['type']==typ)
        inventory[typ]=[{'inputs':list(k[0]),'outputs':list(k[1]),'attrs':json.loads(k[2]),'count':v} for k,v in groups.items()]
    cases=[]
    def check(name,actual,expected,tolerance=0):
        error=float(np.max(np.abs(np.asarray(actual,dtype=np.float64)-np.asarray(expected,dtype=np.float64))))
        if error>tolerance:raise ValueError('synthetic contract mismatch '+name)
        cases.append({'case':name,'max_abs_error':error,'tolerance':tolerance})
    for name in ['attention_mask','swa_attention_mask']:
        spec=dict(t[name]);spec['dimensions']=[2]
        check(name+'_unsigned_grid_endpoints',decode(np.array([0,65535],dtype=np.uint16),spec),[-50.,0.])
    logits=dict(t['logits']);logits['dimensions']=[3];words=np.array([0,31869,65535],dtype=np.uint16)
    check('unsigned_output_grid',decode(words,logits),[(int(v)-31869)*0.0008891067700460553 for v in words],2e-6)
    source={'datatype':'uFxp_16','dimensions':[2],'grid':{'axis':None,'bitwidths':[16],'scale':[1.0],'offset':[-32768]}}
    target={'datatype':'Float_16','dimensions':[2]};op={'type':'Convert','attrs':{'dynamic_input_data':False,'dynamic_output_data':False}}
    converted=encode(logical_op(op,[decode(np.array([32768,32769],dtype=np.uint16),source)],[2]),target)
    check('Convert_obeys_quantization_grid',converted,[0.,1.])
    # A general Cast ignores quantization parameters. Current helper would not;
    # all THREE actual Cast nodes are Float16->Float16 identities, so this is dormant.
    actual_casts=[o for o in p['operators'] if o['type']=='Cast']
    if len(actual_casts)!=3 or any([t[n]['datatype'] for n in o['inputs']+o['outputs']]!=['Float_16','Float_16'] for o in actual_casts):raise ValueError('unreviewed non-identity Cast in actual graph')
    half_values=np.array([0.,-0.,1+2**-11,1+3*2**-11,2**-24],dtype=np.float32)
    packed=b''.join(struct.pack('<e',float(x)) for x in half_values)
    if encode(half_values,{'datatype':'Float_16'}).astype('<f2').tobytes()!=packed:raise ValueError('binary16 boundary mismatch')
    cases.append({'case':'FP16_rounding_ties_signed_zero_subnormal','exact_bytes':True})
    x=np.arange(24,dtype=np.float32).reshape(2,1,3,4)/10-1;gamma=np.array([1,2,.5,1.5],dtype=np.float32);beta=np.array([0,.1,-.1,.2],dtype=np.float32)
    rmsop={'type':'RmsNorm','attrs':{'axes':[3],'epsilon':1e-6}}
    expected=np.empty_like(x)
    for a in range(2):
        for c in range(3):
            row=x[a,0,c];den=math.sqrt(sum(float(v)**2 for v in row)/4+1e-6)
            expected[a,0,c]=[float(row[j])*float(gamma[j])/den+float(beta[j]) for j in range(4)]
    check('RmsNorm_axis3_gamma_beta',logical_op(rmsop,[x,gamma,beta],list(x.shape)),expected,5e-7)
    soft={'type':'Softmax','attrs':{'axis':3,'beta':1.0}};expected=np.empty_like(x)
    for a in range(2):
        for c in range(3):
            vals=[math.exp(float(v)) for v in x[a,0,c]];expected[a,0,c]=[v/sum(vals) for v in vals]
    check('Softmax_axis3_beta1',logical_op(soft,[x],list(x.shape)),expected,1e-7)
    a=np.arange(12,dtype=np.float32).reshape(2,1,2,3);b=np.arange(12,dtype=np.float32).reshape(1,3,4);expected=np.empty((2,1,2,4),dtype=np.float32)
    for batch in range(2):
        for i in range(2):
            for j in range(4):expected[batch,0,i,j]=sum(float(a[batch,0,i,k])*float(b[0,k,j]) for k in range(3))
    check('MatMul_innermost_dims_batch_broadcast_no_transposes',logical_op({'type':'MatMul','attrs':{'transpose_in0':False,'transpose_in1':False}},[a,b],list(expected.shape)),expected)
    conv_x=np.arange(6,dtype=np.float32).reshape(1,1,2,3);weight=np.arange(12,dtype=np.float32).reshape(1,1,3,4);bias=np.arange(4,dtype=np.float32);expect=expected[:1]+bias
    check('Conv1x1_NHWC_HWIO_bias',logical_op({'type':'Conv2d','attrs':{'stride':[1,1],'dilation':[1,1],'group':1,'pad_amount':[[0,0],[0,0]]}},[conv_x,weight,bias],list(expect.shape)),expect)
    check('FullyConnected_OI_bias',logical_op({'type':'FullyConnected','attrs':{}},[conv_x.reshape(1,2,3),weight[0,0].T,bias],[1,2,4]),expect.reshape(1,2,4))
    definition=HEADER.parent/'QnnOpDef.h';defs=definition.read_text();enums={'ADD':0,'DIVIDE':2,'MULTIPLY':13,'POWER':16,'SUBTRACT':18}
    import re
    for key,value in enums.items():
        if not re.search(r'#define\s+QNN_OP_ELEMENT_WISE_BINARY_OPERATION_'+key+r'\s+'+str(value)+r'\b',defs):raise ValueError('binary operation enum mismatch')
    from matched_prefill_inputs import advance_cache
    caches={'past_key_4_h0_in':np.full((1,1,2,3968),32768,dtype=np.uint16),'past_value_4_h0_in':np.full((1,1,3968,2),32768,dtype=np.uint16).view(np.float16),'swa_key_0_h0_in':np.full((1,1,2,512),32768,dtype=np.uint16),'swa_value_0_h0_in':np.full((1,1,512,2),32768,dtype=np.uint16)}
    for start in range(0,1929,128):
        count=min(128,1929-start);synthetic={}
        for name,buf in caches.items():
            axis=-1 if '_key_' in name else -2;shape=list(buf.shape);shape[axis]=128;value=np.full(shape,6666,dtype=buf.dtype)
            for row in range(count):
                index=[slice(None)]*buf.ndim;index[axis]=row;value[tuple(index)]=start+row+1
            synthetic[name.removesuffix('_in')+'_out']=value
        advance_cache(caches,synthetic,{'start':start,'real_rows':count})
        end=start+count
        for name,buf in caches.items():
            axis=-1 if '_key_' in name else -2;width=buf.shape[axis];expected=np.full(buf.shape,32768,dtype=np.uint16)
            if buf.dtype==np.float16:expected=expected.view(np.float16)
            for token in range(max(0,end-width),end):
                index=[slice(None)]*buf.ndim;index[axis]=token%width;expected[tuple(index)]=token+1
            if not np.array_equal(buf.view(np.uint16),expected.view(np.uint16)):raise ValueError('synthetic own-cache ring/global/negative-zero mismatch')
    cases.append({'case':'own_cache16chunks_global_SWA_wrap_final9_excludes_padding_FP16_negative_zero','exact_bytes':True,'synthetic_cache_types':4})
    normalizers=[];seen=set()
    for op in p['operators']:
        if op['type']!='RmsNorm':continue
        for role,name in zip(['gamma','beta'],op['inputs'][1:]):
            if name in seen:continue
            seen.add(name);spec=t[name]
            if 'static' not in spec:raise ValueError('dynamic normalizer parameter needs a separate audit')
            path=POLICY.parent/spec['static']['file']
            if sha(path)!=spec['static']['npy_sha256']:raise ValueError('static normalizer changed')
            data=decode(np.load(path,mmap_mode='r',allow_pickle=False),spec)
            normalizers.append({'name':name,'role':role,'datatype':spec['datatype'],'values':int(data.size),'finite':bool(np.isfinite(data).all()),'minimum':float(data.min()),'maximum':float(data.max()),'nonzero':int(np.count_nonzero(data))})
    outputs=[n for o in p['operators'] for n in o['outputs']];result={'classification':'saved_policy_and_synthetic_operator_contract_checks','model_graph_forward_calls':0,'phone_calls':0,'actual_neural_model_operand_evaluations':0,'static_parameter_dequantization':True,'reference_implementation_changed':False,'policy_sha256':POLICY_SHA,'topology_shape_preflight':preflight,'duplicate_output_writer_names':len(outputs)-len(set(outputs)),'operator_inventory':inventory,'synthetic_cases':cases,'static_normalizer_parameters':normalizers,'contract_documents':[{'path':str(doc),'sha256':sha(doc)},{'path':str(definition),'sha256':sha(definition)}],'dormant_Cast_generality_gap':'Reference treats non-preserved Cast like Convert and would obey grids, unlike general QNN Cast. Actual three Cast nodes are Float16 identity, so this is NOT an active explanation. No code changed.','remaining_uncertainty':'Only final QNN/reference vectors and operation timing/name traces were saved; no matching intermediate activation values. These static/synthetic checks do not locate first numerical divergence or validate the full reference.','seconds':time.monotonic()-started}
    out.mkdir(parents=True,exist_ok=False);(out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


def prototype_fp16_storage_view(raw,datatype):
    """AUDIT-ONLY prototype. Do not confuse FP16 transport bits with real uFxp16."""
    if datatype!='Float_16':return raw
    value=np.asarray(raw)
    if value.dtype==np.float16:return raw
    if value.dtype.kind=='u' and value.dtype.itemsize==2:
        return np.asarray(value,dtype=np.uint16).view(np.float16)
    raise ValueError('unreviewed Float16 storage representation')


def audit_fp16_transport(out):
    import struct
    from unittest.mock import patch
    from declared_dlc_reference import DeclaredDlcReference,decode
    source=TRACK/'tools/declared_dlc_reference.py'
    if sha(source)!='06f108e24d5370d94e57b24cb8e285106deeef8be0d03d9f29b28187b4cd2045' or sha(POLICY)!=POLICY_SHA:raise ValueError('frozen failed reference/policy changed')
    p=json.loads(POLICY.read_text());records=[];names=set()
    for name,t in p['tensors'].items():
        if t['datatype']!='Float_16' or 'static' not in t:continue
        path=POLICY.parent/t['static']['file']
        if sha(path)!=t['static']['npy_sha256']:raise ValueError('FP16 static blob changed')
        raw=np.load(path,mmap_mode='r',allow_pickle=False);fixed=prototype_fp16_storage_view(raw,t['datatype']);old=decode(raw,t)
        if raw.dtype!=np.uint16 or raw.shape!=fixed.shape or fixed.flags.writeable or not np.shares_memory(raw,fixed):raise ValueError('unexpected actual FP16 transport or lost readonly view')
        independent=np.frombuffer(b''.join(struct.pack('<f',struct.unpack('<e',struct.pack('<H',int(word)))[0]) for word in raw.reshape(-1)),dtype='<f4').reshape(raw.shape)
        if not np.array_equal(fixed.astype(np.float32).view(np.uint32),independent.view(np.uint32)):raise ValueError('IEEE half decoding disagreement')
        names.add(name);records.append({'name':name,'IR_datatype':t['datatype'],'storage_dtype':str(raw.dtype),'values':int(raw.size),'raw_npy_sha256':sha(path),'raw_word_set':sorted({int(x) for x in raw.reshape(-1)}),'current_numeric_decode_min':float(old.min()),'current_numeric_decode_max':float(old.max()),'IEEE_half_decode_min':float(fixed.min()),'IEEE_half_decode_max':float(fixed.max()),'numeric_decode_mismatches':int(np.count_nonzero(old!=fixed.astype(np.float32)))})
    affected=[{'index':op['index'],'name':op['name'],'type':op['type'],'static_inputs':[n for n in op['inputs'] if n in names]} for op in p['operators'] if any(n in names for n in op['inputs'])]
    if len(records)!=30 or len(affected)!=15:raise ValueError('reviewed affected scope changed')
    out.mkdir(parents=True,exist_ok=False);fixture=out/'synthetic';fixture.mkdir()
    gamma=np.full(4,0x3c00,dtype=np.uint16);beta=np.zeros(4,dtype=np.uint16);np.save(fixture/'gamma.npy',gamma);np.save(fixture/'beta.npy',beta)
    tensors={n:{'name':n,'datatype':'Float_16','dimensions':shape} for n,shape in [('x',[1,1,1,4]),('g',[4]),('b',[4]),('gv',[1,1,1,4]),('y',[1,1,1,4]),('z',[1,1,1,4])]}
    for n,file in [('g','gamma.npy'),('b','beta.npy')]:tensors[n]['static']={'file':file,'npy_sha256':sha(fixture/file),'dtype':'uint16'}
    ops=[{'index':0,'name':'synthetic_gamma_view','type':'Reshape','inputs':['g'],'outputs':['gv'],'attrs':{}},{'index':1,'name':'synthetic_RmsNorm','type':'RmsNorm','inputs':['x','gv','b'],'outputs':['y'],'attrs':{'axes':[3],'epsilon':1e-6}},{'index':2,'name':'synthetic_identity_cast','type':'Cast','inputs':['y'],'outputs':['z'],'attrs':{}}]
    model={'tensors':tensors,'operators':ops,'input_names':['x'],'output_names':['z']};path=fixture/'policy.json';path.write_text(json.dumps(model)+'\n');x=np.array([1,2,3,4],dtype=np.float16).reshape(1,1,1,4)
    baseline=DeclaredDlcReference(path).run_encoded({'x':x})['z'];real_load=np.load;normalized=[]
    def storage_loader(file,*args,**kwargs):
        result=real_load(file,*args,**kwargs)
        if Path(file).name in ['gamma.npy','beta.npy']:
            result=prototype_fp16_storage_view(result,'Float_16');normalized.append(str(result.dtype))
        return result
    with patch('declared_dlc_reference.np.load',side_effect=storage_loader):corrected=DeclaredDlcReference(path).run_encoded({'x':x})['z']
    expected=(x.astype(np.float32)/np.sqrt(np.mean(x.astype(np.float32)**2,axis=3,keepdims=True)+np.float32(1e-6))).astype(np.float16)
    if not np.array_equal(corrected.view(np.uint16),expected.view(np.uint16)) or not np.all(baseline>1000) or set(normalized)!={'float16'}:raise ValueError('synthetic real-loader/view/RmsNorm regression failed')
    words=np.array([0,0x8000,0x3c00,0xc000,1],dtype=np.uint16);bits_before=words.copy();half=prototype_fp16_storage_view(words,'Float_16')
    if not np.array_equal(half.view(np.uint16),bits_before) or not np.shares_memory(words,half) or prototype_fp16_storage_view(words,'uFxp_16') is not words or prototype_fp16_storage_view(half,'Float_16') is not half:raise ValueError('bit-preservation/type isolation failed')
    cast_source=TRACK/'.local/paired-mapping-observer/build-01/sdk-source/examples/Genie/Genie/src/qualla/engines/qnn-htp/nsp-base-model.hpp'
    if 'fp16_ieee_to_fp32_value(inputs[i])' not in cast_source.read_text():raise ValueError('SDK half-word conversion anchor missing')
    stderr=TRACK/'.local/legacy-prefill-host-runs/legacy-ref-20260913T131149Z-01/child.stderr';trace=stderr.parent/'native/operations.jsonl';executed=Counter();indices={row['index'] for row in affected}
    with trace.open() as f:
        for line in f:
            row=json.loads(line)
            if row['event']=='begin' and row['index'] in indices:executed[row['index']]+=1
    result={'classification':'active_reference_FP16_static_transport_decode_defect','failed_reference_source_sha256':sha(source),'policy_sha256':POLICY_SHA,'static_tensors':records,'affected_consumers':affected,'first_known_affected_operator':affected[0],'affected_operator_begins_in_saved_full_run':sum(executed.values()),'all_affected_consumers_seen_in_all16chunks':set(executed)==indices and set(executed.values())=={16},'SDK_word_conversion_source':{'path':str(cast_source),'sha256':sha(cast_source),'line':632,'conversion':'fp16_ieee_to_fp32_value(inputs[i])'},'independent_IEEE_binary16_validation':True,'synthetic_actual_loader_preserved_view_RmsNorm_Cast_path':{'operators':3,'old_result':[float(v) for v in baseline.reshape(-1)],'prototype_result':[float(v) for v in corrected.reshape(-1)],'prototype_matches_expected_half_bytes':True,'actual_model_operands_used':False},'prototype_preserves_signed_zero_subnormal_and_readonly_word_bits':True,'true_ufxp16_unchanged':True,'already_float16_unchanged':True,'saved_host_numerical_warnings':{'path':str(stderr),'sha256':sha(stderr),'lines':stderr.read_text().splitlines()},'production_reference_implementation_changed':False,'model_graph_or_phone_replays':0,'correction_scope':'Normalize ONLY declared Float16 static uint16 transport words to binary16 encoded views before preserved-memory paths/decode; retain actual quantized UINT16, BW4 rules, all other arithmetic/caches/limits. Prototype tested, production update not made.','causal_limit':'Proves active wrong gamma values in failed reference. Does not prove this is the sole mismatch cause, corrected full-run agreement, QNN defect, or generation quality.'}
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True);group=p.add_mutually_exclusive_group();group.add_argument('--controls-only',action='store_true');group.add_argument('--fp16-transport-only',action='store_true');a=p.parse_args();out=a.output_dir.resolve()
    if not out.is_relative_to(TRACK/'.local/declared-reference-static-audit'):p.error('owned fresh static-audit output required')
    if a.fp16_transport_only:audit_fp16_transport(out)
    elif a.controls_only:audit_controls(out)
    else:audit(out)
