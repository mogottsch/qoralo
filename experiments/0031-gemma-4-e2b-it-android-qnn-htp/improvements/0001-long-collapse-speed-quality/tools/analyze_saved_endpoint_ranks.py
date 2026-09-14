#!/usr/bin/env python3
"""ONE saved-only native-QAT / captured-QNN rank packet. No model, ADB or decoding."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import time

import numpy as np

TRACK = Path(__file__).resolve().parents[1]
EXP = TRACK.parents[1]
NATIVE = TRACK / '.local/native-qat-reference/full-prefill-1800-01'
QNN = TRACK / '.local/legacy-logits-phone-runs/legacy-prefill-20260913T125558Z-01'
STAGE = TRACK / '.local/frozen-stages/paired-legacy-logits-stage-01'
ROOT = TRACK / '.local/saved-endpoint-ranks'
N = 262144
KS = (5, 20, 128)
INPUT_SHA = '3b5c04febbc9d55c529ee7ece510607203dbdc8256a6abc05ba0498cf4e52b64'
NATIVE_SHA = '021585a71f18f3e9a071455864bde306762ff052afabc190b28f0527a535b28c'
F32_SHA = 'f2c76d883ed7c67554357d8aa9958803e288adf1e83eb6557b9c3a21d0b253ec'
QNN_SHA = '7b6c6e2d755a024e59d8ac05fbe4a27e992bfa4774c2286fff85144da26bafe9'
TOKENIZER_SHA = 'cc8d3a0ce36466ccc1278bf987df5f71db1719b9ca6b4118264f45cb627bfe0f'
CONFIG_SHA = 'cf6d7dc22738b5e6beb364bac833d78b869f5a6ffd57dfc96c6be3f2abc80424'
QNN_SCALE = 0.0008891067700460553
QNN_OFFSET = -31869
PINS = {
    'results/native-qat-prefill-1800-01/private-originals-manifest.json': 'cc1ac17f62959c278aaabcfd3c08e71c9268203997cfa8911495d3069b6ef158',
    'results/native-qat-prefill-1800-01/result.json': '4510c1720c501f89ccb5de25d0a668c57314b164dfd0bf42af0df50a2e805218',
    'results/same-source-head-fidelity-01/result.json': '0a2c59cb555a14be41834143e0def886dfdba8283e4fbb24b0961975dfffce0e',
    'tools/validate_legacy_prefill_capture.py': '5896074000e806339e3925d0391b11b9879aef77c925d36ca0a2a65acb6db19c',
    '.local/frozen-stages/paired-legacy-logits-stage-01/frozen-manifest.json': '7b61cf0a03ad93292127a7ad59e1b74ae9b61ac4e660691a0cff5a947b40486c',
}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load_json(path):
    return json.loads(Path(path).read_text())


def expand_bf16(native, f32):
    require(native.dtype == np.dtype('<u2') and f32.dtype == np.dtype('<f4'), 'BF16 words / F32 storage types required')
    require(native.shape == f32.shape and native.ndim == 1, 'same one-dimensional endpoint shapes required')
    expanded = (native.astype('<u4') << np.uint32(16)).view('<f4')
    require(np.array_equal(expanded.view('<u4'), f32.view('<u4')), 'saved BF16/F32 expansion mismatch')
    require(bool(np.isfinite(expanded).all()), 'nonfinite native endpoint')
    return expanded


def bind_endpoints():
    """Revalidate original records/bytes; never load a model or a tokenizer."""
    for rel, digest in PINS.items():
        require(sha(TRACK / rel) == digest, 'immutable provenance changed: ' + rel)
    native_manifest = load_json(TRACK / 'results/native-qat-prefill-1800-01/private-originals-manifest.json')
    for record in native_manifest:
        path = Path(record['path'])
        require(path.is_relative_to(TRACK / '.local/native-qat-reference') and not path.is_symlink(), 'native evidence outside owned source root')
        require(path.stat().st_size == record['bytes'] and sha(path) == record['sha256'], 'native evidence hash/size changed: ' + path.name)
    public = load_json(TRACK / 'results/native-qat-prefill-1800-01/result.json')
    guard = load_json(TRACK / '.local/native-qat-reference/full-1800-01-launch/guard-result.json')
    require(guard['actual_child_exit'] == 0 and guard['child_reaped'] and guard['stop_reason'] is None, 'native forward did not complete successfully')
    require(public['completed_forward'] and public['strict_loaded_validation_passed'], 'invalid native checkpoint result')
    require(public['exact_input_ids_sha256'] == INPUT_SHA, 'native recorded input binding changed')
    result = load_json(NATIVE / 'result.json')
    capture = load_json(NATIVE / 'capture.json')
    runtime = load_json(NATIVE / 'runtime-before-load.json')
    contract = load_json(NATIVE / 'forward-contract.json')
    loaded = load_json(NATIVE / 'load-validation.json')
    require(result['passed'] and result['model_forward_calls'] == 1 and result['generation_calls'] == 0, 'one valid native prefill required')
    require(capture['shape'] == [1, 1, N] and capture['original_dtype'] == 'torch.bfloat16' and capture['raw_written_before_analysis'], 'native endpoint capture contract changed')
    require(contract['input_shape'] == [1, 1929] and contract['logits_to_keep'] == 1 and contract['use_cache'] is False, 'native last-row full-history contract changed')
    require(runtime['input_int32le_sha256'] == INPUT_SHA and runtime['config_sha256'] == CONFIG_SHA, 'native runtime source/input changed')
    require(loaded['passed'] and not loaded['failures'], 'native strict loaded validation failed')
    head = {v['key']: v for v in loaded['text_head_tensors'] if v['key'].startswith('lm_head.')}
    require(head['lm_head.weight']['shape'] == [N, 384] and head['lm_head.weight']['matches_source_at_native_dtype'], 'native output-channel order/shape unbound')
    config_path = TRACK / '.local/same-source-reference-readiness/source-20260912-01/config.json'
    require(sha(config_path) == CONFIG_SHA, 'native vocabulary config changed')
    config = load_json(config_path)
    require(config['text_config']['vocab_size'] == N, 'native vocabulary size changed')
    head_audit = load_json(TRACK / 'results/same-source-head-fidelity-01/result.json')
    require(head_audit['rows'] == N and head_audit['source_checkpoint_sha256'] == runtime['checkpoint_sha256'] and head_audit['comparisons']['head_f32']['exact_equal'], 'native/export head row-order provenance failed')

    from validate_legacy_prefill_capture import validate
    qnn_binding = validate(QNN / 'collection.json')
    collection = load_json(QNN / 'collection.json')
    require(collection['identity_verified'] and collection['input_hashes_verified'], 'QNN captured route binding failed')
    qnn_ids = [int(v) for v in (QNN / 'raw/device/input-token-ids.txt').read_text().split()]
    native_ids = (NATIVE / 'input-ids.int32le').read_bytes()
    require(len(qnn_ids) == 1929 and all(0 <= x < N for x in qnn_ids), 'QNN input length/range changed')
    encoded_ids = struct.pack('<1929i', *qnn_ids)
    require(encoded_ids == native_ids and hashlib.sha256(native_ids).hexdigest() == INPUT_SHA, 'actual 1929 input-ID bytes differ')
    executions = []
    with (QNN / 'raw/device/genie-verbose.log').open() as stream:
        for line in stream:
            require('GEMMA_PREFILL_CAPTURE_ERROR' not in line, 'QNN observer error')
            match = re.search(r'Graph (ar128|ar1)_cl4096_1_of_1 execution finished with result (\S+)', line)
            if match:
                executions.append(match.groups())
    require(executions == [('ar128', '0')] * 16, 'exact completed AR128 capture required')
    stage = load_json(STAGE / 'frozen-manifest.json')
    archive_tokenizer = EXP / '.local/checkpoint/extracted/gemma_4_e2b_it_w4a16/tokenizer.json'
    require(stage['files']['tokenizer.json']['sha256'] == TOKENIZER_SHA and sha(STAGE / 'tokenizer.json') == TOKENIZER_SHA and sha(archive_tokenizer) == TOKENIZER_SHA, 'export/physical-route vocabulary tokenizer identity changed')

    paths = [NATIVE / 'last-logits.native.bin', NATIVE / 'last-logits.float32.bin', QNN / 'raw/device/prefill-capture/15-output-logits.raw']
    for path, digest, size in zip(paths, [NATIVE_SHA, F32_SHA, QNN_SHA], [2*N, 4*N, 2*N]):
        require(path.stat().st_size == size and sha(path) == digest, 'endpoint vector hash/size mismatch')
    require(capture['native_sha256'] == NATIVE_SHA and capture['float32_sha256'] == F32_SHA, 'native capture vector hashes changed')
    native = expand_bf16(np.fromfile(paths[0], dtype='<u2'), np.fromfile(paths[1], dtype='<f4'))
    qnn = np.fromfile(paths[2], dtype='<u2')
    require(native.shape == (N,) and qnn.shape == (N,), 'full vocabulary endpoint sizes required')
    require(bool(np.isfinite((qnn.astype(np.float64) + QNN_OFFSET) * QNN_SCALE).all()), 'nonfinite QNN dequantization')
    binding = {
        'native_original_manifest_files_verified': len(native_manifest),
        'native_guard_exit': guard['actual_child_exit'], 'native_one_forward_no_generation': True,
        'native_dtype': 'BF16', 'native_exact_F32_expansion_verified': True,
        'QNN_binding': qnn_binding, 'QNN_AR128_executions': 16, 'QNN_AR1_executions': 0,
        'same_input_ID_bytes': True, 'input_ID_count': 1929, 'input_ID_sha256': INPUT_SHA,
        'vocabulary_size': N, 'tokenizer_sha256': TOKENIZER_SHA,
        'vocabulary_order_basis': 'Native loaded head row order + complete native-F32/export head row audit; identical archive/deployed tokenizer bytes; native contiguous last-logit output and bound QNN logical row8 ABI. No token text decoded.',
        'source_checkpoint_sha256': runtime['checkpoint_sha256'],
        'QNN_context_sha256': stage['context_sha256'],
        'native_softcapping_config': config['text_config'].get('final_logit_softcapping'),
        'QNN_logit_grid': {'scale': QNN_SCALE, 'offset': QNN_OFFSET},
        'vectors': [{'path': str(p), 'bytes': p.stat().st_size, 'sha256': sha(p)} for p in paths],
        'provenance_pins': PINS,
        'model_weights_reopened': False, 'tokenizer_loaded_or_token_text_decoded': False,
        'same_token_history_does_not_mean_same_activations_or_math': True,
        'route_difference': 'Native mixed-INT2/4/8 BF16/SRQ CPU vs calibrated QNN DLC/HTP; upstream embedding/PLE and LUT requantization math differ. Not quantization-only attribution.',
        'invalid_or_partial_DLC_reference_used': False,
    }
    return native, qnn, binding


def finite_vector(values):
    values = np.asarray(values)
    require(values.ndim == 1 and values.size > 0 and np.isfinite(values).all(), 'nonempty finite one-dimensional vector required')
    return values


def rank_interval(values, token_id):
    values = finite_vector(values)
    require(0 <= token_id < values.size, 'ID outside vocabulary')
    value = values[token_id]
    greater = int(np.count_nonzero(values > value))
    ties = int(np.count_nonzero(values == value))
    return {'min': greater + 1, 'max': greater + ties, 'midrank': greater + (ties + 1)/2, 'tie_count': ties}


def midranks(values):
    values = finite_vector(values)
    _, inverse, counts = np.unique(values, return_inverse=True, return_counts=True)
    rank = values.size - np.cumsum(counts) + (counts + 1)/2
    ties = counts[counts > 1]
    return rank[inverse], {'unique_scores': int(counts.size), 'tied_groups': int(ties.size), 'tokens_in_tied_groups': int(ties.sum()), 'largest_tie': int(counts.max()), 'tied_pairs': int(np.sum(counts*(counts-1)//2))}


def top_partition(values, k):
    values = finite_vector(values)
    require(0 < k <= values.size, 'invalid fixed top-k')
    threshold = np.partition(values, values.size-k)[values.size-k]
    strict, boundary = values > threshold, values == threshold
    count = int(strict.sum()); size = int(boundary.sum())
    return strict, boundary, k-count, {'threshold': threshold.item(), 'strict_count': count, 'boundary_tie_count': size, 'boundary_slots': k-count, 'tie_crosses_cutoff': size > k-count, 'tie_expanded_count': count+size}


def topk_overlap(left, right, k):
    """Exact overlap range over every admissible choice at each boundary tie."""
    require(np.shape(left) == np.shape(right), 'same vocabulary shape required')
    a, b, s, left_info = top_partition(left, k)
    c, d, t, right_info = top_partition(right, k)
    forced = int(np.count_nonzero(a & c))
    q = int(np.count_nonzero(b & c)); p = int(np.count_nonzero(a & d))
    shared = int(np.count_nonzero(b & d))
    free_left = int(np.count_nonzero(b & ~(c | d)))
    free_right = int(np.count_nonzero(d & ~(a | b)))
    minimum = forced + max(0, max(0, s-free_left)+max(0, t-free_right)-shared)
    maximum = forced + min(s, q)+min(t, p)+min(shared, max(0, s-q), max(0, t-p))
    require(0 <= minimum <= maximum <= k, 'invalid overlap bounds')
    return {'k': k, 'native': left_info, 'QNN_raw_codes': right_info,
            'admissible_topk_intersection_min': minimum, 'admissible_topk_intersection_max': maximum,
            'per_route_topk_disagreement_min': k-maximum, 'per_route_topk_disagreement_max': k-minimum,
            'symmetric_difference_min': 2*(k-maximum), 'symmetric_difference_max': 2*(k-minimum),
            'tie_expanded_intersection': int(np.count_nonzero((a | b) & (c | d))),
            'arbitrary_tie_break_used': False}


def compare(native, qnn, ks=KS):
    native, qnn = finite_vector(native), finite_vector(qnn)
    require(native.shape == qnn.shape, 'same vocabulary shape required')
    rn, nt = midranks(native); rq, qt = midranks(qnn)
    rn -= rn.mean(); rq -= rq.mean()
    denominator = float(np.sqrt(np.dot(rn, rn)*np.dot(rq, rq)))
    rho = None if denominator == 0 else float(np.dot(rn, rq)/denominator)
    winners = {}
    for name, own, other, other_name in [('native', native, qnn, 'QNN_raw_code_steps'), ('QNN', qnn, native, 'native_saved_F32_units')]:
        ids = np.flatnonzero(own == own.max())
        rows = []
        for token_id in ids[:128]:
            token_id = int(token_id); cross = rank_interval(other, token_id)
            rows.append({'id': token_id, 'own_rank': rank_interval(own, token_id), 'other_route_rank': cross,
                         'winner_displacement_rank_min': cross['min']-1, 'winner_displacement_rank_max': cross['max']-1,
                         'other_route_gap_to_max': float(other.max())-float(other[token_id]), 'gap_units': other_name})
        winners[name] = {'winner_count': int(ids.size), 'winner_IDs_bounded': rows, 'all_winners_listed': ids.size <= 128}
    return {'elements': int(native.size), 'topk': [topk_overlap(native, qnn, k) for k in ks], 'winners': winners,
            'global_statistic': {'name': 'Spearman Pearson-correlation of descending average tied ranks', 'value': rho, 'null_reason': 'constant rank vector' if rho is None else None,
                                 'high_global_agreement_is_not_small_decision_or_prefill_drift': True, 'vocabulary_tail_can_dominate': True},
            'ties': {'native_BF16': nt, 'QNN_UINT16': qt},
            'rank_basis': 'Native exact BF16-expanded values and QNN raw codes (strictly positive affine grid); no cross-route absolute-magnitude equivalence assumed',
            'token_text_decoding': False, 'automatic_causal_or_quality_classification': False}


class PacketWriter:
    """Conservative 256KiB child-output share of the 1MiB whole new-output budget."""
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=False, mode=0o700)
        self.bytes = 0

    def write(self, name, value):
        require(Path(name).name == name, 'flat packet filename required')
        data = (json.dumps(value, indent=2, allow_nan=False)+'\n').encode()
        require(len(data) <= 65536 and self.bytes+len(data) <= 262144, 'bounded packet output exceeded')
        with (self.root/name).open('xb') as f:
            f.write(data); f.flush(); os.fsync(f.fileno())
        self.bytes += len(data)


def execute(root, binder=bind_endpoints):
    writer = PacketWriter(root); start = time.monotonic()
    writer.write('started.json', {'classification': 'ONE_saved_endpoint_packet_started', 'source_sha256': sha(Path(__file__)), 'model_forward_calls': 0, 'ADB_calls': 0})
    try:
        native, qnn, binding = binder()
        writer.write('bindings.json', binding)
        stats = compare(native, qnn)
        writer.write('ranks.json', stats)
        status = {'classification': 'saved_endpoint_rank_packet_complete', 'all_bindings_passed': True, 'seconds': time.monotonic()-start,
                  'comparison_performed': True, 'model_forward_calls': 0, 'ADB_calls': 0, 'token_text_decoding': False,
                  'no_invalid_or_partial_reference': True, 'no_variant_or_policy_patch': True, 'no_QNN_defect_quantization_only_cause_or_repetition_diagnosis': True}
        code = 0
    except Exception as error:
        status = {'classification': 'saved_endpoint_packet_stopped_on_error', 'error_type': type(error).__name__, 'error': str(error)[:1024],
                  'comparison_performed': (writer.root/'ranks.json').exists(), 'seconds': time.monotonic()-start, 'automatic_retry': False}
        code = 2
    writer.write('status.json', status)
    print(json.dumps({'classification': status['classification'], 'exit': code, 'new_packet_bytes': writer.bytes}))
    return code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--grant', type=Path, required=True)
    args = parser.parse_args(); output = args.output_dir.resolve(); grant = load_json(args.grant)
    require(output.is_relative_to(ROOT) and output.name == 'packet-01', 'fresh owned one-packet root required')
    require(grant['id'] == 'pi-saved-endpoint-ranks-20260914-01' and grant['source_sha256'] == sha(Path(__file__)), 'scoped grant/source mismatch')
    used = ROOT/'used-grants'; used.mkdir(parents=True, exist_ok=True)
    with (used/(grant['id']+'.json')).open('x') as f:
        json.dump({'grant_sha256': sha(args.grant), 'output': str(output)}, f)
    return execute(output)


if __name__ == '__main__':
    raise SystemExit(main())
