#!/usr/bin/env python3
"""Saved-only full-vector comparison. No model/phone execution and no DSP-bit claim."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

TRACK=Path(__file__).resolve().parents[1]
SCALE=0.0008891067700460553
OFFSET=-31869
VOCAB=262144


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def compare_codes(qnn,reference,scale=SCALE,offset=OFFSET):
    qnn=np.asarray(qnn);reference=np.asarray(reference)
    if qnn.dtype!=np.uint16 or reference.dtype!=np.uint16 or qnn.ndim!=1 or reference.shape!=qnn.shape or not qnn.size:raise ValueError('equal nonempty one-dimensional UINT16 vectors required')
    if not np.isfinite(scale) or scale<=0 or not np.isfinite(offset):raise ValueError('finite positive common output grid required')
    delta=reference.astype(np.int32)-qnn.astype(np.int32);absolute=np.abs(delta)
    q=(qnn.astype(np.float64)+offset)*scale;r=(reference.astype(np.float64)+offset)*scale
    norm=float(np.linalg.norm(q)*np.linalg.norm(r));centered_q=q-q.mean();centered_r=r-r.mean();cnorm=float(np.linalg.norm(centered_q)*np.linalg.norm(centered_r))
    def maxima(values):
        ids=np.flatnonzero(values==values.max());largest=np.sort(values)[-2:]
        return {'lowest_ID':int(ids[0]),'tie_count':int(ids.size),'IDs_bounded':ids[:16].astype(int).tolist(),'IDs_truncated':bool(ids.size>16),'top2_code_margin':int(largest[-1])-int(largest[-2]) if values.size>1 else None}
    k=min(20,qnn.size);ids=np.arange(qnn.size);top_q=np.lexsort((ids,-qnn.astype(np.int32)))[:k];top_r=np.lexsort((ids,-reference.astype(np.int32)))[:k]
    percentiles={str(p):float(np.percentile(absolute,p)) for p in [50,95,99,100]}
    return {'values_compared':int(qnn.size),'equal_codes':int(np.count_nonzero(delta==0)),'equal_fraction':float(np.mean(delta==0)),'different_codes':int(np.count_nonzero(delta)),'reference_minus_QNN_mean_codes':float(delta.mean()),'mean_absolute_error_codes':float(absolute.mean()),'absolute_error_code_percentiles':percentiles,'mean_absolute_error_common_grid':float(absolute.mean()*scale),'maximum_absolute_error_common_grid':float(absolute.max()*scale),'RMSE_common_grid':float(np.sqrt(np.mean(delta.astype(np.float64)**2))*scale),'cosine_common_grid':float(np.dot(q,r)/norm) if norm else None,'cosine_unavailable_reason':None if norm else 'zero vector norm','Pearson_common_grid':float(np.dot(centered_q,centered_r)/cnorm) if cnorm else None,'Pearson_unavailable_reason':None if cnorm else 'zero centered variance','QNN_argmax':maxima(qnn),'reference_argmax':maxima(reference),'argmax_sets_intersect':bool(np.any((qnn==qnn.max())&(reference==reference.max()))),'topk':int(k),'topk_overlap':len(set(top_q.tolist())&set(top_r.tolist())),'QNN_topk_IDs':top_q.astype(int).tolist(),'reference_topk_IDs':top_r.astype(int).tolist(),'analysis_tie_order':'ascending token ID; not an assertion of DSP/sampler tie handling','common_grid':{'scale':scale,'offset':offset},'bit_exact_codes':bool(np.array_equal(qnn,reference))}


def inspect_vectors(qnn_path,reference_path,float_path,expected_qnn_sha,expected_reference_sha,expected_float_sha):
    for path,size,digest in [(qnn_path,VOCAB*2,expected_qnn_sha),(reference_path,VOCAB*2,expected_reference_sha),(float_path,VOCAB*4,expected_float_sha)]:
        if Path(path).stat().st_size!=size or sha(path)!=digest:raise ValueError('full vector length/hash mismatch '+str(path))
    qnn=np.fromfile(qnn_path,dtype='<u2');ref=np.fromfile(reference_path,dtype='<u2');floating=np.fromfile(float_path,dtype='<f4')
    expanded=(ref.astype(np.float32)+np.float32(OFFSET))*np.float32(SCALE)
    if not np.isfinite(floating).all() or not np.array_equal(expanded.view(np.uint32),floating.view(np.uint32)):raise ValueError('reference F32 serialization does not match raw codes/common grid')
    return {**compare_codes(qnn,ref),'reference_float32_finite_values':VOCAB,'reference_raw_to_F32_serialization_verified':True,'QNN_raw_sha256':expected_qnn_sha,'reference_raw_sha256':expected_reference_sha,'reference_float32_sha256':expected_float_sha}


def trace_summary(path):
    result={'begin':0,'end':0,'malformed_lines':0,'sequence_anomalies':0,'by_chunk':{},'last_begin':None,'last_end':None};opened={}
    if not Path(path).exists():return {'available':False}
    with Path(path).open() as stream:
        for line in stream:
            try:row=json.loads(line);key=(row['chunk'],row['index']);event=row['event']
            except (ValueError,KeyError,TypeError):result['malformed_lines']+=1;continue
            if event not in ['begin','end']:result['sequence_anomalies']+=1;continue
            result[event]+=1;chunk=result['by_chunk'].setdefault(str(row['chunk']),{'begin':0,'end':0});chunk[event]+=1;result['last_'+event]=row
            if event=='begin':
                if key in opened:result['sequence_anomalies']+=1
                opened[key]=row
            elif key in opened:del opened[key]
            else:result['sequence_anomalies']+=1
    result.update(available=True,open_operations=list(opened.values())[:20],open_operation_count=len(opened),raw_sha256=sha(path));return result


def analyze(host_root,out,*,corrected=False):
    host_root=Path(host_root).resolve();out=Path(out).resolve()
    expected_root=TRACK/('.local/corrected-legacy-prefill-host-runs' if corrected else '.local/legacy-prefill-host-runs')
    if not host_root.is_relative_to(expected_root):raise ValueError('owned saved host root for the explicit reference version required')
    if not out.is_relative_to(TRACK/'.local/paired-prefill-comparison'):raise ValueError('fresh owned saved-analysis root required')
    from validate_legacy_prefill_capture import validate,specification
    spec=specification();phone=validate(spec['phone_collection']);native=host_root/'native'
    def optional(path):return json.loads(path.read_text()) if path.exists() else None
    guard=optional(host_root/'guard-result.json');service=optional(host_root/'service-exit.json');capture=optional(native/'capture.json');progress=optional(native/'progress.json');grant=optional(host_root/'grant.json')
    expected_grant=spec['host_grant_id']
    if corrected:
        from run_corrected_paired_prefill_host import CORRECTED_GRANT,CORRECTED_REFERENCE_SHA
        expected_grant=CORRECTED_GRANT
        if not grant or grant.get('host_source_bindings',{}).get(str(TRACK/'tools/declared_dlc_reference_fp16.py'))!=CORRECTED_REFERENCE_SHA:raise ValueError('corrected reference source binding missing')
    if not grant or grant['grant_id']!=expected_grant or grant['phone_collection_sha256']!=spec['phone_collection_sha256']:raise ValueError('wrong source/capture grant')
    nonfinite=optional(native/'nonfinite-first.json')
    stderr=(host_root/'child.stderr').read_text(errors='replace') if (host_root/'child.stderr').exists() else ''
    warnings=[line for line in stderr.splitlines() if 'RuntimeWarning:' in line or 'REFERENCE_NONFINITE' in line]
    result={'phone_binding':phone,'host_root':str(host_root),'reference_version':'storage_corrected' if corrected else 'original_INVALID_REFERENCE','first_unexpected_nonfinite':nonfinite,'numerical_warning_markers':warnings,'guard':guard,'service':service,'reference_capture':capture,'progress':progress,'trace':trace_summary(native/'operations.jsonl'),'comparison':None,'classification':'incomplete_or_unvalidated_reference_preserved','model_or_phone_executed_by_analysis':False,'DSP_bit_exact_claim':False,'long_generation_quality_claim':False,'sole_AS_cause_claim':False}
    if nonfinite is None and capture and capture.get('complete') and capture.get('AR128_executions')==16 and capture.get('input_tokens')==1929 and progress and progress.get('completed_chunks')==16:
        result['comparison']=inspect_vectors(Path(phone['capture_dir'])/'15-output-logits.raw',native/'last-logits.uint16le',native/'last-logits.float32le',spec['raw_QNN_logits_sha256'],capture['raw_sha256'],capture['float32_sha256'])
        result['classification']='complete_storage_corrected_prefill_vector_comparison' if corrected else 'complete_but_INVALID_original_reference_comparison'
        result['control_exit_caveat']=None if guard and guard.get('actual_child_exit')==0 and not guard.get('guard_error') and not guard.get('stop_reason') and service and service.get('actual_service_exit')==0 else 'complete hash-bound vectors exist; retain missing/nonzero controller/guard/service observations separately'
    out.mkdir(parents=True,exist_ok=False);(out/'analysis.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'classification':result['classification'],'analysis_sha256':sha(out/'analysis.json'),'comparison':result['comparison']},indent=2));return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--host-root',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--corrected',action='store_true');a=p.parse_args();analyze(a.host_root,a.output_dir,corrected=a.corrected)
