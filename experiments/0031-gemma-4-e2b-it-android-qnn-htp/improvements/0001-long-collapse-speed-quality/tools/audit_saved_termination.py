#!/usr/bin/env python3
"""Bounded saved/source audit. No model execution, runtime load or ADB.

Reads only an identity-checked model's small metadata section; the whole file is
stream-hashed, never interpreted as executable/model inference. No stop/BOS
setting is changed. Missing actual QNN sampled IDs remain explicitly unknown.
"""
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct

TRACK = Path(__file__).resolve().parents[1]
EXP = TRACK.parents[1]
REPO = EXP.parents[1]
REFERENCE = REPO/'experiments/0025-gemma-4-e2b-it-android'
SDK = Path('/home/moritz/opt/qairt/2.49.40.260810')
RESULT = TRACK/'results/termination-template-sampler-audit-01'
STAGE = TRACK/'.local/frozen-stages/value-path-long-20260911T125353Z-01'
MODEL_SHA = '181938105e0eefd105961417e8da75903eacda102c4fce9ce90f50b97139a63c'


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for data in iter(lambda: stream.read(1024*1024), b''): digest.update(data)
    return digest.hexdigest()


def varint(data, pos):
    value = shift = 0
    while pos < len(data) and shift < 70:
        byte = data[pos]; pos += 1
        value |= (byte & 127) << shift
        if not byte & 128: return value, pos
        shift += 7
    raise ValueError('invalid bounded protobuf varint')


def fields(data):
    pos = 0
    while pos < len(data):
        tag,pos = varint(data,pos); number,wire = tag>>3,tag&7
        if not number: raise ValueError('invalid field zero')
        if wire == 0:
            value,pos = varint(data,pos)
        elif wire == 2:
            length,pos = varint(data,pos)
            if pos+length > len(data): raise ValueError('truncated field')
            value=data[pos:pos+length];pos+=length
        elif wire in (1,5):
            length=8 if wire==1 else 4
            if pos+length > len(data): raise ValueError('truncated fixed field')
            value=data[pos:pos+length];pos+=length
        else: raise ValueError('unsupported metadata wire type')
        yield number,wire,value


def token_union(data):
    nested = [v for n,w,v in fields(data) if n==1 and w==2]
    if len(nested)!=1: raise ValueError('expected token_ids union')
    values=[]
    for n,w,v in fields(nested[0]):
        if n!=1: continue
        if w==0: values.append(v)
        elif w==2:
            pos=0
            while pos<len(v): number,pos=varint(v,pos);values.append(number)
        else: raise ValueError('invalid token_ids encoding')
    return values


def load_runner(path):
    objects=[]
    for line in path.read_text().splitlines():
        try: obj=json.loads(line)
        except ValueError: continue
        if isinstance(obj,dict) and 'prompts' in obj and 'runs' in obj: objects.append(obj)
    if len(objects)!=1: raise ValueError('expected one retained runner result')
    return objects[0]


def main():
    RESULT.mkdir(parents=True,exist_ok=False)
    model=REFERENCE/'.local/model/gemma-4-E2B-it.litertlm'
    if sha(model)!=MODEL_SHA: raise ValueError('accepted generic LiteRT model changed')
    # Bounds from the retained container peek; validate against the checked file
    # and parse token-union fields using the pinned schema rather than text grep.
    with model.open('rb') as stream: stream.seek(16384); metadata=stream.read(28576-16384)
    model_fields=list(fields(metadata))
    starts=[token_union(v) for n,w,v in model_fields if n==1 and w==2]
    stops=[token_union(v) for n,w,v in model_fields if n==2 and w==2]
    assert starts==[[2]] and stops==[[1],[50],[106]]
    tokenizer=json.loads((STAGE/'tokenizer.json').read_text())
    names={item['id']:item['content'] for item in tokenizer['added_tokens'] if item['id'] in (1,2,50,105,106)}
    config=json.loads((STAGE/'gemma4-e2b-htp-cl4096-greedy.json').read_text())
    qat=EXP/'.local/checkpoint/extracted/gemma_4_e2b_it_w4a16/generation_config.json'
    upstream=REFERENCE/'.local/upstream/base/generation_config.json'
    qnn_ids={}
    for tier in ['short','medium','long']:
        data=(EXP/f'protocol/token-ids/{tier}.int32le').read_bytes()
        qnn_ids[tier]=list(struct.unpack('<'+'i'*(len(data)//4),data))
    routes={}
    sources=[model,qat,upstream,STAGE/'tokenizer.json',STAGE/'gemma4-e2b-htp-cl4096-greedy.json',
        REFERENCE/'tools/litert_lm_canonical_runner.cc',EXP/'tools/prepare_runtime_bundle.py',
        REFERENCE/'.local/LiteRT-LM/runtime/proto/token.proto',
        REFERENCE/'.local/LiteRT-LM/runtime/proto/llm_metadata.proto',
        REFERENCE/'.local/LiteRT-LM/runtime/engine/engine_settings.cc',
        REFERENCE/'.local/LiteRT-LM/runtime/core/tasks.cc']
    for route in ['android-cpu-campaign','android-gpu-campaign']:
        root=REFERENCE/'results'/route
        report=json.loads((root/'result.json').read_text()); raw_path=root/'raw/runner-stdout.jsonl'
        raw=load_runner(raw_path);sources += [root/'result.json',raw_path]
        assert report['artifact_identity']['model_sha256']==MODEL_SHA
        tiers={}
        for tier in ['short','medium','long']:
            ids=raw['prompts'][tier]['token_ids']; reference_text=root/f'rendered/{tier}.txt';qnn_text=EXP/f'protocol/rendered/{tier}.txt'
            sources += [reference_text,qnn_text,EXP/f'protocol/token-ids/{tier}.int32le']
            tiers[tier]={'same_rendered_bytes':reference_text.read_bytes()==qnn_text.read_bytes(),
                'rendered_sha256':sha(reference_text),'reference_count':len(ids),'qnn_count':len(qnn_ids[tier]),
                'reference_prefix':ids[:4],'qnn_prefix':qnn_ids[tier][:4],
                'entire_reference_equals_extra_BOS_then_QNN':ids==[2]+qnn_ids[tier]}
        longs=[]
        for run in raw['runs']:
            if run.get('tier')!='long':continue
            ids=run['emitted_token_ids']
            longs.append({'id':run['id'],'filtered_callback_count':len(ids),
                'runtime_generated_tokens':run['runtime_generated_tokens'],
                'callback_stop_id_counts':{str(i):ids.count(i) for i in [1,50,106]},
                'stop_reason_classification':run['stop_reason'],'task_state':run['runtime_task_state'],
                'terminating_sampled_id':None,
                'limitation':'These are filtered callback IDs. Matching stop tokens are withheld by runtime stop detection; the absent terminating ID is not established by decoded text or this callback list.'})
        routes[route]={'model_sha256':MODEL_SHA,'runtime':report['runtime'],'route':report['route'],
                       'input_comparison':tiers,'long_actual_callback_evidence':longs}
    log=TRACK/'.local/value-precision-phone-long-runs/value-long-20260911T130755Z-01/raw/device/genie-verbose.log'
    runtime_lines={}
    with log.open() as stream:
        for number,line in enumerate(stream,1):
            for key,needle in [('context','ctx-new: dialog0 config '),('sampler','sampler-new: basic ctx dialog0 config ')]:
                if needle in line and key not in runtime_lines:
                    runtime_lines[key]={'line':number,'text':line.rstrip(),'json':json.loads(line.split(needle,1)[1])}
            if len(runtime_lines)==2:break
    assert runtime_lines['context']['json']['eos-token']==[1,106]
    sdk_sources={
        'qualla/context.cpp':[30,50], 'qualla/include/qualla/context.hpp':[35,42],
        'qualla/dialogs/basic.cpp':[740,795], 'qualla/sampler.cpp':[174,213],
        'DebugConfig.hpp':[15,62], 'qualla/engines/qnn-htp/nsp-graph.hpp':[207,226],
        'qualla/engines/qnn-htp/nsp-graph.cpp':[431,507],
        'qualla/engines/qnn-htp/nsp-model.cpp':[4352,4381]}
    refs={name:{'path':str(SDK/'examples/Genie/Genie/src'/name),'sha256':sha(SDK/'examples/Genie/Genie/src'/name),'lines':span} for name,span in sdk_sources.items()}
    result={'classification':'saved_source_termination_template_sampler_audit',
        'model_metadata':{'accepted_model_sha256':MODEL_SHA,'offset':16384,'bytes':len(metadata),
            'section_sha256':hashlib.sha256(metadata).hexdigest(),'start_ids':starts,'stop_sequences':stops},
        'qnn_context':config['dialog']['context'],'qnn_sampler':config['dialog']['sampler'],
        'qnn_actual_runtime_config_lines':runtime_lines,
        'qat_generation_eos_ids':json.loads(qat.read_text())['eos_token_id'],
        'upstream_generation_eos_ids':json.loads(upstream.read_text())['eos_token_id'],
        'special_token_names':names,'stop_ids_missing_from_qnn':[50],
        'missing_token_semantics':'50 is <|tool_response>, not the ordinary <turn|> end marker106, which QNN already recognizes.',
        'actual_qnn_sampled_id_stream_retained':False,'actual_missed_token50_observed':None,
        'qnn_evidence_limit':'Retained decoded output, counts, input-ID prefix and partial logits do not expose the selected-token stream. No absence/occurrence assertion is inferred by output retokenization.',
        'reference_routes':routes,
        'sampler_assessment':'QNN greedy fast path uses direct argmax; LiteRT uses CPU TOP_P(k=1,p=1,temp=1), an argmax-equivalent singleton candidate. Temperature/seed configuration differs but does not establish stochastic sampling on these routes.',
        'source_refs':refs,'sources':[{'path':str(p),'sha256':MODEL_SHA if p==model else sha(p)} for p in sorted(set(sources))],
        'model_or_runtime_executed':False,'phone_access':False,'termination_or_input_changed':False,
        'negative_candidate_unchanged':True,
        'next_discriminator':'Capture actual selected IDs and applied EOS membership before stop/text filtering, with unchanged candidate/input/termination/sampler. This can test whether50 is actually missed. Do not add a stop or a BOS as a purported fix from decoded-text evidence. Address the independently proven extra-BOS reference confound explicitly before matched-route causal comparisons.'}
    (RESULT/'result.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    (RESULT/'sources').mkdir();shutil.copyfile(Path(__file__),RESULT/'sources/audit_saved_termination.py')
    for name,path in [('qat-generation-config.json',qat),('upstream-generation-config.json',upstream)]:shutil.copyfile(path,RESULT/'sources'/name)
    print(json.dumps({'result':str(RESULT/'result.json'),'sha256':sha(RESULT/'result.json'),
                      'missing_stop_id':50,'actual_missed_id_evidence':None}))


if __name__=='__main__':main()
