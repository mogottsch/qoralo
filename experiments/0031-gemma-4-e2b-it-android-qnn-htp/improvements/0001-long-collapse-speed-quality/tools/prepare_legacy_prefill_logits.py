#!/usr/bin/env python3
"""HOST-ONLY relocation of the raw final-row hook into the actual PLE legacy path."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil

TRACK=Path(__file__).resolve().parents[1]
BASE=TRACK/'.local/paired-mapping-observer/build-01/sdk-source'
REL='examples/Genie/Genie/src/qualla/engines/qnn-htp/nsp-model.cpp'
EXPECTED='ebe9e4ef26efce16b0de64c9f021e60de9dc9366ca8e6c02cc5011c474277a6f'
PRIOR_PREP_SHA='4b6302d88ac7221df01a5a53d1a0e786f19b13e2e2004c1665b101d24e21d18b'


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()


def hooks():
    if sha(TRACK/'tools/prepare_paired_prefill_capture.py')!=PRIOR_PREP_SHA:raise ValueError('original capture preparation changed')
    from prepare_paired_prefill_capture import OUTPUT_HOOK
    observed=OUTPUT_HOOK.replace('GEMMA_PAIRED_PREFILL_LOGIT_CAPTURE_V1: last valid row, before Tensor/sampler access.','GEMMA_PLE_LEGACY_LOGIT_CAPTURE_V2: existing view already selects row8; no second offset.')
    observed=observed.replace('{"before_sampler_access", true}, {"cache_tensor", false}', '{"before_sampler_access", true}, {"cache_tensor", false},\n        {"before_original_dequantization", true}, {"row_view_already_offset", true},\n        {"source_path", "PLE_legacy_getDequantLogits"}')
    return OUTPUT_HOOK,observed


def patch(source):
    old,new=hooks()
    anchor='  __TRACE("qnn-htp: getDequantLogits Returning {}*{} from [{}]", count, m_vocab_size, step.str());\n'
    old_anchor='  __TRACE("qnn-htp: getLogits Returning {}*{} from [{}]", count, m_vocab_size, step.str());\n'
    if source.count(old)!=1 or source.count(anchor)!=1 or source.count(old_anchor)!=1:raise ValueError('legacy hook anchor changed')
    result=source.replace(old,'').replace(anchor,anchor+new)
    if result.replace(new,'').replace(old_anchor,old_anchor+old)!=source:raise ValueError('non-observation mutation')
    # Data expression is deliberately the already-offset native view, unchanged.
    if '"logits", logit_buffer,\n                                  size * bitwidth' not in new:raise ValueError('double-offset or buffer-expression mutation')
    return result


def prepare(out):
    build=json.loads((BASE.parent/'build-result.json').read_text())
    if build['actual_native_exit']!=0 or build['binary_sha256']!='ee2b10d89d9fec2442bdf6cfd6a1e369eb525ec1c0d091acd2ee19bcb00ba099':raise ValueError('frozen mapping base mismatch')
    if sha(BASE/REL)!=EXPECTED:raise ValueError('bound nsp source changed')
    files=[Path(parent)/name for parent,_,names in os.walk(BASE,followlinks=True) for name in names if (Path(parent)/name).is_file()]
    if sum(p.stat().st_size for p in files)>2*1024**3 or shutil.disk_usage(TRACK).free<72*1024**3:raise ValueError('copy/disk bound')
    out.mkdir(parents=True,exist_ok=False);dest=out/'sdk-source';shutil.copytree(BASE,dest,symlinks=False)
    (dest/REL).write_text(patch((BASE/REL).read_text()))
    evidence={'classification':'raw_logit_observer_relocated_to_real_PLE_legacy_dispatch','changes':[{'path':REL,'before':EXPECTED,'after':sha(dest/REL)}],'existing_row8_pointer_offset_applied_exactly_once':True,'original_deQuantizeOutputs_call_and_computation_unchanged':True,'input_mapping_allocation_observers_unchanged':True,'model_LUT_config_caps_AS_changed':False,'model_or_phone_executed':False}
    (out/'preparation.json').write_text(json.dumps(evidence,indent=2)+'\n');print(json.dumps(evidence,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args();out=a.output_dir.resolve()
    if not out.is_relative_to(TRACK/'.local/paired-legacy-logits'):p.error('fresh owned private root required')
    prepare(out)
