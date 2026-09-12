"""Bounded observation-only CPU timings; no model import/execution on import.

Every wrapped callable is evaluated ONCE with its original arguments and the
same object/result/exception is returned. No tensor contents or .weight probes.
Start events are flushed before expensive calls; parent IDs distinguish nested
inclusive timings. Exclusive times subtract immediate children on the same
Python thread; process CPU time includes all native worker threads.
"""
from contextlib import contextmanager
from functools import wraps
import json
from pathlib import Path
import threading
import time


class CostTrace:
    def __init__(self,path,tensor_type,max_events=10000,max_bytes=8*1024*1024):
        self.path=Path(path);self.file=self.path.open('x',buffering=1)
        self.tensor_type=tensor_type;self.max_events=max_events;self.max_bytes=max_bytes
        self.events=0;self.bytes=0;self.calls=0;self.logging_error=None
        self.local=threading.local()

    def describe(self,value):
        if isinstance(value,self.tensor_type):
            return {'kind':'tensor','shape':list(value.shape),'dtype':str(value.dtype),'device':str(value.device)}
        if isinstance(value,(str,int,float,bool)) or value is None:return value
        # In particular, NEVER read a module's .weight property for metadata.
        return {'kind':type(value).__name__}

    def emit(self,row):
        if self.logging_error:return
        try:
            line=json.dumps(row,sort_keys=True)+'\n';size=len(line.encode())
            if self.events>=self.max_events or self.bytes+size>self.max_bytes:
                self.logging_error='bounded trace cap reached; computation continues unchanged';return
            self.file.write(line);self.file.flush();self.events+=1;self.bytes+=size
        except Exception as error:self.logging_error=f'{type(error).__name__}: {error}'

    def wrap(self,label,original):
        @wraps(original)
        def observed(*args,**kwargs):
            self.calls+=1;call=self.calls
            stack=getattr(self.local,'stack',None)
            if stack is None:stack=[];self.local.stack=stack
            frame={'call':call,'parent':stack[-1]['call'] if stack else None,'depth':len(stack),
                   'thread':threading.get_ident(),'wall':time.monotonic_ns(),'cpu':time.process_time_ns(),
                   'child_wall':0,'child_cpu':0}
            name='unlabeled'
            try:
                name=label(*args,**kwargs) if callable(label) else label
                self.emit({'event':'begin','call':call,'parent':frame['parent'],'depth':frame['depth'],'thread':frame['thread'],
                    'operation':name,'monotonic_ns':frame['wall'],'process_cpu_ns':frame['cpu'],
                    'args':[self.describe(x) for x in args],'kwargs':{k:self.describe(v) for k,v in kwargs.items()}})
            except Exception as error:self.logging_error=f'metadata: {type(error).__name__}: {error}'
            stack.append(frame);exception=None;result=None
            try:
                result=original(*args,**kwargs)
                return result
            except BaseException as error:
                exception=type(error).__name__
                raise
            finally:
                wall=time.monotonic_ns()-frame['wall'];cpu=time.process_time_ns()-frame['cpu']
                stack.pop()
                if stack:stack[-1]['child_wall']+=wall;stack[-1]['child_cpu']+=cpu
                try:
                    self.emit({'event':'error' if exception else 'end','call':call,'parent':frame['parent'],'depth':frame['depth'],'thread':frame['thread'],
                        'operation':name,'exception_type':exception,'wall_ns':wall,'process_cpu_ns':cpu,
                        'exclusive_wall_ns':wall-frame['child_wall'],'exclusive_process_cpu_ns':cpu-frame['child_cpu'],
                        'output':self.describe(result) if not exception else None})
                except Exception as error:self.logging_error=f'metadata: {type(error).__name__}: {error}'
        return observed

    @contextmanager
    def instrument(self,model,gemma_quant,torch):
        """Install read-only wrappers after loading/validation, restore exactly."""
        named=list(model.named_modules());names={id(m):(n or '<root>') for n,m in named}
        patches=[];instance_forwards=[]
        def patch(owner,name,replacement):
            original=getattr(owner,name);patches.append((owner,name,original));setattr(owner,name,replacement)
        def method_label(suffix):
            return lambda self,*args,**kwargs:names.get(id(self),type(self).__name__)+suffix
        try:
            emb=gemma_quant.QuantizedEmbedding;linear=gemma_quant.QuantizedLinear
            # Accessing this descriptor on the CLASS does not evaluate its getter.
            original_property=emb.weight
            patch(emb,'weight',property(self.wrap(method_label('.weight_property'),original_property.fget),
                                        original_property.fset,original_property.fdel,original_property.__doc__))
            patch(emb,'_dequantize_weights',self.wrap(method_label('.embedding_dequant'),emb._dequantize_weights))
            patch(linear,'_dequantize_weights',self.wrap(method_label('.linear_dequant'),linear._dequantize_weights))
            patch(gemma_quant,'apply_srq',self.wrap('native.apply_srq',gemma_quant.apply_srq))
            patch(torch.nn.functional,'linear',self.wrap('torch.functional.linear',torch.nn.functional.linear))
            patch(torch,'matmul',self.wrap('torch.matmul',torch.matmul))
            for name,module in named:
                selected=(name in ('','model','model.language_model') or
                          type(module).__name__=='Gemma4DecoderLayer' or
                          isinstance(module,(linear,emb,torch.nn.Linear)))
                if not selected:continue
                had_instance='forward' in module.__dict__;previous=module.__dict__.get('forward')
                # Retrieving a bound method does not execute it. The wrapper
                # calls that original bound method once; no extra self binding.
                original=module.forward
                module.forward=self.wrap((name or '<root>')+'.forward',original)
                instance_forwards.append((module,had_instance,previous))
            yield self
        finally:
            for module,had_instance,previous in reversed(instance_forwards):
                if had_instance:module.forward=previous
                else:delattr(module,'forward')
            for owner,name,original in reversed(patches):setattr(owner,name,original)

    def close(self):
        try:self.file.close()
        except Exception as error:self.logging_error=f'{type(error).__name__}: {error}'
        return {'events':self.events,'bytes':self.bytes,'calls':self.calls,'logging_error':self.logging_error,
                'boundary':'Observation overhead included. Do not sum nested inclusive timings or overlapping process-CPU intervals as independent cost.'}
