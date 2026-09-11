#!/usr/bin/env python3
"""One CPU FP32 reference on the frozen QDQ-origin p1 pack; no QNN or export.

The candidate W4A16 route is NOT changed. This evaluates unquantized checkpoint
values promoted to FP32 against already-retained QDQ/QNN outputs on identical
external inputs. It is not an FP32-origin trajectory or an Android campaign.
"""
from __future__ import annotations
import argparse
import gc
import hashlib
import json
import os
from pathlib import Path
import resource
import sys
import time
import traceback


def pin(path):
    path=Path(path);h=hashlib.sha256()
    with path.open('rb') as f:
        while b:=f.read(1024*1024):h.update(b)
    return {'path':str(path.resolve()),'bytes':path.stat().st_size,'sha256':h.hexdigest()}


def check(record):
    actual=pin(record['path'])
    if any(actual[k]!=record[k] for k in ('bytes','sha256')):
        raise ValueError('Bound artifact changed: '+record['path'])
    return actual


def save(path,data):
    Path(path).write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')


def tensor_metrics(reference,actual):
    import torch
    if reference.shape!=actual.shape:
        raise ValueError('Comparison shape mismatch')
    finite=bool(torch.isfinite(reference).all() and torch.isfinite(actual).all())
    record={'shape':list(reference.shape),'finite':finite}
    if not finite:
        return dict(record,cosine=None,l2=None,max_abs=None,mean_abs=None,reason='nonfinite retained output')
    a=reference.reshape(-1).double();b=actual.reshape(-1).double();delta=b-a
    denominator=float(torch.linalg.vector_norm(a)*torch.linalg.vector_norm(b))
    return dict(record,cosine=float(torch.dot(a,b))/denominator if denominator else None,
                cosine_null_reason=None if denominator else 'zero vector norm',
                l2=float(torch.linalg.vector_norm(delta)),max_abs=float(delta.abs().max()),
                mean_abs=float(delta.abs().mean()),exact_equal_values=int((reference==actual).sum()))


def capture_hidden(model):
    """Read-only post-layer snapshots, matching compiler's hidden_states order."""
    captured=[]
    def hook(layer,args,output):
        captured.append(output[0].detach().clone())
        # Returning None is essential: do not replace a layer's outputs.
    handles=[layer.register_forward_hook(hook) for layer in model.layers]
    return captured,handles


def load_weights(model,adapter,checkpoint):
    """Copy into existing Parameters: assign=True would stale recurrence refs."""
    import torch
    state=adapter.adapt_converted_state_dict(torch.load(checkpoint,map_location='cpu',mmap=True,weights_only=True))
    dtypes={}
    for tensor in state.values():dtypes[str(tensor.dtype)]=dtypes.get(str(tensor.dtype),0)+1
    missing,unexpected=model.load_state_dict(state,strict=False)
    ignored=[name for name in unexpected if name.endswith(('.conv_state','.recurrent_state'))]
    unexpected=[name for name in unexpected if name not in ignored]
    if missing or unexpected:raise ValueError(f'Checkpoint mismatch: {missing=} {unexpected=}')
    del state;gc.collect()
    for layer in model.layers:
        if layer.is_linear:
            a=layer.attention
            if a.recurrence._a_log is not a.A_log or a.recurrence._dt_bias is not a.dt_bias:
                raise ValueError('Recurrence parameter identity changed')
    if any(p.dtype!=torch.float32 for p in model.parameters()):raise ValueError('Expected FP32 model parameters')
    return {'checkpoint_tensor_dtype_counts':dtypes,'ignored_state_templates':ignored,
            'parameter_elements':sum(p.numel() for p in model.parameters()),
            'parameter_bytes':sum(p.numel()*p.element_size() for p in model.parameters()),
            'loading':'copy into existing FP32 Parameters, no assign/meta replacement',
            'recurrence_parameter_identity_verified':True}


def compare_saved(reference,others):
    if len(reference)!=73 or any(len(x)!=73 for x in others.values()):raise ValueError('Expected 73-output reference ABI')
    result={}
    for name,actual in others.items():
        result[name]={'outputs':[tensor_metrics(a,b) for a,b in zip(reference,actual)],
                      'logits_argmax':int(actual[0].argmax()),'reference_argmax':int(reference[0].argmax())}
    return result


def run(request_path,output):
    import torch
    from types import SimpleNamespace
    from controlled_position1 import validate_inputs,values_digest
    from executorch.examples.models.llama.model_args import ModelArgs
    import qwen35_qnn_model as adapter
    request=json.loads(request_path.read_text());output.mkdir(parents=True,exist_ok=False)
    started=time.monotonic();hidden=[];handles=[]
    result={'status':'started','phase':'preflight','request':pin(request_path),'forward_started':False,
            'forward_returned':False,'maximum_model_forwards':1,'new_QNN_SDK_calls':0,'physical_execution':False}
    def record(phase):
        result['phase']=phase;result['elapsed_seconds']=time.monotonic()-started
        result['ru_maxrss_kib']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        save(output/'result.json',result);print(json.dumps({'phase':phase,'rss_high_water_kib':result['ru_maxrss_kib']}),flush=True)
    try:
        record('preflight')
        if resource.getrlimit(resource.RLIMIT_AS)[0]!=request['address_space_bytes'] or len(os.sched_getaffinity(0))!=4:
            raise ValueError('Worker resource contract not applied')
        torch.set_num_threads(4);torch.set_num_interop_threads(1);torch.set_grad_enabled(False)
        for rec in request['pins']:check(rec)
        header=json.loads(Path(request['pack_header']).read_text())
        params=json.loads(Path(request['params']).read_text());context=header['context']
        config=ModelArgs(max_seq_len=context,max_context_len=context,max_batch_size=1,use_kv_cache=True,**params)
        inputs=torch.load(header['input_pack']['path'],map_location='cpu',weights_only=True)
        ids=list(__import__('numpy').fromfile(request['token_ids'],dtype='<i4'))
        validate_inputs(inputs,SimpleNamespace(**params),ids,context)
        digest=values_digest(inputs)
        if digest!=header['input_values_sha256']:raise ValueError('Input pack logical digest changed')
        prior={}
        for name,path in request['prior_result_paths'].items():
            prior[name]=json.loads(Path(path).read_text())
            p=prior[name]
            if p['status']!='completed_single_call' or p['submitted_input_values_sha256']!=digest or p['input_mutation_observed']:
                raise ValueError('Historical backend call is not on the same input pack')
        result.update(input_values_sha256=digest,token_id=int(inputs[0]),position=int(inputs[2]),state_origin='QDQ after p0, not FP32-own trajectory',
                      input_tensors=len(inputs),runtime={'torch':torch.__version__,'python':sys.version,'threads':4,'interop':1,'backend':'CPU FP32 eager'})
        record('model_construct')
        t=time.monotonic();model=adapter.Qwen35QnnModel(config,context_len=context).eval()
        result['weight_load']=load_weights(model,adapter,request['checkpoint']);model.requires_grad_(False)
        result['model_construct_and_load_seconds']=time.monotonic()-t
        hidden,handles=capture_hidden(model)
        if values_digest(inputs)!=digest:raise ValueError('Input changed before forward')
        result['forward_started']=True;record('forward')
        t=time.monotonic()
        with torch.no_grad():values=model(*inputs)
        result['forward_seconds']=time.monotonic()-t;result['forward_returned']=True
        # Raw first, even if later ABI, finite-value or comparison checks fail.
        raw=[x.detach().cpu().contiguous() for x in (*values,*hidden)]
        torch.save(raw,output/'outputs.pt');result['raw_outputs']=pin(output/'outputs.pt');record('raw_saved')
        for h in handles:h.remove()
        handles=[]
        result['input_mutation_observed']=values_digest(inputs)!=digest
        if result['input_mutation_observed']:raise ValueError('Reference model mutated submitted inputs')
        if len(values)!=49 or len(hidden)!=24:raise ValueError('Expected 49 public outputs plus24 hidden taps')
        result['output_specs']=[{'shape':list(x.shape),'dtype':str(x.dtype),'finite':bool(torch.isfinite(x).all())} for x in raw]
        # Do not retain parameter RAM through saved-output analysis/post hashing.
        del model,values,inputs,hidden;hidden=[];gc.collect()
        record('saved_comparison')
        others={name:torch.load(r['raw_outputs']['path'],map_location='cpu',weights_only=True) for name,r in prior.items()}
        comparison=compare_saved(raw,others);save(output/'comparison.json',comparison)
        result['comparison']=pin(output/'comparison.json')
        result['FP32_logits_argmax']=int(raw[0].argmax())
        result['all_outputs_finite']=all(x['finite'] for x in result['output_specs'])
        record('postpins')
        result['postpins']=[check(rec) for rec in request['pins']]
        result['status']='completed_single_FP32_call'
        result['claim_limits']=['FP32 computation on the unchanged converted checkpoint values; not recovery of unknown higher-precision training weights.',
          'One current-call comparison on QDQ-origin history; not FP32-origin trajectory or generated-text quality.',
          'Saved full-model QNN comparison is x86 HtpProvider evidence, not this model on Android.',
          'Common external inputs do not imply identical per-layer internal inputs or identify a causal operator.',
          'No production quantization/artifact/runner change; no QDQ/QNN replay, export or calibration.']
        record('complete');return result
    except BaseException as error:
        for h in handles:h.remove()
        if hidden:
            torch.save(hidden,output/'partial-hidden.pt');result['partial_hidden']=pin(output/'partial-hidden.pt')
        result.update(status='error',error={'type':type(error).__name__,'message':str(error),'traceback':traceback.format_exc()})
        record(result['phase']);raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--request',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();run(args.request,args.output)
