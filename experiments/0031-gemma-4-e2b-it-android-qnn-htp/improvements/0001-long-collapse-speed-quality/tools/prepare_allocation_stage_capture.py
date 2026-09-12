#!/usr/bin/env python3
"""HOST-ONLY source preparation for fixed-stack allocation observations."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil

TRACK=Path(__file__).resolve().parents[1]
BASE=TRACK/'.local/paired-prefill-capture/build-01/sdk-source'
CPP='examples/Genie/Genie/src/qualla/'
EXPECTED={'encoders/text-encoders/LUT.cpp':'ff7a399f9c14fb20ba21495a2dc51f025d6f88a86148f85b7682ee38ae43bc0f','dialog.cpp':'baa2ff5b37431160b3d6526e009846f80272b75922f8a2ee3de24b476e5f0746','dialogs/basic.cpp':'186ef7ca56a72c1a711cebce0118e4a54985da00e2acf862b6a43d6dddc4a5d9'}


def change(text,old,new,count):
    if text.count(old)!=count:raise ValueError('allocation source anchor changed')
    result=text.replace(old,new)
    if result.replace(new,old)!=text:raise ValueError('noninvertible observation patch')
    return result


def patch_lut(source):
    out=source
    for expression,label in [('tokens.size() * embeddingSize','lut.vector.output'),('p_vec.size() * embeddingSize','lut.string.output')]:
        a='tokens.size()' if expression.startswith('tokens') else 'p_vec.size()'
        old=f'output.resize({expression});';new=f'gemma_alloc_trace::resize("{label}", output, {a}, embeddingSize, [&]() {{ {old} }});'
        out=change(out,old,new,1)
    return '#include "qualla/allocation_stage_trace.hpp"\n'+out


def patch_dialog(source):
    start=source.index('bool Dialog::query(const std::string& str, Sentence::Code scode, Dialog::Callback callback)')
    end=source.index('  std::vector<int32_t> p_vec;  // prompt tokens',start)
    region=source[start:end]
    for variable,width,label in [('decoderInput','inputBitWidth','decoder.main.resize'),('decoderPerLayerInput','inputPerLayerBitWidth','decoder.ple.resize')]:
        old=f'{variable}.resize(numElements * {width});'
        new=f'gemma_alloc_trace::resize("{label}", {variable}, numElements, {width}, [&]() {{ {old} }});'
        region=change(region,old,new,2)
    region=change(region,'bool status = _encoder->encode(str, encoderOutput, tokenizedInput);','bool status = gemma_alloc_trace::call("encoder.main.encode", [&]() { return _encoder->encode(str, encoderOutput, tokenizedInput); });',1)
    region=change(region,'status = _perlayer_encoder->encode(str, encoderPerLayerOutput, tokenizedPerLayerInput);','status = gemma_alloc_trace::call("encoder.ple.encode", [&]() { return _perlayer_encoder->encode(str, encoderPerLayerOutput, tokenizedPerLayerInput); });',1)
    old='return query(\n        decoderInput, decoderPerLayerInput, scode, t2eCallback, t2ePerLayerCallback, callback);'
    new='return gemma_alloc_trace::call("query.encoded_handoff", [&]() { return query(\n        decoderInput, decoderPerLayerInput, scode, t2eCallback, t2ePerLayerCallback, callback); });'
    region=change(region,old,new,1)
    return '#include "qualla/allocation_stage_trace.hpp"\n'+source[:start]+region+source[end:]


def patch_basic(source):
    out=source
    for variable,size,label in [('eosEmbedding','embedBufSize','basic.eos.main'),('eosPerLayerEmbedding','embedPerLayerBufSize','basic.eos.ple')]:
        old=f'std::vector<uint8_t> {variable}({size}, 0.0);'
        new=f'auto {variable} = gemma_alloc_trace::construct("{label}", {size}, sizeof(uint8_t), [&]() {{ return std::vector<uint8_t>({size}, 0.0); }});'
        out=change(out,old,new,1)
    old='engine.process(embedding_vectors, embedding_perlayer_vectors, {}, logits);'
    new='gemma_alloc_trace::scalar_call("basic.engine.process", [&]() { return engine.process(embedding_vectors, embedding_perlayer_vectors, {}, logits); });'
    out=change(out,old,new,1)
    return '#include "qualla/allocation_stage_trace.hpp"\n'+out


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()


def prepare(out):
    base_result=json.loads((BASE.parent/'build-result.json').read_text())
    if base_result['actual_native_exit']!=0 or base_result['binary_sha256']!='3a61a7ea888e39b54999c25b0644ff068733c343cb693e5eafee9be4538dccc2':raise ValueError('frozen capture-runtime base mismatch')
    for name,expected in EXPECTED.items():
        if sha(BASE/(CPP+name))!=expected:raise ValueError('bound allocation source changed '+name)
    files=[Path(parent)/name for parent,_,names in os.walk(BASE,followlinks=True) for name in names if (Path(parent)/name).is_file()]
    if sum(f.stat().st_size for f in files)>2*1024**3 or shutil.disk_usage(TRACK).free<72*1024**3:raise ValueError('bounded copy/disk headroom')
    out.mkdir(parents=True,exist_ok=False);target=out/'sdk-source';shutil.copytree(BASE,target,symlinks=False);bindings=[]
    for name,fn in [('encoders/text-encoders/LUT.cpp',patch_lut),('dialog.cpp',patch_dialog),('dialogs/basic.cpp',patch_basic)]:
        rel=CPP+name;old=(BASE/rel).read_text();new=fn(old);(target/rel).write_text(new);bindings.append({'path':rel,'before':sha(BASE/rel),'after':sha(target/rel)})
    header=target/(CPP+'include/qualla/allocation_stage_trace.hpp');shutil.copyfile(TRACK/'tools/allocation_stage_trace.hpp',header);bindings.append({'path':str(header.relative_to(target)),'before':None,'after':sha(header)})
    result={'classification':'allocation_observer_source_only','changes':bindings,'model_or_phone_executed':False,'source_original_allocations_called_once':True,'original_allocation_expressions_and_call_order_retained':True,'failure_logger':'fixed arrays/manual integer formatting/open/read/write/getrlimit; no allocator interception, JSON or heap strings','errno':'saved immediately at original exception before diagnostics; errno-at-observation, not proof malloc set it','diagnostic_multiplication':'overflow checked separately; original allocation expressions unchanged','caps_changed':False,'allocation_log_cap_bytes':65536,'allocation_log_cap_events':64}
    (out/'preparation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args();out=a.output_dir.resolve()
    if not out.is_relative_to(TRACK/'.local/paired-allocation-observer'):p.error('owned fresh private output required')
    prepare(out)


if __name__=='__main__':main()
