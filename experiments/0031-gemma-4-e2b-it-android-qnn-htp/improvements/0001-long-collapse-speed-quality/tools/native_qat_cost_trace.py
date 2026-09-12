"""Observation-only streaming timings for a future explicitly scoped checkpoint.

Does not import/load a model or install patches on import. Calls the original
function once, returns the same object, and rethrows the original exception.
Only shapes/dtypes/devices are recorded, never tensor values. An event is
flushed before each call so the unfinished operation survives a process stop.
"""
from functools import wraps
import json
from pathlib import Path
import time


class CostTrace:
    def __init__(self,path,tensor_type,max_events=10000):
        self.path=Path(path)
        self.file=self.path.open('x',buffering=1)
        self.tensor_type=tensor_type
        self.max_events=max_events
        self.events=0
        self.calls=0
        self.logging_error=None

    def describe(self,value):
        if isinstance(value,self.tensor_type):
            return {'kind':'tensor','shape':list(value.shape),'dtype':str(value.dtype),'device':str(value.device)}
        # Never inspect a module's .weight property: quantized embedding .weight
        # can itself materialize an entire vocabulary table.
        if isinstance(value,(str,int,float,bool)) or value is None:return value
        return {'kind':type(value).__name__}

    def emit(self,row):
        if self.logging_error:return
        if self.events>=self.max_events:
            self.logging_error='trace event cap reached; model computation continues unchanged'
            return
        try:
            self.file.write(json.dumps(row,sort_keys=True)+'\n');self.file.flush();self.events+=1
        except Exception as error:
            self.logging_error=f'{type(error).__name__}: {error}'
            # This optional observation must never substitute or interrupt the
            # original computation after a costly forward has started.

    def wrap(self,label,original):
        @wraps(original)
        def observed(*args,**kwargs):
            self.calls+=1;call=self.calls
            name=label(*args,**kwargs) if callable(label) else label
            wall=time.monotonic_ns();cpu=time.process_time_ns()
            self.emit({'event':'begin','call':call,'operation':name,'monotonic_ns':wall,'process_cpu_ns':cpu,
                       'args':[self.describe(x) for x in args],'kwargs':{k:self.describe(v) for k,v in kwargs.items()}})
            try:
                result=original(*args,**kwargs)
            except BaseException as error:
                self.emit({'event':'error','call':call,'operation':name,'exception_type':type(error).__name__,
                           'wall_ns':time.monotonic_ns()-wall,'process_cpu_ns':time.process_time_ns()-cpu})
                raise
            self.emit({'event':'end','call':call,'operation':name,'wall_ns':time.monotonic_ns()-wall,
                       'process_cpu_ns':time.process_time_ns()-cpu,'output':self.describe(result)})
            return result
        return observed

    def close(self):
        self.file.close()
        return {'events':self.events,'calls':self.calls,'logging_error':self.logging_error,
                'boundary':'Instrumentation only. Native function/arguments/results are unchanged; timing overhead is not a speed result.'}
