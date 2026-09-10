#!/usr/bin/env python3
"""Analyze saved control/own-trajectory output tensors only; no model execution."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from compare_qnn_trajectory import Store, checked_artifact, load_bound_tensor
from controlled_position1 import difference_vectors
from replay_saved_qdq import artifact


def compare_saved(reference, actual):
    import torch
    if reference.shape != actual.shape or reference.dtype != actual.dtype:
        raise ValueError('Saved output geometry/dtype mismatch')
    a, b = reference.double().reshape(-1), actual.double().reshape(-1)
    finite = bool(torch.isfinite(a).all() and torch.isfinite(b).all())
    if not finite:
        return {'finite': False, 'cosine': None, 'max_abs': None, 'mean_abs': None,
                'l2_difference': None, 'cosine_null_reason': 'nonfinite saved values'}
    norms = float(a.norm()), float(b.norm())
    cosine = None if not all(norms) else float(torch.dot(a, b) / (norms[0] * norms[1]))
    d = b-a
    return {'finite': True, 'cosine': cosine, 'cosine_null_reason': 'zero norm' if cosine is None else None,
            'max_abs': float(d.abs().max()), 'mean_abs': float(d.abs().mean()),
            'l2_difference': float(d.norm()), 'reference_l2': norms[0], 'actual_l2': norms[1]}


def output_identity(index, layer_types):
    if index == 0: return 'logits', None, None
    if index <= 24: return 'state_a', index-1, layer_types[index-1]
    if index <= 48: return 'state_b', index-25, layer_types[index-25]
    return 'hidden_after_layer', index-49, layer_types[index-49]


def analyze(qnn_result_path, own_prefix_directory, output_dir):
    import torch
    torch.set_num_threads(1)
    store = Store(output_dir)
    q = json.loads(qnn_result_path.read_text())
    if q['status'] != 'completed_single_call' or q['backend'] != 'qnn' or q['graph_calls_returned'] != 1 or q['target_position'] != 1:
        raise ValueError('Expected completed single QNNposition1 control')
    if not q['exact_same_pack_qdq_reference_used'] or q['input_mutation_observed']:
        raise ValueError('Control lacks an unmutated same-pack QDQ reference')
    qdq_path = Path(q['paired_qdq_control']['path'])
    checked_artifact(qdq_path, q['paired_qdq_control'])
    d = json.loads(qdq_path.read_text())
    if d['backend'] != 'qdq' or d['status'] != 'completed_single_call' or d['graph_calls_returned'] != 1 or d['target_position'] != 1:
        raise ValueError('Invalid paired QDQ control')
    if d['input_mutation_observed'] or d['pack_header']['sha256'] != q['pack_header']['sha256'] or d['submitted_input_values_sha256'] != q['submitted_input_values_sha256']:
        raise ValueError('Control inputs differ')
    header_path = Path(q['pack_header']['path']); checked_artifact(header_path, q['pack_header'])
    header = json.loads(header_path.read_text())
    if d['model_artifact']['sha256'] != header['models']['histogram_qdq']['sha256'] or q['model_artifact']['sha256'] != header['models']['histogram_pte']['sha256']:
        raise ValueError('Paired model artifact mismatch')
    old = json.loads((own_prefix_directory/'raw/result.json').read_text())
    if old['binding']['pte_sha256'] != q['model_artifact']['sha256'] or old['binding']['qdq_sha256'] != d['model_artifact']['sha256']:
        raise ValueError('Own-state prefix is from a different route')
    if old['binding']['params_sha256'] != header['models']['params']['sha256'] or old['binding']['token_ids_sha256'] != header['models']['input_ids']['sha256'] or old['binding']['context'] != header['context']:
        raise ValueError('Own-state params/input/context mismatch')
    historical_entries = [e for e in json.loads((own_prefix_directory/'compression-manifest.json').read_text())['files'] if e['kind']=='qdq_logits' and e.get('position')==1]
    if len(historical_entries)!=1 or historical_entries[0]['raw_sha256'] != header['historical_qdq_position1']['sha256']:
        raise ValueError('Historical QDQ vector differs from the original prefix reference')
    journal = own_prefix_directory/'raw/progress.jsonl';checked_artifact(journal,old['progress_artifact'])
    events = [json.loads(line) for line in journal.read_text().splitlines()]
    matching = [row for row in events if row['event']=='compared' and row['position']==1]
    if len(matching)!=1 or matching[0]['input_token']!=header['target_token']:
        raise ValueError('Own-state position/token mismatch')
    c = load_bound_tensor(Path(q['raw_outputs']['path']),q['raw_outputs'])
    ref = load_bound_tensor(Path(d['raw_outputs']['path']),d['raw_outputs'])
    own = load_bound_tensor(Path(matching[0]['raw_outputs']['path']),matching[0]['raw_outputs'])
    historical = load_bound_tensor(Path(header['historical_qdq_position1']['path']),header['historical_qdq_position1'])
    if any(len(x)!=73 for x in (c,ref,own)):raise ValueError('Expected three complete73-output bundles')
    params_path = own_prefix_directory/'raw/params.json'
    if artifact(params_path)['sha256']!=old['binding']['params_sha256']:raise ValueError('Parameter hash mismatch')
    types=json.loads(params_path.read_text())['layer_types']
    rows=[]
    for i,(r,a,o) in enumerate(zip(ref,c,own)):
        kind,layer,layer_type=output_identity(i,types)
        rows.append({'output_index':i,'kind':kind,'layer':layer,'layer_type':layer_type,
                     'current_call_same_inputs':compare_saved(r,a),
                     'prior_state_effect_in_qnn':compare_saved(a,o),
                     'own_qnn_vs_control_qdq':compare_saved(r,o)})
    vectors = difference_vectors(own[0],c[0],ref[0],historical)
    vector_artifact = store.tensor('raw/logit-difference-vectors.pt',vectors)
    terms={name:{'l2':float(x.double().norm()),'mean_abs':float(x.double().abs().mean()),'max_abs':float(x.abs().max())} for name,x in vectors.items()}
    # Validate identity in double precision separately; raw float32 terms/residual stay intact.
    double_terms=difference_vectors(own[0].double(),c[0].double(),ref[0].double(),historical.double())
    doubles_residual=float(double_terms['rounding_residual'].abs().max())
    if doubles_residual > 1e-12:raise ValueError('Difference-vector identity failed')
    report={'schema_version':1,'evidence_class':'saved_tensor_position1_same_pack_current_call_and_state_effect_analysis',
            'analysis_model_or_pte_execution':False,'same_pack_header_sha256':q['pack_header']['sha256'],
            'same_input_values_sha256':q['submitted_input_values_sha256'],
            'input_sources':{'qnn_control_result':artifact(qnn_result_path),'qdq_control_result':artifact(qdq_path),
                             'qnn_control_outputs':q['raw_outputs'],'qdq_control_outputs':d['raw_outputs'],
                             'own_qnn_outputs':matching[0]['raw_outputs'],'historical_qdq_logits':header['historical_qdq_position1']},
            'outputs':rows,'output_count':73,'all_three_bundles_finite':all(row[k]['finite'] for row in rows for k in ('current_call_same_inputs','prior_state_effect_in_qnn','own_qnn_vs_control_qdq')),
            'historical_reference_logits_equal_new_qdq':bool(torch.equal(historical,ref[0])),
            'logit_vectors':vector_artifact,'logit_vector_terms':terms,'double_identity_max_abs_residual':doubles_residual,
            'argmax':{'new_qdq':int(ref[0].argmax()),'controlled_qnn':int(c[0].argmax()),'own_qnn':int(own[0].argmax())},
            'metrics_precision':'float64 saved-data comparisons; original runtime float32 metrics remain unchanged',
            'claim_limits':['This analyzes existing saved tensors, not a new model run.','Current-call same-input error and prior-state effect are both measured; no individual operator root cause or full-trajectory fidelity follows.','Layer taps are endpoints within a call; earlier hidden errors propagate into later layers.','Other than logits, no historical full-replay QDQ output bundle exists at this position; own-QNN comparisons use the new controlled QDQ outputs.','Difference vectors add with recorded floating residual; scalar cosines and norms are not additive or attribution percentages.','Prior-state-effect interpretation assumes the fixed PTE/native runtime stack; physical/accuracy/campaign claims remain excluded.']}
    store.result(report)
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--qnn-result',type=Path,required=True)
    p.add_argument('--own-prefix-directory',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True)
    args=p.parse_args()
    r=analyze(args.qnn_result,args.own_prefix_directory,args.output_dir)
    print(json.dumps({'all73_finite':r['all_three_bundles_finite'],'logits':r['outputs'][0],'vector_terms':r['logit_vector_terms']},indent=2))


if __name__=='__main__':main()
