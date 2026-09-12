#!/usr/bin/env python3
"""Portable declared-DLC policy arithmetic, NOT proprietary DSP-kernel emulation.

Imports/constructor never run an operation. Full graphs require an explicit run
opt-in; preparation tests use only small synthetic policies.
"""
from collections import Counter
import json
import hashlib
from pathlib import Path
import time

import numpy as np
from scipy.special import erf

SUPPORTED={'Reshape','FullyConnected','Eltwise_Binary','Reduce','Gather','Conv2d','RmsNorm','Transpose','Convert','StridedSlice','Concat','MatMul','Softmax','ElementWiseNeuron','Cast'}
MEMORY_OPS={'Reshape','Gather','Transpose','StridedSlice','Concat','Convert','Cast'}


def grid_arrays(t):
    g=t['grid'];axis=g['axis'];shape=[1]*len(t['dimensions'])
    if axis is not None:shape[axis]=len(g['scale'])
    scale=np.asarray(g['scale'],dtype=np.float32).reshape(shape)
    offset=np.asarray(g['offset'],dtype=np.float32).reshape(shape)
    bits=set(g['bitwidths'])
    if len(bits)!=1:raise ValueError('mixed per-axis bit widths not supported')
    return scale,offset,next(iter(bits))


def decode(raw,t,max_temporary_elements=1048576):
    dtype=t['datatype']
    if 'Fxp_' not in dtype:return np.asarray(raw,dtype=np.float32) if dtype.startswith('Float') else raw
    scale,offset,bits=grid_arrays(t)
    def block(value,s,o):
        if dtype.startswith('sFxp') and bits<np.dtype(value.dtype).itemsize*8:
            # BW4 int8 containers carry low-nibble two's-complement codes.
            q=np.bitwise_and(np.asarray(value,dtype=np.int32),(1<<bits)-1)
            q=np.where(q>=(1<<(bits-1)),q-(1<<bits),q)
        else:q=value
        return (np.asarray(q,dtype=np.float32)+o)*s
    if raw.size<=max_temporary_elements:return block(raw,scale,offset)
    # One dequantized operand, never an all-F32 model cache. Tile contiguous
    # leading rows so effective-width/sign/scale temporaries stay bounded.
    axis=next(j for j,n in enumerate(raw.shape) if n>1)
    row_size=raw.size//raw.shape[axis];step=max(1,max_temporary_elements//row_size)
    result=np.empty(raw.shape,dtype=np.float32)
    for start in range(0,raw.shape[axis],step):
        selection=[slice(None)]*raw.ndim;selection[axis]=slice(start,start+step);selection=tuple(selection)
        if t['grid']['axis']==axis:s,o=scale[selection],offset[selection]
        else:s,o=scale,offset
        result[selection]=block(raw[selection],s,o)
    return result


def encode(value,t):
    dtype=t['datatype']
    if dtype=='Float_16':return np.asarray(value,dtype=np.float16)
    if dtype=='Float_32':return np.asarray(value,dtype=np.float32)
    if 'Fxp_' not in dtype:
        kinds={'Int_32':np.int32,'UInt_32':np.uint32,'Int_64':np.int64,'UInt_64':np.uint64,'Int_8':np.int8,'UInt_8':np.uint8,'Int_16':np.int16,'UInt_16':np.uint16,'Bool_8':np.bool_}
        return np.asarray(value,dtype=kinds[dtype])
    scale,offset,bits=grid_arrays(t)
    if np.any(scale<=0):raise ValueError('nonpositive active output scale')
    signed=dtype.startswith('sFxp');lo=-(1<<(bits-1)) if signed else 0;hi=(1<<(bits-1))-1 if signed else (1<<bits)-1
    width=int(dtype.rsplit('_',1)[1]);storage=np.dtype(('int' if signed else 'uint')+str(width))
    # Reference rounding policy is explicit. DSP half-way behavior, fusion and
    # accumulation are not inferred from these declared tensor encodings.
    return np.clip(np.rint(np.asarray(value,dtype=np.float32)/scale-offset),lo,hi).astype(storage)


def same_policy(a,b):
    return a['datatype']==b['datatype'] and a.get('grid')==b.get('grid')


def validate_op(op):
    typ=op['type'];a=op['attrs']
    if typ not in SUPPORTED:raise ValueError('unexpressed operation '+typ)
    if typ=='Eltwise_Binary' and a['operation'] not in {0,2,13,16,18}:raise ValueError('unexpressed binary operation')
    if typ=='ElementWiseNeuron' and a['operation'] not in {1,8}:raise ValueError('unexpressed neuron operation')
    if typ=='Reduce' and a['reduce_type']!='ReduceMean':raise ValueError('unexpressed reduction')
    if typ=='Conv2d' and not (a['stride']==[1,1] and a['dilation']==[1,1] and a['group']==1 and a['pad_amount']==[[0,0],[0,0]]):raise ValueError('only actual1x1 unpadded convolution policy supported')
    if typ=='StridedSlice' and any(a[k] for k in ['begin_mask','end_mask','new_axes_mask','shrink_axes']):raise ValueError('nonzero slice masks not supported')


def logical_op(op,args,shape):
    validate_op(op);typ=op['type'];a=op['attrs']
    if typ=='Reshape':return args[0].reshape(shape)
    if typ in {'Convert','Cast'}:return args[0]
    if typ=='Transpose':return args[0].transpose(a['perm'])
    if typ=='Concat':return np.concatenate(args,axis=a['axis'])
    if typ=='Gather':return np.take(args[0],args[1].astype(np.int64),axis=a['axis'])
    if typ=='StridedSlice':return args[0][tuple(slice(int(lo),int(hi),int(step)) for lo,hi,step in a['ranges'])]
    if typ=='Eltwise_Binary':return {0:np.add,2:np.divide,13:np.multiply,16:np.power,18:np.subtract}[a['operation']](*args)
    if typ=='Reduce':return np.mean(args[0],axis=tuple(a['axes']),keepdims=a['keep_dims'],dtype=np.float32)
    if typ=='MatMul':
        x,y=args
        if a['transpose_in0']:x=x.swapaxes(-1,-2)
        if a['transpose_in1']:y=y.swapaxes(-1,-2)
        return np.matmul(x,y)
    if typ=='FullyConnected':
        y=np.matmul(args[0],args[1].T)
        return y+args[2] if len(args)>2 else y
    if typ=='Conv2d':
        if args[1].shape[:2]!=(1,1):raise ValueError('non-pointwise convolution')
        y=np.matmul(args[0],args[1][0,0])
        return y+args[2] if len(args)>2 else y
    if typ=='RmsNorm':
        x=args[0];y=x/np.sqrt(np.mean(x*x,axis=tuple(a['axes']),keepdims=True,dtype=np.float32)+np.float32(a['epsilon']))
        if len(args)>1:y=y*args[1]
        if len(args)>2:y=y+args[2]
        return y
    if typ=='Softmax':
        x=args[0]*np.float32(a['beta']);x=x-np.max(x,axis=a['axis'],keepdims=True);v=np.exp(x)
        return v/np.sum(v,axis=a['axis'],keepdims=True,dtype=np.float32)
    if typ=='ElementWiseNeuron':
        if a['operation']==8:return np.tanh(args[0])
        # QNN MasterOpDef GELU formula is erf, not an invented tanh fallback.
        x=args[0];return np.float32(.5)*x*(np.float32(1)+erf(x/np.float32(np.sqrt(2))))
    raise AssertionError(typ)


def inferred_shape(op,shapes,target):
    typ=op['type'];a=op['attrs'];x=list(shapes[0])
    if typ=='Reshape':
        if np.prod(x,dtype=np.int64)!=np.prod(target,dtype=np.int64):raise ValueError('reshape element count')
        return target
    if typ in {'Convert','Cast','RmsNorm','Softmax','ElementWiseNeuron'}:return x
    if typ=='Transpose':return [x[j] for j in a['perm']]
    if typ=='StridedSlice':return [len(range(*slice(*q).indices(n))) for n,q in zip(x,a['ranges'])]
    if typ=='Gather':
        axis=a['axis'];return x[:axis]+list(shapes[1])+x[axis+1:]
    if typ=='Concat':
        axis=a['axis']
        if any(any(v!=x[j] for j,v in enumerate(s) if j!=axis) for s in shapes):raise ValueError('concat non-axis dimensions')
        x[axis]=sum(s[axis] for s in shapes);return x
    if typ=='Eltwise_Binary':return list(np.broadcast_shapes(*map(tuple,shapes)))
    if typ=='Reduce':return [1 if j in a['axes'] else n for j,n in enumerate(x)] if a['keep_dims'] else [n for j,n in enumerate(x) if j not in a['axes']]
    if typ=='FullyConnected':
        if x[-1]!=shapes[1][-1]:raise ValueError('FC contraction')
        return x[:-1]+[shapes[1][0]]
    if typ=='Conv2d':
        if x[-1]!=shapes[1][-2]:raise ValueError('Conv contraction')
        return x[:-1]+[shapes[1][-1]]
    if typ=='MatMul':
        y=list(shapes[1])
        if a['transpose_in0']:x[-2:]=x[-2:][::-1]
        if a['transpose_in1']:y[-2:]=y[-2:][::-1]
        if x[-1]!=y[-2]:raise ValueError('MatMul contraction')
        return list(np.broadcast_shapes(tuple(x[:-2]),tuple(y[:-2])))+[x[-2],y[-1]]
    raise ValueError('shape inference unavailable '+typ)


def policy_preflight(policy):
    tensors=policy['tensors'];seen=set(policy['input_names'])|{n for n,t in tensors.items() if 'static' in t};issues=[]
    for op in policy['operators']:
        try:
            validate_op(op)
            if len(op['outputs'])!=1:raise ValueError('multiple outputs unsupported')
            if any(n not in seen for n in op['inputs']):raise ValueError('non-topological or missing input')
            if op['type']=='Conv2d' and tensors[op['inputs'][1]]['dimensions'][:2]!=[1,1]:raise ValueError('non-pointwise convolution')
            target=tensors[op['outputs'][0]]['dimensions']
            if inferred_shape(op,[tensors[n]['dimensions'] for n in op['inputs']],target)!=target:raise ValueError('declared output shape mismatch')
            for name in op['inputs']+op['outputs']:
                t=tensors[name]
                if 'Fxp_' in t['datatype']:
                    g=t['grid']
                    if not g['scale'] or len(set(g['bitwidths']))!=1:raise ValueError('unexpressed grid')
                    if g['axis'] is not None and len(g['scale'])!=t['dimensions'][g['axis']]:raise ValueError('axis-grid mismatch')
            seen.update(op['outputs'])
        except (ValueError,KeyError) as e:issues.append({'op':op['name'],'issue':str(e)})
    return {'passed':not issues,'issues':issues,'operators_checked':len(policy['operators']),'arithmetic':'F32 logical ops, actual stored effective-width static codes, declared per-tensor/per-axis grids, explicit binary16 boundaries. Integer output rounding nearest-even; DSP fidelity unresolved.','full_model_executed':False}


def memory_plan(policy):
    """Conservative shape-only liveness; not measured full-model memory."""
    tensors=policy['tensors']
    def elements(name):return int(np.prod(tensors[name]['dimensions'],dtype=np.int64))
    def encoded_bytes(name):
        typ=tensors[name]['datatype'];width=2 if typ in {'uFxp_16','Float_16'} else 4
        return elements(name)*width
    remaining=Counter(n for op in policy['operators'] for n in op['inputs'])
    for n in policy['output_names']:remaining[n]+=1
    # Caller retains the38 prepared inputs/caches for the chunk; count them once.
    fixed=sum(encoded_bytes(n) for n in policy['input_names']);live={};peak=fixed;max_args=0;max_output=0
    for op in policy['operators']:
        max_args=max(max_args,sum(elements(n)*4 for n in op['inputs']))
        for n in op['outputs']:live[n]=encoded_bytes(n);max_output=max(max_output,elements(n)*4)
        peak=max(peak,fixed+sum(live.values()))
        for n in op['inputs']:
            remaining[n]-=1
            if remaining[n]==0:live.pop(n,None)
    statics=[n for n,t in tensors.items() if 'static' in t]
    largest=max(statics,key=elements)
    return {'static_code_bytes':sum(tensors[n]['static']['raw_bytes'] for n in statics),'dequantized_static_cache_policy':'NONE; mmap actual codes on demand, release dequantized operands after each op','largest_F32_static_name':largest,'largest_F32_static_bytes':elements(largest)*4,'dequant_tile_elements':1048576,'dequant_temporary_estimate_bytes':64*1024**2,'conservative_encoded_liveness_bytes':peak,'largest_F32_argument_sum_bytes':max_args,'largest_F32_output_bytes':max_output,'all_static_F32_bytes_NOT_retained':sum(elements(n)*4 for n in statics),'host_cap_bytes':12*1024**3,'host_swap_cap_bytes':2*1024**3,'full_model_memory_measured':False,'boundary':'Shape-based accounting excludes allocator/BLAS packing/library overhead;12GiB cgroup remains the hard limit. Views counted conservatively, no all-F32 retained graph.'}


class DeclaredDlcReference:
    def __init__(self,policy_path):
        self.path=Path(policy_path);self.policy=json.loads(self.path.read_text());self.preflight=policy_preflight(self.policy)
        if not self.preflight['passed']:raise ValueError(self.preflight['issues'])
        self._static_verified=False

    def verify_static_bindings(self):
        count=0
        for spec in self.policy['tensors'].values():
            if 'static' not in spec:continue
            info=spec['static'];path=self.path.parent/info['file'];h=hashlib.sha256()
            if not path.resolve().is_relative_to(self.path.parent.resolve()):raise ValueError('static path escaped owned policy')
            with path.open('rb') as f:
                for block in iter(lambda:f.read(4*1024*1024),b''):h.update(block)
            if h.hexdigest()!=info.get('npy_sha256'):raise ValueError('static blob binding mismatch '+info['file'])
            count+=1
        self._static_verified=True;return count

    def run_encoded(self,inputs,*,allow_full_model=False,authorization_id=None,wall_seconds=1800,on_event=None):
        if len(self.policy['operators'])>32 and (not allow_full_model or not authorization_id):
            raise PermissionError('Full-model execution is not authorized by preparation; explicit separately granted run required')
        start=time.monotonic()
        if len(self.policy['operators'])>32 and not self._static_verified:self.verify_static_bindings()
        p=self.policy;t=p['tensors'];live={};left=Counter(n for op in p['operators'] for n in op['inputs'])
        for n in p['output_names']:left[n]+=1
        if set(inputs)!=set(p['input_names']):raise ValueError('exact input set required')
        for n,v in inputs.items():
            if list(v.shape)!=t[n]['dimensions']:raise ValueError('input shape mismatch '+n)
            dtype=t[n]['datatype']
            expected=np.dtype('float16' if dtype=='Float_16' else 'uint16' if dtype=='uFxp_16' else 'float32' if dtype=='Float_32' else v.dtype)
            if v.dtype!=expected:raise ValueError('encoded input dtype mismatch '+n)
            live[n]=v
        for op in p['operators']:
            if time.monotonic()-start>wall_seconds:raise TimeoutError('reference wall bound')
            if on_event:on_event({'event':'begin','index':op['index'],'name':op['name'],'seconds':time.monotonic()-start})
            raw=[np.load(self.path.parent/t[n]['static']['file'],mmap_mode='r',allow_pickle=False) if 'static' in t[n] else live[n] for n in op['inputs']]
            out_name=op['outputs'][0];spec=t[out_name]
            policy_inputs=op['inputs'][:1] if op['type']=='Gather' else op['inputs']
            preserved=op['type'] in MEMORY_OPS and all(same_policy(t[n],spec) for n in policy_inputs)
            args=raw if preserved else [decode(v,t[n]) for n,v in zip(op['inputs'],raw)]
            value=logical_op(op,args,spec['dimensions']);value=value if preserved else encode(value,spec)
            if list(value.shape)!=spec['dimensions']:raise ValueError('output shape mismatch '+op['name'])
            live[out_name]=value
            for n in op['inputs']:
                left[n]-=1
                if left[n]==0:live.pop(n,None)
            if on_event:on_event({'event':'end','index':op['index'],'seconds':time.monotonic()-start})
            del raw,args,value
        return {n:live[n] for n in p['output_names']}
