#!/usr/bin/env python3
"""Bounded corrected reference adapter; preserve the original failed source verbatim."""
import hashlib
import json
import os
from pathlib import Path
import sys
import types

import numpy as np

TOOLS=Path(__file__).resolve().parent
BASE_SHA='06f108e24d5370d94e57b24cb8e285106deeef8be0d03d9f29b28187b4cd2045'


class NonFiniteIntermediate(FloatingPointError):
    pass


def storage_view(raw,datatype):
    """Only declared binary16 UInt16 transport words are reinterpreted as FP16."""
    if datatype!='Float_16':return raw
    value=np.asarray(raw)
    if value.dtype==np.float16:return raw
    if value.dtype.kind=='f' and value.dtype.itemsize==2:
        return np.asarray(value,dtype=np.float16)  # endian conversion, numeric half values unchanged
    if value.dtype.kind=='u' and value.dtype.itemsize==2:
        # Convert WORD byte order when needed, then reinterpret bits, never 15360->15360.0.
        return np.asarray(value,dtype=np.uint16).view(np.float16)
    raise ValueError('unreviewed declared Float16 storage representation '+str(value.dtype))


class FiniteObserver:
    """No repairs. Stop before a nonfinite can become an apparently valid integer code."""
    def __init__(self,path=None):
        self.path=Path(path) if path is not None else None
        self.context={'chunk':None,'operator_index':None,'operator_name':None}
        self.first=None

    def set_context(self,op,chunk):
        self.context={'chunk':chunk,'operator_index':op.get('index') if op else None,'operator_name':op.get('name','')[:512] if op else None}

    def record(self,record):
        if self.first is None:
            self.first=record
            if self.path is not None:
                payload=(json.dumps(record,indent=2)+'\n').encode()
                if len(payload)>8192:raise RuntimeError('nonfinite diagnostic size bound')
                try:
                    fd=os.open(self.path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_CLOEXEC|os.O_NOFOLLOW,0o600)
                    with os.fdopen(fd,'wb',closefd=True) as f:f.write(payload);f.flush();os.fdatasync(f.fileno())
                except OSError as error:
                    print('REFERENCE_NONFINITE_DIAGNOSTIC_WRITE_FAILED '+type(error).__name__,file=sys.stderr,flush=True)
        raise NonFiniteIntermediate('first unexpected nonfinite '+json.dumps(self.first,sort_keys=True))

    def floating_error(self,error,phase,tensor=None):
        self.record({**self.context,'phase':phase,'tensor':str(tensor)[:512] if tensor is not None else None,'source':'numpy floating-point trap; failed expression is not recomputed','reason':str(error)[:512],'arithmetic_repaired_or_clipped_by_observer':False})

    def check(self,value,phase,tensor=None):
        array=np.asarray(value)
        if array.dtype.kind not in 'fc':return
        scanned=0
        for block in np.nditer(array,flags=['external_loop','buffered','zerosize_ok'],op_flags=['readonly'],order='K',buffersize=262144):
            bad=~np.isfinite(block)
            if np.any(bad):
                record={**self.context,'phase':phase,'tensor':str(tensor)[:512] if tensor is not None else None,'shape':list(array.shape),'dtype':str(array.dtype),'scan_order':'K; offsets are scan positions, not logical tensor coordinates','first_bad_block_offset':scanned,'block_elements':int(block.size),'block_nan_count':int(np.count_nonzero(np.isnan(block))),'block_positive_infinity_count':int(np.count_nonzero(np.isposinf(block))),'block_negative_infinity_count':int(np.count_nonzero(np.isneginf(block))),'first_bad_indices_within_block':np.flatnonzero(bad)[:8].astype(int).tolist(),'arithmetic_repaired_or_clipped_by_observer':False}
                self.record(record)
            scanned+=int(block.size)


def materialize_source():
    path=TOOLS/'declared_dlc_reference.py';source=path.read_text()
    if hashlib.sha256(source.encode()).hexdigest()!=BASE_SHA:raise ValueError('frozen failed reference source changed')
    original=source
    changes=[
      ("    dtype=t['datatype']\n    if 'Fxp_' not in dtype:return np.asarray(raw,dtype=np.float32) if dtype.startswith('Float') else raw", "    dtype=t['datatype']\n    if dtype=='Float_16':return np.asarray(_storage_view(raw,dtype),dtype=np.float32)\n    if 'Fxp_' not in dtype:return np.asarray(raw,dtype=np.float32) if dtype.startswith('Float') else raw"),
      ("def encode(value,t):\n    dtype=t['datatype']\n    if dtype=='Float_16':return np.asarray(value,dtype=np.float16)", "def encode(value,t):\n    _finite(value,'encode_input',t.get('name'))\n    dtype=t['datatype']\n    if dtype=='Float_16':\n        encoded=np.asarray(value,dtype=np.float16)\n        _finite(encoded,'float16_encode',t.get('name'))\n        return encoded"),
      ("    return np.clip(np.rint(np.asarray(value,dtype=np.float32)/scale-offset),lo,hi).astype(storage)", "    shifted=np.asarray(value,dtype=np.float32)/scale-offset\n    _finite(shifted,'requantization_before_round_clip',t.get('name'))\n    return np.clip(np.rint(shifted),lo,hi).astype(storage)"),
      ("        start=time.monotonic()\n        if len(self.policy['operators'])>32 and not self._static_verified:self.verify_static_bindings()", "        chunk=getattr(self,'_observed_chunks',0);self._observed_chunks=chunk+1\n        _observer_context(None,chunk)\n        start=time.monotonic()\n        if len(self.policy['operators'])>32 and not self._static_verified:self.verify_static_bindings()"),
      ("            live[n]=v\n        for op in p['operators']:", "            _finite(v,'graph_input',n)\n            live[n]=v\n        for op in p['operators']:\n            _observer_context(op,chunk)"),
      ("raw=[np.load(self.path.parent/t[n]['static']['file'],mmap_mode='r',allow_pickle=False) if 'static' in t[n] else live[n] for n in op['inputs']]", "raw=[_load_static(self.path.parent/t[n]['static']['file'],t[n]) if 'static' in t[n] else live[n] for n in op['inputs']]"),
      ("            value=logical_op(op,args,spec['dimensions']);value=value if preserved else encode(value,spec)", "            for input_name,arg in zip(op['inputs'],args):_finite(arg,'operator_input',input_name)\n            value=logical_op(op,args,spec['dimensions'])\n            _finite(value,'logical_output',out_name)\n            value=value if preserved else encode(value,spec)\n            _finite(value,'encoded_output',out_name)"),
    ]
    for before,after in changes:
        if source.count(before)!=1:raise ValueError('corrected reference anchor changed')
        source=source.replace(before,after)
    inverse=source
    for before,after in reversed(changes):inverse=inverse.replace(after,before)
    if inverse!=original:raise ValueError('unbounded reference mutation')
    return source,{'base_sha256':BASE_SHA,'materialized_sha256':hashlib.sha256(source.encode()).hexdigest(),'changes':changes,'storage_correction':'declared Float16 UInt16 words -> binary16 views before preserved-memory operations and decode','true_UFIXED16_and_BW4_unchanged':True,'finite_grid_rounding_and_clipping_unchanged':True,'nonfinite_policy':'record first unexpected nonfinite and stop before integer rounding/clipping/cast; no repair','arithmetic_beyond_storage_correction_changed':False}


def load_runtime(diagnostic_path=None):
    source,receipt=materialize_source();observer=FiniteObserver(diagnostic_path)
    def load_static(path,spec):
        return storage_view(np.load(path,mmap_mode='r',allow_pickle=False),spec['datatype'])
    module=types.ModuleType('corrected_declared_dlc_reference');module.__file__=str(Path(__file__).resolve())
    module.__dict__.update(_storage_view=storage_view,_load_static=load_static,_finite=observer.check,_observer_context=observer.set_context)
    exec(compile(source,module.__file__,'exec'),module.__dict__)
    # Trap hidden NumPy floating failures too (e.g. RMS square overflow), not
    # just nonfinite returned tensors. Underflow remains ordinary precision behavior.
    def guarded(function,phase):
        def call(*args,**kwargs):
            try:
                with np.errstate(over='raise',invalid='raise',divide='raise',under='ignore'):
                    return function(*args,**kwargs)
            except NonFiniteIntermediate:raise
            except FloatingPointError as error:
                spec=args[1] if phase in {'decode','encode'} else None
                observer.floating_error(error,phase,spec.get('name') if isinstance(spec,dict) else None)
        return call
    for name in ['logical_op','encode','decode']:module.__dict__[name]=guarded(module.__dict__[name],name)
    module.finite_observer=observer
    receipt['floating_error_traps']=['overflow','invalid','divide_by_zero']
    receipt['underflow_policy']='unchanged; not escalated'
    return module,receipt
