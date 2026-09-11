#!/usr/bin/env python3
"""Two weight-only CPU ablations; FP32 activations, no QNN/candidate claim."""
import argparse
import gc
import json
import os
from pathlib import Path
import resource
import time
import traceback

from compare_fp32_position1 import pin,check,save,load_weights,capture_hidden,compare_saved

EPS=0.0001/65535


def reconstruct_weight(weight,mode):
    """Source-derived W4 reconstruction, not a finalized native encoding capture.

LPBQ retains framework codes from original block scales. Native submission
rounds each scale to 1..16 multiples of max(block scale)/16 per output row.
Depthwise Conv remains per-channel (its input-channel dimension is1).
"""
    import torch
    if mode not in ('per_channel','lpbq32'):raise ValueError('Unknown ablation')
    if weight.dtype!=torch.float32:raise ValueError('Expected unchanged weights promoted to FP32')
    original_shape=weight.shape
    if mode=='lpbq32' and weight.ndim==2:
        if weight.shape[1]%32:raise ValueError('No silent padding/remainder grouping')
        view=weight.reshape(weight.shape[0],-1,32)
        scales=(view.abs().amax(dim=-1)/7).clamp_min(EPS)
        codes=torch.round(view*(1/scales[...,None])).clamp(-7,7).to(torch.int8)
        base=scales.amax(dim=1,keepdim=True)/16
        scale_codes=torch.round(scales/base).clamp(1,16).to(torch.uint8)
        expanded=base*scale_codes.float()
        reconstructed=(codes.float()*expanded[...,None]).reshape(original_shape)
    else:
        view=weight.reshape(weight.shape[0],-1)
        scales=(view.abs().amax(dim=1)/7).clamp_min(EPS)
        codes=torch.round(view*(1/scales[:,None])).clamp(-7,7).to(torch.int8)
        reconstructed=(codes.float()*scales[:,None]).reshape(original_shape)
    return reconstructed


def quantize_model(model,mode):
    import torch
    records=[]
    with torch.no_grad():
        for name,module in model.named_modules():
            if not isinstance(module,(torch.nn.Linear,torch.nn.Conv2d)):continue
            weight=module.weight;elements=weight.numel();sse=0.;max_abs=0.;zeros=0
            for first in range(0,weight.shape[0],128):
                original=weight[first:first+128]
                reconstructed=reconstruct_weight(original,mode)
                delta=reconstructed.double()-original.double()
                sse+=float((delta*delta).sum());max_abs=max(max_abs,float(delta.abs().max()))
                zeros+=int((reconstructed==0).sum());original.copy_(reconstructed)
            records.append({'module':name,'shape':list(weight.shape),'elements':elements,'weight_error_sse':sse,'max_abs':max_abs,'zero_elements':zeros,
                            'granularity':'block32_LPBQ_source_expansion' if mode=='lpbq32' and weight.ndim==2 else 'per_output_channel'})
    return records


def run(request_path,out):
    import torch
    import numpy as np
    from types import SimpleNamespace
    import qwen35_qnn_model as adapter
    from controlled_position1 import validate_inputs,values_digest
    from executorch.examples.models.llama.model_args import ModelArgs
    request=json.loads(request_path.read_text());out.mkdir(parents=True,exist_ok=False);started=time.monotonic()
    result={'status':'started','kind':'CPU_weight_only_diagnostic_FP32_activations','request':pin(request_path),'calls_started':0,'calls_returned':0,
            'maximum_forward_calls':2,'QNN_calls':0,'phone_calls':0,'cases':[]}
    def checkpoint(phase):
        result.update(phase=phase,elapsed_seconds=time.monotonic()-started,ru_maxrss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        save(out/'result.json',result);print(json.dumps({'phase':phase,'calls_returned':result['calls_returned']}),flush=True)
    try:
        if resource.getrlimit(resource.RLIMIT_AS)[0]!=request['address_space_bytes'] or len(os.sched_getaffinity(0))!=4:raise ValueError('Resource envelope missing')
        torch.set_num_threads(4);torch.set_num_interop_threads(1);torch.set_grad_enabled(False)
        for r in request['pins']:check(r)
        h=json.loads(Path(request['pack_header']).read_text());params=json.loads(Path(request['params']).read_text())
        inputs=torch.load(h['input_pack']['path'],map_location='cpu',weights_only=True)
        validate_inputs(inputs,SimpleNamespace(**params),np.fromfile(request['token_ids'],dtype='<i4'),h['context'])
        digest=values_digest(inputs)
        if digest!=h['input_values_sha256']:raise ValueError('Wrong input pack')
        reference=torch.load(request['fp32_outputs'],map_location='cpu',weights_only=True)
        config=ModelArgs(max_seq_len=h['context'],max_context_len=h['context'],max_batch_size=1,use_kv_cache=True,**params)
        checkpoint('model_construct');model=adapter.Qwen35QnnModel(config,context_len=h['context']).eval();model.requires_grad_(False)
        for mode in request['cases']:
            case={'mode':mode,'status':'started','activations':'FP32, no activation QDQ','embedding_norm_and_other_parameters':'unchanged promoted checkpoint values'}
            result['cases'].append(case);checkpoint(mode+':restore_original_weights')
            case['loading']=load_weights(model,adapter,request['checkpoint'])
            case_start=time.monotonic();case['quantized_modules']=quantize_model(model,mode)
            case['weight_transform_seconds']=time.monotonic()-case_start
            hidden,handles=capture_hidden(model)
            if values_digest(inputs)!=digest:raise ValueError('Inputs changed before ablation')
            result['calls_started']+=1;checkpoint(mode+':forward');t=time.monotonic()
            try:outputs=model(*inputs)
            finally:
                for handle in handles:handle.remove()
            case['forward_seconds']=time.monotonic()-t;result['calls_returned']+=1
            raw=[x.detach().contiguous().cpu() for x in (*outputs,*hidden)]
            path=out/(mode+'.outputs.pt');torch.save(raw,path);case['raw_outputs']=pin(path);checkpoint(mode+':raw_saved')
            case['input_values_sha256']=values_digest(inputs)
            if case['input_values_sha256']!=digest:raise ValueError('Ablation mutated inputs')
            case['all73_finite']=len(raw)==73 and all(bool(torch.isfinite(x).all()) for x in raw)
            comparison=compare_saved(reference,{mode:raw})[mode];save(out/(mode+'.comparison.json'),comparison)
            case['comparison']=pin(out/(mode+'.comparison.json'));case['status']='completed'
            del raw,outputs,hidden;gc.collect()
        del model,inputs,reference;gc.collect();checkpoint('postpins')
        result['postpins']=[check(r) for r in request['pins']]
        result.update(status='completed_two_weight_only_calls',limits=[
          'FP32 activations and unquantized embedding/norm/constants: neither case is a deployed W4A16 route.',
          'LPBQ32 is reconstruction from frontend weight codes plus submitted scale expansion; not observed finalized native weights.',
          'Same QDQ-origin p1 history, not FP32-own trajectory; two calls are not generated-text or campaign validation.',
          'No production weights/artifacts modified; each case restores original checkpoint values in the one private CPU model.'])
        checkpoint('complete')
    except BaseException as error:
        result.update(status='error',error={'type':type(error).__name__,'message':str(error),'traceback':traceback.format_exc()});checkpoint(result.get('phase','preflight'));raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--request',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.request,a.output)
