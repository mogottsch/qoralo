#!/usr/bin/env python3
"""Isolated pinned native-QAT structural validation. No fallback computation.

Default mode is metadata/meta-device validation only. A CPU forward is added
only after the strict source schema passes; no generate() or device access.
"""
import argparse
from collections import Counter
import hashlib
import importlib.metadata
import json
from pathlib import Path
import re
import struct
import sys
import time

TRACK=Path(__file__).resolve().parents[1]
EXP=TRACK.parents[1]
ROOT=TRACK/'.local/native-qat-reference'
PIN='323f24345ed92f88e68a14aeef7db78ee2b52475'
SRC=ROOT/'source-323f2434-01/extracted'/('transformers-'+PIN)/'src'
DEPS=ROOT/'dependencies-01/site-packages'
CONFIG=TRACK/'.local/same-source-reference-readiness/source-20260912-01/config.json'
CONFIG_SHA='cf6d7dc22738b5e6beb364bac833d78b869f5a6ffd57dfc96c6be3f2abc80424'
QUANT_SHA='9bf6d109dfc3540a46953f5b183af766edcf6a044529c12d7751db47ee71cc17'
CHECKPOINT=EXP/'.local/hf-checkpoint/model.safetensors'
CHECKPOINT_SHA='efab429012b97ab986c4d4838a46ff3ad95d618b42ce514771ca40fadc76a9a4'
INPUT=TRACK/'.local/frozen-stages/aligned-gpu-20260912T094856Z-01/expected-input-ids.int32le'
INPUT_SHA='3b5c04febbc9d55c529ee7ece510607203dbdc8256a6abc05ba0498cf4e52b64'


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()


def in_scope(name):return name=='lm_head' or name.startswith(('model.language_model.','lm_head.'))


def header():
    with CHECKPOINT.open('rb') as f:
        n=struct.unpack('<Q',f.read(8))[0]
        if n>8*1024*1024:raise ValueError('unbounded safetensors header')
        data=f.read(n)
    return json.loads(data),hashlib.sha256(data).hexdigest()


def compare_schema(expected,source,ignore_patterns):
    wanted={k for k in expected if in_scope(k)};present={k for k in source if in_scope(k)}
    extras=sorted(present-wanted)
    native_unused={k:[p for p in ignore_patterns if re.search(p,k)] for k in extras}
    unsupported=[k for k,v in native_unused.items() if not v]
    mismatches=[];dtype_changes=[]
    for k in sorted(wanted&present):
        e,s=expected[k],source[k]
        if e['shape']!=s['shape']:mismatches.append({'name':k,'expected':e['shape'],'source':s['shape']})
        if s['dtype']!=e['dtype']:
            if s['dtype'] not in ('F32','BF16','F16') or e['dtype'] not in ('F32','BF16','F16'):
                mismatches.append({'name':k,'expected_dtype':e['dtype'],'source_dtype':s['dtype']})
            else:dtype_changes.append({'name':k,'source':s['dtype'],'native_applied':e['dtype']})
    missing=sorted(wanted-present)
    return {'passed':not(missing or unsupported or mismatches),'expected_text_head_keys':len(wanted),
      'source_text_head_keys':len(present),'missing':missing,'unaccounted_source_keys':unsupported,'shape_or_integer_dtype_mismatches':mismatches,
      'native_declared_unused_keys':native_unused,'floating_dtype_conversions':dtype_changes,
      'unused_boundary':'Only patterns declared by the exact native model/quantizer; cache scales are not applied by that native implementation. No keys are discarded by custom loader logic.'}


def setup():
    if sha(CONFIG)!=CONFIG_SHA or sha(SRC/'transformers/integrations/gemma_quant.py')!=QUANT_SHA:raise ValueError('pinned source/config changed')
    if sha(INPUT)!=INPUT_SHA:raise ValueError('effective input changed')
    sys.path[:0]=[str(SRC),str(DEPS)]
    import torch,transformers
    from transformers import Gemma4Config,Gemma4ForConditionalGeneration
    from transformers.quantizers.quantizer_gemma import GemmaQuantizer
    from transformers.utils.quantization_config import GemmaQuantizationConfig
    from transformers.utils.generic import ContextManagers
    from transformers.integrations.gemma_quant import QuantizedLinear,QuantizedEmbedding
    if not Path(transformers.__file__).resolve().is_relative_to(SRC):raise ValueError('un-pinned Transformers import')
    torch.set_num_threads(2);torch.set_num_interop_threads(1)
    config=Gemma4Config.from_dict(json.loads(CONFIG.read_text()))
    for c in (config,config.text_config,config.audio_config,config.vision_config):c.dtype=torch.bfloat16;c._attn_implementation='eager'
    quant=GemmaQuantizer(GemmaQuantizationConfig.from_dict(config.quantization_config),pre_quantized=True)
    with ContextManagers(Gemma4ForConditionalGeneration.get_init_context(torch.bfloat16,True,False,False)):
        model=Gemma4ForConditionalGeneration(config)
        quant.preprocess_model(model=model,dtype=torch.bfloat16,device_map={'':'cpu'},use_kernels=False)
    mapping={torch.float32:'F32',torch.bfloat16:'BF16',torch.float16:'F16',torch.uint8:'U8',torch.int8:'I8',torch.int64:'I64',torch.int32:'I32',torch.bool:'BOOL'}
    expected={k:{'shape':list(v.shape),'dtype':mapping[v.dtype]} for k,v in model.state_dict().items()}
    patterns=sorted(model._keys_to_ignore_on_load_unexpected or [])
    # This is a validation-schema correction, NOT a change to the model. The
    # pinned native quantized loader installs checkpoint-shaped parameters, and
    # QuantizedEmbedding already supports block-wise scales. Bind only this
    # known PLE shape; do not adopt arbitrary checkpoint shapes permissively.
    ple_key='model.language_model.embed_tokens_per_layer.embedding_scale'
    if expected[ple_key]['shape']!=[262144,1] or model.model.language_model.embed_tokens_per_layer.embedding_dim!=8960:raise ValueError('pinned PLE constructor changed')
    expected[ple_key]['constructor_shape']=[262144,1]
    expected[ple_key]['shape']=[262144,35]
    source,header_sha=header();validation=compare_schema(expected,source,patterns)
    validation['native_variable_shape_binding']={'key':ple_key,'constructor_shape':[262144,1],'checkpoint_loaded_shape':[262144,35],'block_width':256,'model_modified':False,'basis':'Pinned core_model_loading.set_param_for_module retains checkpoint shape for quantizers; native QuantizedEmbedding._dequantize_weights computes block_size=embedding_dim/scale_columns.'}
    modules={name:{'class':type(m).__name__,'num_bits':m.num_bits,'source_file':str(SRC/'transformers/integrations/gemma_quant.py')} for name,m in model.named_modules() if in_scope(name) and isinstance(m,(QuantizedLinear,QuantizedEmbedding))}
    validation.update(expected_state=expected,native_ignore_patterns=patterns,quant_modules=modules,quant_module_counts=dict(Counter((str(x['num_bits'])+'bit '+x['class']) for x in modules.values())),
      checkpoint_header_sha256=header_sha,input_ids_sha256=INPUT_SHA,input_ids_count=1929,attn_implementation=model.model.language_model.config._attn_implementation,
      runtime={'torch':torch.__version__,'transformers':transformers.__version__,'transformers_source':str(Path(transformers.__file__).resolve()),'packages':{k:importlib.metadata.version(k) for k in ['safetensors','tokenizers','accelerate','huggingface-hub','numpy']}})
    return validation


def execute(out,observe_cost=False):
    """Called once, only by the bounded host guard after metadata validation."""
    from contextlib import nullcontext
    import gc
    import os
    validation=json.loads((ROOT/'meta-validation-02/validation.json').read_text())
    if not validation['passed']:raise ValueError('metadata schema did not pass')
    source_header,header_sha=header()
    if header_sha!=validation['checkpoint_header_sha256']:raise ValueError('checkpoint header changed')
    if sha(CHECKPOINT)!=CHECKPOINT_SHA or sha(INPUT)!=INPUT_SHA or sha(CONFIG)!=CONFIG_SHA:raise ValueError('checkpoint/input/config binding changed')
    if sha(SRC/'transformers/integrations/gemma_quant.py')!=QUANT_SHA:raise ValueError('native quant implementation changed')
    sys.path[:0]=[str(SRC),str(DEPS)]
    import torch,transformers
    from safetensors import safe_open
    from transformers import Gemma4Config,Gemma4ForConditionalGeneration,GenerationConfig
    from transformers.integrations import gemma_quant
    torch.set_num_threads(2);torch.set_num_interop_threads(1)
    if not Path(transformers.__file__).resolve().is_relative_to(SRC):raise ValueError('wrong Transformers source')
    runtime={'torch':torch.__version__,'transformers':transformers.__version__,'source_revision':PIN,'dtype':'bfloat16','device':'cpu','attention':'eager','use_kernels':False,'threads':torch.get_num_threads(),'interop_threads':torch.get_num_interop_threads(),
      'packages':{k:importlib.metadata.version(k) for k in ['safetensors','tokenizers','accelerate','huggingface-hub','numpy']},'quant_implementation_sha256':QUANT_SHA,'checkpoint_sha256':CHECKPOINT_SHA,'config_sha256':CONFIG_SHA,'input_int32le_sha256':INPUT_SHA,'source_sha256':sha(Path(__file__))}
    generation_path=ROOT/'source-323f2434-01/generation_config.json'
    if sha(generation_path)!='fb53f4c64e58896a63472e8eb304397db4a39453e1da0f5d57625ec5a8c1050e':raise ValueError('native generation metadata changed')
    runtime['generation_config_sha256']=sha(generation_path)
    runtime['generation_config_used_only_for_loader_initialization']=True
    runtime['observation_only_cost_trace']=observe_cost
    runtime['cost_trace_source_sha256']=sha(Path(__file__).with_name('native_qat_cost_trace.py')) if observe_cost else None
    (out/'runtime-before-load.json').write_text(json.dumps(runtime,indent=2)+'\n')
    cfg=Gemma4Config.from_dict(json.loads(CONFIG.read_text()))
    generation=GenerationConfig.from_dict(json.loads(generation_path.read_text()))
    began=time.monotonic();model,info=Gemma4ForConditionalGeneration.from_pretrained(str(CHECKPOINT.parent),config=cfg,generation_config=generation,dtype=torch.bfloat16,device_map={'':'cpu'},attn_implementation='eager',use_kernels=False,local_files_only=True,output_loading_info=True)
    (out/'loading-info.json').write_text(json.dumps(info,indent=2,default=str)+'\n')
    mapping={torch.float32:'F32',torch.bfloat16:'BF16',torch.float16:'F16',torch.uint8:'U8',torch.int8:'I8',torch.int64:'I64',torch.int32:'I32',torch.bool:'BOOL'}
    actual=model.state_dict();checks=[];failures=[];scale_stats=[]
    if {k for k in actual if in_scope(k)}!={k for k in validation['expected_state'] if in_scope(k)}:failures.append({'issue':'loaded text/head key set differs from validated schema'})
    with safe_open(str(CHECKPOINT),framework='pt',device='cpu') as f:
        for key,e in validation['expected_state'].items():
            if not in_scope(key):continue
            value=actual.get(key)
            if value is None:failures.append({'key':key,'issue':'missing loaded tensor'});continue
            structural=list(value.shape)==e['shape'] and mapping[value.dtype]==e['dtype'] and value.device.type=='cpu'
            equal=structural and torch.equal(value,f.get_tensor(key).to(dtype=value.dtype))
            checks.append({'key':key,'shape':list(value.shape),'dtype':mapping[value.dtype],'device':str(value.device),'matches_source_at_native_dtype':bool(equal)})
            if not equal:failures.append({'key':key,'issue':'shape/dtype/device/source-value mismatch'})
            if key.endswith('_scale'):
                finite=bool(torch.isfinite(value).all());scale_stats.append({'key':key,'finite':finite,'nonzero':int(torch.count_nonzero(value)),'elements':value.numel()})
                if not finite:failures.append({'key':key,'issue':'nonfinite scale'})
    modules={n:m for n,m in model.named_modules() if in_scope(n) and isinstance(m,(gemma_quant.QuantizedLinear,gemma_quant.QuantizedEmbedding))}
    if set(modules)!=set(validation['quant_modules']):failures.append({'issue':'native quant module set changed'})
    for name,module in modules.items():
        expected=validation['quant_modules'][name]
        if type(module).__name__!=expected['class'] or module.num_bits!=expected['num_bits']:failures.append({'key':name,'issue':'native quant type/bit mismatch'})
    if model.model.language_model.config._attn_implementation!='eager':failures.append({'issue':'requested eager CPU attention not applied'})
    loaded={'passed':not failures,'failures':failures,'text_head_tensors':checks,'scale_validation':scale_stats,'native_quant_modules':validation['quant_modules'],'native_declared_unused_checkpoint_keys':validation['native_declared_unused_keys'],'seconds':time.monotonic()-began,'cache_scale_boundary':'The pinned native loader intentionally does not apply checkpoint cache scales; no custom quantized-cache implementation is substituted.'}
    (out/'load-validation.json').write_text(json.dumps(loaded,indent=2)+'\n')
    if failures:raise ValueError('strict loaded text/head validation failed; no forward')
    del actual,checks
    gc.collect()
    raw=INPUT.read_bytes();ids=list(struct.unpack('<1929i',raw));input_ids=torch.tensor([ids],dtype=torch.long,device='cpu')
    position_ids=torch.arange(1929,dtype=torch.long,device='cpu').unsqueeze(0);attention_mask=torch.ones_like(input_ids)
    (out/'input-ids.int32le').write_bytes(raw)
    (out/'forward-contract.json').write_text(json.dumps({'input_shape':[1,1929],'input_dtype':'int64','position_ids':'0..1928','attention_mask':'ones','use_cache':False,'logits_to_keep':1,'generation_calls':0,'allowed_forward_calls':1,'sampler_or_EOS_policy_applied':False},indent=2)+'\n')
    counts=Counter();srq=Counter();handles=[];original_srq=gemma_quant.apply_srq
    def count_module(name):
        def hook(module,inputs,output):counts[name]+=1
        return hook
    for name,module in modules.items():handles.append(module.register_forward_hook(count_module(name)))
    def observed_srq(x,scale,bits=8):
        srq['calls']+=1;srq['bits_'+str(bits)]+=1
        if bool(torch.any(scale!=0)):srq['calibrated_calls']+=1
        # The exact pinned native function computes and returns the result.
        return original_srq(x,scale,bits)
    gemma_quant.apply_srq=observed_srq
    cost_trace=None
    if observe_cost:
        from native_qat_cost_trace import CostTrace
        cost_trace=CostTrace(out/'native-operations.jsonl',tensor_type=torch.Tensor)
    cost_context=cost_trace.instrument(model,gemma_quant,torch) if cost_trace else nullcontext()
    model.eval();start=time.monotonic();(out/'forward-started.json').write_text(json.dumps({'monotonic':start,'forward_calls':1})+'\n')
    try:
        with cost_context,torch.inference_mode():
            output=model(input_ids=input_ids,attention_mask=attention_mask,position_ids=position_ids,use_cache=False,logits_to_keep=1,return_dict=True)
        elapsed=time.monotonic()-start;logits=output.logits.detach().contiguous()
        # Persist original bits and an explicitly labeled F32 view BEFORE analysis.
        native=logits.view(torch.uint16).numpy().tobytes() if logits.dtype==torch.bfloat16 else logits.numpy().tobytes()
        fp32=logits.float().numpy().tobytes()
        for name,data in [('last-logits.native.bin',native),('last-logits.float32.bin',fp32)]:
            with (out/name).open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
        capture={'shape':list(logits.shape),'original_dtype':str(logits.dtype),'native_sha256':hashlib.sha256(native).hexdigest(),'native_bytes':len(native),'float32_sha256':hashlib.sha256(fp32).hexdigest(),'float32_bytes':len(fp32),'seconds':elapsed,'forward_calls':1,'module_call_counts':dict(counts),'SRQ_calls':dict(srq),'raw_written_before_analysis':True}
        (out/'capture.json').write_text(json.dumps(capture,indent=2)+'\n')
        if list(logits.shape)!=[1,1,262144] or logits.dtype!=torch.bfloat16:raise ValueError('unexpected retained output shape/dtype')
        # One logical forward can legitimately look up the token embedding
        # twice (e.g. the native pad-embedding helper). Require coverage, not
        # an invented one-callback-per-module invariant.
        if set(counts)!=set(modules) or any(n<1 for n in counts.values()):raise ValueError('native quant module execution coverage incomplete')
        linear_calls=sum(counts[name] for name,m in modules.items() if isinstance(m,gemma_quant.QuantizedLinear))
        if srq['calls']<2*linear_calls or srq['calibrated_calls']==0 or srq['bits_8']!=srq['calls']:raise ValueError('native SRQ path not fully observed')
        flat=logits.float().flatten();finite=bool(torch.isfinite(flat).all())
        values,indices=torch.topk(flat,20)
        analysis={'finite':finite,'argmax_id':int(torch.argmax(flat)),'top20_ids':indices.tolist(),'top20_logits':values.tolist(),'min':float(flat.min()),'max':float(flat.max()),'QNN_w4a16_equivalence':False,'full_generation_quality_result':False}
        (out/'analysis.json').write_text(json.dumps(analysis,indent=2)+'\n')
        if not finite:raise ValueError('nonfinite retained logits')
        return {'passed':True,'classification':'one_native_qat_cpu_prefill_captured','model_forward_calls':1,'generation_calls':0,'adb_calls':0,'load_seconds':loaded['seconds'],'forward_seconds':elapsed,'argmax_id':analysis['argmax_id'],'capture':capture,'QNN_w4a16_equivalence':False,'full_generation_quality_result':False}
    finally:
        gemma_quant.apply_srq=original_srq
        if cost_trace:
            try:(out/'cost-trace-status.json').write_text(json.dumps(cost_trace.close(),indent=2)+'\n')
            except Exception:pass  # optional trace failure never substitutes model output
        for h in handles:h.remove()
        (out/'native-execution-observations.json').write_text(json.dumps({'module_calls':dict(counts),'SRQ_calls':dict(srq)},indent=2)+'\n')
        del model,modules
        gc.collect()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--execute',action='store_true');p.add_argument('--observe-cost',action='store_true');args=p.parse_args();out=args.output_dir.resolve()
    if not out.is_relative_to(ROOT):p.error('fresh owned private output required')
    out.mkdir(parents=True,exist_ok=False);start=time.monotonic()
    try:
        if args.execute:result=execute(out,observe_cost=args.observe_cost)
        else:
            validation=setup();(out/'validation.json').write_text(json.dumps(validation,indent=2)+'\n')
            result={'classification':'native_qat_meta_schema_validated' if validation['passed'] else 'native_qat_meta_schema_blocked','passed':validation['passed'],'seconds':time.monotonic()-start,'model_weights_loaded':False,'model_forward_calls':0,'adb_calls':0,'source_sha256':sha(Path(__file__))}
        (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
        return 0 if result['passed'] else 2
    except Exception as error:
        (out/'result.json').write_text(json.dumps({'passed':False,'error':repr(error),'seconds':time.monotonic()-start,'model_forward_calls':int((out/'forward-started.json').exists()),'raw_logits_present':(out/'last-logits.native.bin').exists(),'adb_calls':0},indent=2)+'\n');raise


if __name__=='__main__':raise SystemExit(main())
