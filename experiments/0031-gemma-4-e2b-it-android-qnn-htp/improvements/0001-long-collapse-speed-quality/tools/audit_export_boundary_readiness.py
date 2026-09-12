#!/usr/bin/env python3
"""Read graph/source metadata and saved evidence; never create an inference session."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import time

TRACK=Path(__file__).resolve().parents[1]
EXP=TRACK.parents[1]
ARCHIVE=EXP/'.local/checkpoint/extracted/gemma_4_e2b_it_w4a16'
HUB=EXP/'.local/ai-hub-models-v0.61.0'
SOURCE=TRACK/'.local/native-qat-reference/source-323f2434-01/extracted/transformers-323f24345ed92f88e68a14aeef7db78ee2b52475/src/transformers'
GENIE=TRACK/'.local/selected-id-trace-runs/trace-build-20260911T142946Z-04/sdk-source/examples/Genie/Genie/src/qualla'
STAGE=TRACK/'.local/frozen-stages/selected-id-long-20260911T143756Z-01'
CONTEXT=TRACK/'results/value-precision-path-context-attempt-01/raw/compile-02/context-info.json'
TRACE=TRACK/'.local/selected-id-phone-long-runs/trace-long-20260911T150027Z-01/raw/device'


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def requant_codebook(lut_scale,lut_offset,input_scale,input_offset,clamp):
    """Source-defined numeric conversion of all256 codes, no model tensors."""
    scale=lut_scale/input_scale
    offset=int(scale*lut_offset-input_offset)  # C++ int32_t member assignment
    values=[scale*q+offset for q in range(256)]
    invalid=[q for q,v in enumerate(values) if not 0<=v<65536]
    # Never invent modulo semantics for out-of-range float-to-unsigned casts.
    if invalid and not clamp:return {'unclamped_out_of_range_codes':invalid,'conversion_valid_for_all_codes':False}
    codes=[int(min(65535,max(0,v)) if clamp else v) for v in values]
    delta=[(c+input_offset)*input_scale-(q+lut_offset)*lut_scale for q,c in enumerate(codes)]
    return {'requant_scale':scale,'requant_offset_int32':offset,'conversion_valid_for_all_codes':True,'unclamped_out_of_range_codes':invalid,
            'output_code_min':min(codes),'output_code_max':max(codes),'max_abs_added_error':max(map(abs,delta)),
            'boundary':'Error introduced by source-defined UINT8-to-UINT16 conversion only, excluding prior LUT quantization and native BF16 differences; not execution proof.'}


def tensor_metadata(tree,names):
    found=[]
    def walk(x):
        if isinstance(x,dict):
            if x.get('name') in names and 'quantizeParams' in x:found.append(x)
            for v in x.values():walk(v)
        elif isinstance(x,list):
            for v in x:walk(v)
    walk(tree);return found


def partial_logits_inventory(path):
    counts=Counter();markers=0
    with path.open(errors='replace') as f:
        for line in f:
            if 'input-logits:' not in line:continue
            markers+=1
            match=re.search(r'input-logits:\s*\[([^]]*)\]\s*\.\.\.\s*\[([^]]*)\]',line)
            if match:counts[str(tuple(len(x.split(',')) for x in match.groups()))]+=1
            else:counts['unparsed']+=1
    return {'marker_count':markers,'entries_per_head_tail':dict(counts),'complete_vocabulary_vector':False,
            'boundary':'Bound sampler source emits first10 and last10 typed entries only; not a sampled-ID reconstruction or full-logit comparison.'}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args();out=a.output_dir.resolve()
    if out.parent!=TRACK/'results' or not out.name.startswith('export-boundary-source-readiness-'):p.error('fresh owning result directory required')
    out.mkdir(parents=True,exist_ok=False);started=time.monotonic()
    import onnx  # protobuf metadata only; external weight data explicitly not loaded
    model=onnx.load(ARCHIVE/'model_dynamic.onnx',load_external_data=False)
    ops=Counter(n.op_type for n in model.graph.node);domains=Counter(n.domain for n in model.graph.node)
    enc=json.loads((ARCHIVE/'model.encodings').read_text())
    hist={}
    for key in ['activation_encodings','param_encodings']:
        vals=enc[key].values() if isinstance(enc[key],dict) else enc[key];c=Counter()
        for v in vals:
            if isinstance(v,list):v=v[0]
            c[str((v.get('bw',v.get('bitwidth')),v.get('dtype')))]+=1
        hist[key]=dict(c)
    cfg=json.loads((STAGE/'gemma4-e2b-htp-cl4096-greedy.json').read_text())['dialog']
    tensors=tensor_metadata(json.loads(CONTEXT.read_text()),{'inputs_embeds','per_layer_inputs','logits'})
    book={}
    for label,name,clamp in [('embedding','inputs_embeds',False),('perlayer-embedding','per_layer_inputs',True)]:
        selected=[x for x in tensors if x['name']==name];grids=[x['quantizeParams']['scaleOffset'] for x in selected]
        if not grids or any(x!=grids[0] for x in grids):raise ValueError('input grid not common to AR pair')
        qp=cfg[label]['quant-param'];g=grids[0]
        book[name]={'lut':cfg[label],'graph_grid':g,'all_256_codes':requant_codebook(qp['scale'],qp['offset'],g['scale'],g['offset'],clamp)}
    roots=[EXP/'.local/phone-runs',EXP/'.local/campaign-runs']+[TRACK/'.local'/n for n in ['phone-return-runs','phone-return-long-runs','value-precision-phone-long-runs','selected-id-phone-long-runs']]
    candidate_files=[];file_count=0
    for root in roots:
        if not root.exists():continue
        for f in root.rglob('*'):
            if not f.is_file():continue
            file_count+=1
            if f.suffix in {'.raw','.npy','.npz'} or 'logit' in f.name.lower():candidate_files.append({'path':str(f),'bytes':f.stat().st_size})
    source_files=[ARCHIVE/'args.json',ARCHIVE/'config.json',ARCHIVE/'model_dynamic.onnx',ARCHIVE/'model.encodings',EXP/'tools/build_embedding_luts.py',
      SOURCE/'integrations/gemma_quant.py',SOURCE/'models/gemma4/modeling_gemma4.py',CONTEXT,STAGE/'gemma4-e2b-htp-cl4096-greedy.json',
      HUB/'src/qai_hub_models/models/_shared/gemma4/_utils.py',HUB/'src/qai_hub_models/models/_shared/gemma4/model.py',HUB/'src/qai_hub_models/models/_shared/gemma4/model_adaptations.py',HUB/'src/qai_hub_models/models/_shared/gemma4/quantize.py',HUB/'src/qai_hub_models/models/gemma_4_e2b_it/model.py',
      GENIE/'sampler.cpp',GENIE/'dialog.cpp',GENIE/'include/qualla/dialog.hpp',GENIE/'encoders/text-encoders/LUT.cpp',GENIE/'engines/qnn-htp/nsp-model.cpp']
    bindings=[{'path':str(f),'bytes':f.stat().st_size,'sha256':sha(f)} for f in source_files]
    site=EXP/'.local/qairt-2.49.40-venv/lib/python3.10/site-packages'
    result={'classification':'source_and_saved_evidence_readiness_only','neural_model_instantiations_or_forward_calls':0,'adb_calls':0,'raw_model_tensor_capture':False,
      'archived_export':{'graph_sha256':sha(ARCHIVE/'model_dynamic.onnx'),'producer_name':model.producer_name,'producer_version':model.producer_version,'node_count':len(model.graph.node),'function_count':len(model.functions),'op_counts':dict(ops),'node_domains':dict(domains),'args':json.loads((ARCHIVE/'args.json').read_text()),'encoding_version':enc['version'],'quantizer_args':enc['quantizer_args'],'encoding_histograms':hist},
      'available_exporter_source':{'revision':'5975a79b55b40f5cbc61f3ac5e52abe47d9d8bd5','tag':'v0.61.0','relevant_paths_clean_at_inspection':True,'archive_producer_source_revision_proven':False,'default_model':'google/gemma-4-E2B-it','loader_boundary':'deq_proj calls weight.float(), does not unpack packed QAT or use weight_scale/SRQ; embedding loader expects .weight. Do not instantiate it on the retained packed QAT checkpoint as an archive oracle.'},
      'SRQ_boundary':{'native_observed_calls':552,'native_calibrated_calls':550,'native_bits':8,'export_explicit_round_clip_QDQ_nodes':sum(ops[k] for k in ['Round','Clip','QuantizeLinear','DequantizeLinear']),'export_uses_new_16bit_activation_encodings':True,'direct_native_to_HTP_numerical_match':False},
      'input_boundary':{'contracts':book,'graph_IO_metadata':tensors,'layout':'Main1536, PLE35x256=8960; raw token-identity PLE is blended with an in-graph normalized model projection, not pre-projected twice.','native_rounding_boundary':'Native scales/products/output are BF16; LUT authoring unpacks/scales in F32, folds sqrt1536/sqrt256, then global UINT8 quantization. Native bitwise equality not established.','Genie_padding_boundary':'Bound source copies real per-layer vectors first and EOS-fill for remaining AR slots; a generic left-padding helper is not a proven equivalent.'},
      'saved_logit_inventory':{'provider_log_binding':{'path':str(TRACE/'genie-verbose.log'),'bytes':(TRACE/'genie-verbose.log').stat().st_size,'sha256':sha(TRACE/'genie-verbose.log')},'searched_roots':[str(x) for x in roots],'files_examined_by_name':file_count,'raw_logit_candidate_files':candidate_files,'selected_trace_provider':partial_logits_inventory(TRACE/'genie-verbose.log'),'selected_trace_payloads':[{'name':f.name,'bytes':f.stat().st_size} for f in sorted(TRACE.iterdir()) if f.is_file()],'full_native_reference_commit':'a10cab6ce8d57991f665542a2766b1d14a185227','QNN_complete_prefill_logits_found':False,'scope':'Named retained QNN run roots and bound sampler evidence only; not a global filesystem proof. LiteRT selected callbacks are not full logits.'},
      'local_reference_dependency_presence':{'onnxruntime_package':(site/'onnxruntime').is_dir(),'aimet_onnx_package':(site/'aimet_onnx').is_dir(),'inference_session_created':False},
      'readiness':{'matched_causal_comparison_ready':False,'next_inference_authorized':False,'next_smallest_gate':'Static full active-weight mapping plus exact external-input/PLE/LUT/requantization and cache/mask/RoPE ledger; then bind a same-export/same-effective-quantization reference before one paired final-prefill logit comparison.','reject_selected_ID_only_comparison':True,'reject_float_ONNX_as_w4a16_equivalent':True,'reject_new_precision_variant':True},
      'source_bindings':bindings,'seconds':time.monotonic()-started}
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'path':str(out),'node_count':len(model.graph.node),'explicit_SRQ_nodes':result['SRQ_boundary']['export_explicit_round_clip_QDQ_nodes'],'input_requant_codebook':{k:v['all_256_codes'] for k,v in book.items()},'saved_QNN_candidates':candidate_files,'partial_logits':result['saved_logit_inventory']['selected_trace_provider'],'seconds':result['seconds']},indent=2))


if __name__=='__main__':main()
