#!/usr/bin/env python3
"""Prepare an isolated observer-only Genie derivative; no build or device execution."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil

TRACK=Path(__file__).resolve().parents[1]
BASE=TRACK/'.local/selected-id-trace-runs/trace-build-20260911T142946Z-04/sdk-source'
REL='examples/Genie/Genie/src/qualla/engines/qnn-htp/nsp-model.cpp'
EXPECTED='59f71750b92f13dfa797bfad009ebe7b633ae450a7b8eec0ff011ef1e2287f65'

INPUT_HOOK=r'''
  // GEMMA_PAIRED_PREFILL_INPUT_CAPTURE_V1: read-only, after all input preparation.
  try {
    if (step.variant == 128 && step.ctx_size == 4096 && step.n_past >= 0 &&
        step.n_past <= 1920 && step.n_past % 128 == 0) {
      auto* capture_graph = m_nsp_graphs.front()(step.variant, step.ctx_size);
      const char* names[] = {"inputs_embeds", "per_layer_inputs", "attention_mask",
                            "swa_attention_mask", "position_ids_cos", "position_ids_sin",
                            "swa_position_ids_cos", "swa_position_ids_sin"};
      for (const char* name : names) {
        auto* tensor = capture_graph->getInput(name);
        if (!tensor) { gemma_prefill_capture::state().error("missing non-cache input"); break; }
        const uint32_t rank = QNN_TENSOR_GET_RANK(tensor->tensor);
        const uint32_t* dims = QNN_TENSOR_GET_DIMENSIONS(tensor->tensor);
        const auto qp = tensor->quantParam[0];
        gemma_prefill_capture::Json metadata = {
          {"variant", step.variant}, {"context", step.ctx_size}, {"n_past", step.n_past},
          {"n_process", step.n_process}, {"n_valid_kv", step.n_valid_kv},
          {"past_idx", step.past_idx}, {"new_idx", step.new_idx},
          {"buffer_idx", buffer_idx}, {"shape", std::vector<uint32_t>(dims, dims + rank)},
          {"datatype", tensor->dtype.str()}, {"scale", qp.scale}, {"offset", qp.offset},
          {"cache_tensor", false}};
        gemma_prefill_capture::save("input", step.n_past / 128, name,
            getBuffer(tensor, true, buffer_idx),
            tensor->dims.getNumElements() * tensor->dtype.bw(), std::move(metadata));
      }
    }
  } catch (...) {
    std::fprintf(stderr, "GEMMA_PREFILL_CAPTURE_ERROR input-hook exception\n");
  }
'''
OUTPUT_HOOK=r'''
  // GEMMA_PAIRED_PREFILL_LOGIT_CAPTURE_V1: last valid row, before Tensor/sampler access.
  try {
    if (step.variant == 128 && step.ctx_size == 4096 && step.n_past == 1920 &&
        step.n_process == 9 && count == 1) {
      gemma_prefill_capture::Json metadata = {
        {"variant", step.variant}, {"context", step.ctx_size}, {"n_past", step.n_past},
        {"n_process", step.n_process}, {"final_valid_row", step.n_process - count},
        {"shape", std::vector<uint32_t>{1, 1, static_cast<uint32_t>(m_vocab_size)}},
        {"datatype", spec->dtype.str()}, {"scale", scale}, {"offset", offset},
        {"before_sampler_access", true}, {"cache_tensor", false}};
      gemma_prefill_capture::save("output", 15, "logits", logit_buffer,
                                  size * bitwidth, std::move(metadata));
    }
  } catch (...) {
    std::fprintf(stderr, "GEMMA_PREFILL_CAPTURE_ERROR output-hook exception\n");
  }
'''


def patch(source):
    include='#include "qualla/prefill_capture.hpp"\n'
    # Exact original boundaries: only add observation, retain every original line.
    marker='  return true;\n}\n\nbool QnnNspModel::setupInput(const InferenceStep& step,\n                             uint32_t start,\n                             std::vector<int32_t>& tokens,\n                             std::vector<size_t>& tokenNumPerBatch,'
    output='  const size_t size = m_vocab_size * static_cast<size_t>(count);\n  __TRACE("qnn-htp: getLogits Returning {}*{} from [{}]", count, m_vocab_size, step.str());\n'
    if source.count(marker)!=1 or source.count(output)!=1:raise ValueError('frozen source anchors changed')
    result=include+source.replace(marker,INPUT_HOOK+marker).replace(output,output+OUTPUT_HOOK)
    restored=result.removeprefix(include).replace(INPUT_HOOK,'').replace(OUTPUT_HOOK,'')
    if restored!=source:raise ValueError('non-observer source delta')
    return result


def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()


def freeze_stage(stage):
    from prepare_frozen_genie_stage import copy_bound,write_input,verify
    base=TRACK/'.local/frozen-stages/selected-id-long-20260911T143756Z-01'
    build=TRACK/'.local/paired-prefill-capture/build-01'
    result=json.loads((build/'build-result.json').read_text())
    if result['actual_native_exit']!=0:raise ValueError('successful native build required')
    source=json.loads((base/'frozen-manifest.json').read_text());stage.mkdir(parents=True,exist_ok=False,mode=0o700);files={}
    for name,identity in source['files'].items():
        if name in {'lib/libGenie.so','gemma4-e2b-htp-cl4096-greedy.json','exact-long.script'}:continue
        files[name]=copy_bound(base/name,stage/name,identity)
    binary=Path(result['binary']);files['lib/libGenie.so']=copy_bound(binary,stage/'lib/libGenie.so',{'sha256':result['binary_sha256'],'bytes':result['binary_bytes']})
    cfg=json.loads((base/'gemma4-e2b-htp-cl4096-greedy.json').read_text());cfg['dialog']['max-num-tokens']=1
    files['gemma4-e2b-htp-cl4096-greedy.json']=write_input(stage/'gemma4-e2b-htp-cl4096-greedy.json',(json.dumps(cfg,indent=2)+'\n').encode())
    text=(base/'exact-long.script').read_text()
    if text.count('dialog setMaxNumTokens dialog1 2048')!=1:raise ValueError('exact one request cap anchor required')
    text=text.replace('dialog setMaxNumTokens dialog1 2048','dialog setMaxNumTokens dialog1 1')
    files['exact-long.script']=write_input(stage/'exact-long.script',text.encode())
    manifest=dict(source);manifest.update(classification='frozen_paired_prefill_capture_stage',stage_id=stage.name,files=files,payload_bytes=sum(x['bytes'] for x in files.values()),base_output_ceiling=1,phone_authorized=False,model_loaded=False,runtime_loaded=False,adb_used=False)
    manifest['diagnostic']={'queries':1,'input_tokens':1929,'AR128_chunks':16,'final_real_rows':9,'max_output_tokens':1,'AR1_continuation_allowed':False,'capture_before_sampler':True,'capture_noncache_inputs_only':True,'source_request':'new paired-prefill diagnostic; canonical2048 campaign unchanged'}
    manifest['capture_build']=result;manifest['copy_policy']='Independent copies; only observer library and both max-output cap controls changed. No model/LUT/input/context changes.'
    manifest['trace_runtime']={**source['trace_runtime'],'libGenie_sha256':result['binary_sha256'],'original_selected_trace_build_is_base_only':True,'new_capture_before_sampler':True}
    write_input(stage/'frozen-manifest.json',(json.dumps(manifest,indent=2,sort_keys=True)+'\n').encode());digest=sha(stage/'frozen-manifest.json')
    write_input(stage/'SHA256SUMS',(''.join(f'{v["sha256"]}  {k}\n' for k,v in sorted(files.items()))+f'{digest}  frozen-manifest.json\n').encode());verify(stage,digest)
    return {'stage':str(stage),'manifest_sha256':digest,'files':len(files),'bytes':manifest['payload_bytes'],'model_or_phone_executed':False}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args();out=a.output_dir.resolve()
    if not out.is_relative_to(TRACK/'.local/paired-prefill-capture'):p.error('owned fresh private output required')
    if sha(BASE/REL)!=EXPECTED:raise ValueError('frozen nsp source changed')
    # copytree materializes the bound SDK include-directory symlink too.
    files=[Path(parent)/name for parent,_,names in os.walk(BASE,followlinks=True) for name in names if (Path(parent)/name).is_file()]
    if sum(f.stat().st_size for f in files)>2*1024**3 or shutil.disk_usage(TRACK).free<72*1024**3:raise ValueError('copy/disk budget')
    out.mkdir(parents=True,exist_ok=False);target=out/'sdk-source';shutil.copytree(BASE,target,symlinks=False)
    source=(BASE/REL).read_text();(target/REL).write_text(patch(source));header=target/'examples/Genie/Genie/src/qualla/include/qualla/prefill_capture.hpp';shutil.copyfile(TRACK/'tools/prefill_capture.hpp',header)
    changes=[{'path':REL,'before':EXPECTED,'after':sha(target/REL)},{'path':str(header.relative_to(target)),'before':None,'after':sha(header)}]
    receipt={'classification':'observer_only_Genie_source_prepared','source_base':str(BASE),'source_build_commit':'2bcb58f0f25bc642ae731081dcab4149a77f01c7','changed_sources':changes,'base_file_count':len(files),'native_computation_lines_preserved':True,'model_executed':False,'phone_used':False,'new_input_capture_set':['inputs_embeds','per_layer_inputs','attention_mask','swa_attention_mask','position_ids_cos','position_ids_sin','swa_position_ids_cos','swa_position_ids_sin'],'cache_capture':False,'capture_payload_cap_bytes':80*1024**2,'capture_count_cap':129,'capture_journal_cap_bytes':512*1024,'last_logit_before_sampler':True}
    (out/'preparation.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))


if __name__=='__main__':main()
