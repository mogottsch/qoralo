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


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True);args=p.parse_args();out=args.output_dir.resolve()
    if not out.is_relative_to(ROOT):p.error('fresh owned private output required')
    out.mkdir(parents=True,exist_ok=False);start=time.monotonic()
    try:
        validation=setup();(out/'validation.json').write_text(json.dumps(validation,indent=2)+'\n')
        result={'classification':'native_qat_meta_schema_validated' if validation['passed'] else 'native_qat_meta_schema_blocked','passed':validation['passed'],'seconds':time.monotonic()-start,'model_weights_loaded':False,'model_forward_calls':0,'adb_calls':0,'source_sha256':sha(Path(__file__))}
        (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
        return 0 if validation['passed'] else 2
    except Exception as error:
        (out/'result.json').write_text(json.dumps({'passed':False,'error':repr(error),'seconds':time.monotonic()-start,'model_forward_calls':0,'adb_calls':0},indent=2)+'\n');raise


if __name__=='__main__':raise SystemExit(main())
