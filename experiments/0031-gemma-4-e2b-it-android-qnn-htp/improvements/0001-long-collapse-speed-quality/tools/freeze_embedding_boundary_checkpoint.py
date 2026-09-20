#!/usr/bin/env python3
"""Freeze ONE saved-evidence input-boundary checkpoint. No forward, ADB or comparison run."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import time

import numpy as np

TRACK = Path(__file__).resolve().parents[1]
EXP = TRACK.parents[1]
STAGE = EXP / '.local/phone-stage'
CAPTURE = TRACK / '.local/legacy-logits-phone-runs/legacy-prefill-20260913T125558Z-01/raw/device/prefill-capture'
CHECKPOINT = EXP / '.local/hf-checkpoint/model.safetensors'
ROOT = TRACK / '.local/embedding-boundary-checkpoint'
CHECKPOINT_SHA = 'efab429012b97ab986c4d4838a46ff3ad95d618b42ce514771ca40fadc76a9a4'
CAPTURE_BINDING_SHA = 'b0fcf4f660dafb4c88097edfc1517d34a1a015564b39a6d16b814418d78d616a'
INPUT_IDS_SHA = '3b5c04febbc9d55c529ee7ece510607203dbdc8256a6abc05ba0498cf4e52b64'
CHUNK0_EMBEDS_SHA = 'cafd3f67352a0ad9c80cdf3a70312bb0f85314c55b9a5eff2623b09b789ae1b9'
HIDDEN = 1536


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def requantization(lut_encoding, graph_grid):
    """Reproduce the declared UINT8 LUT to UINT16 graph-input conversion."""
    scale = lut_encoding['scale'] / graph_grid['scale']
    offset = int(scale * lut_encoding['offset'] - graph_grid['offset'])
    codes = np.arange(256, dtype=np.float64) * scale + offset
    return {'requant_scale': scale, 'requant_offset_int32': offset,
            'reachable_code_min': int(math.floor(codes.min())), 'reachable_code_max': int(math.ceil(codes.max())),
            'all_codes_in_UINT16_range': bool(codes.min() >= 0 and codes.max() <= 65535)}


def bf16_half_ulp(magnitude):
    """Half spacing of BF16 (8 significand bits, 7 explicit) at the given finite magnitude."""
    magnitude = float(abs(magnitude))
    if magnitude == 0:
        return 0.0
    return float(2.0 ** (math.floor(math.log2(magnitude)) - 8))


def error_budget(lut_encoding, requant_added_error, max_abs_value):
    half_step = lut_encoding['scale'] / 2
    bf16 = bf16_half_ulp(max_abs_value)
    return {'units': 'architecturally scaled embedding value units',
            'LUT_UINT8_half_step': half_step,
            'UINT8_to_UINT16_max_added_error': requant_added_error,
            'native_BF16_half_ulp_at_max_abs_value': bf16,
            'per_element_budget_at_max_abs_value': half_step + requant_added_error + bf16,
            'boundary': 'Declared quantization/storage terms only. Not a claimed hardware error bound and not an accuracy acceptance threshold.'}


def inspect_capture_codes(path, reach):
    """Bounded check that captured graph inputs lie inside the declared LUT image."""
    codes = np.fromfile(path, dtype='<u2')
    require(codes.size == 128 * HIDDEN, 'unexpected captured chunk-0 embedding size')
    return {'values_checked': int(codes.size), 'observed_code_min': int(codes.min()), 'observed_code_max': int(codes.max()),
            'inside_declared_LUT_image': bool(codes.min() >= reach['reachable_code_min'] and codes.max() <= reach['reachable_code_max']),
            'distinct_codes': int(np.unique(codes).size),
            'boundary': 'Consistency of captured codes with the declared requantized LUT image; not proof of equality to native embeddings.'}


def contract():
    provenance = json.loads((STAGE / 'lut-provenance.json').read_text())
    require(provenance['source']['sha256'] == CHECKPOINT_SHA, 'LUT provenance checkpoint differs from native-QAT checkpoint')
    boundary = json.loads((TRACK / 'results/export-boundary-source-readiness-01/result.json').read_text())['input_boundary']['contracts']
    require(sha(TRACK / 'results/paired-legacy-host-binding-01/capture-binding.json') == CAPTURE_BINDING_SHA, 'capture binding changed')
    require(CHECKPOINT.stat().st_size == provenance['source']['bytes'], 'native checkpoint size differs from LUT provenance')
    require(abs(provenance['luts'][0]['architectural_scale'] - math.sqrt(HIDDEN)) < 1e-12, 'declared architectural embedding scale is not sqrt(hidden_size)')

    sides = []
    for lut, name, declared in [(provenance['luts'][0], 'inputs_embeds', boundary['inputs_embeds']),
                                (provenance['luts'][1], 'per_layer_inputs', boundary['per_layer_inputs'])]:
        path = STAGE / lut['filename']
        require(path.stat().st_size == lut['bytes'], 'deployed LUT size changed: ' + lut['filename'])
        reach = requantization(lut['encoding'], declared['graph_grid'])
        recorded = declared['all_256_codes']
        require(abs(reach['requant_scale'] - recorded['requant_scale']) < 1e-9 and reach['requant_offset_int32'] == recorded['requant_offset_int32'],
                'recomputed requantization differs from the recorded export-boundary contract')
        require(reach['reachable_code_min'] <= recorded['output_code_min'] and reach['reachable_code_max'] >= recorded['output_code_max'], 'reachable code range inconsistent')
        sides.append({
            'graph_input': name,
            'QNN_side': {'deployed_LUT': {'path': str(path), 'bytes': lut['bytes'], 'sha256': lut['sha256']},
                         'LUT_encoding': lut['encoding'], 'graph_grid': declared['graph_grid'], 'requantization': reach,
                         'captured_payloads': '16 chunks of actual graph inputs, already validated equal to the host LUT formula'},
            'native_side': {'source_checkpoint_sha256': CHECKPOINT_SHA,
                            'quantized_key': lut['source_quantized_key'], 'scale_key': lut['source_scale_key'],
                            'source_bits': lut['source_bits'], 'architectural_scale': lut['architectural_scale'],
                            'signed_mapping': provenance['dequantization_formula']['signed_mapping'],
                            'saved_native_activation_available': False,
                            'reconstruction': 'Static table gather and declared dequantization for exactly the 1929 captured IDs; no transformer forward.'},
            'error_budget': error_budget(lut['encoding'], declared['all_256_codes']['max_abs_added_error'],
                                         max(abs(lut['encoding']['min']), abs(lut['encoding']['max']))),
        })

    reach0 = sides[0]['QNN_side']['requantization']
    return {'classification': 'frozen_input_boundary_checkpoint_not_executed',
            'question': 'Do the two routes start from the same token embeddings, within declared quantization and storage terms, for exactly the 1929 captured IDs?',
            'earliest_boundary_with_both_sides_available': 'model input (token embedding and per-layer embedding)',
            'internal_layer_activations_saved_on_either_route': False,
            'input_ids_sha256': INPUT_IDS_SHA, 'input_ids': 1929, 'hidden_size': HIDDEN,
            'sides': sides,
            'captured_chunk0_check': inspect_capture_codes(CAPTURE / '00-input-inputs_embeds.raw', reach0),
            'captured_chunk0_sha256': CHUNK0_EMBEDS_SHA,
            'predictions': {
                'consistent_with_declared_quantization': 'Per-element differences stay within the declared per-element budget with no systematic sign or scale pattern. Then both routes start from the same embeddings up to declared quantization, and endpoint divergence arises at or after the first in-graph operation. This does NOT identify a layer.',
                'divergent_before_any_transformer_arithmetic': 'A systematic offset, missing or extra architectural scale, wrong row order, or per-element differences far beyond the budget. Then endpoint differences cannot be attributed to in-graph HTP arithmetic alone.',
                'reported_regardless': 'Per-element and per-row difference distributions in declared units, worst rows/IDs, and the exact fraction outside budget. No pass or fail quality verdict.'},
            'stop_criterion': 'Stop immediately on any binding, size, hash or dtype failure. Otherwise stop after ONE bounded packet, whatever the outcome. No variant, no second boundary, no repeated reconstruction, no automatic follow-up.',
            'execution_envelope_if_authorized': {'RAM_bytes': 2147483648, 'swap': 0, 'CPU': 1, 'seconds': 300,
                                                 'new_output_bytes': 262144, 'output_accounting_includes_preparation_spill': True,
                                                 'model_forward_calls': 0, 'ADB_calls': 0, 'token_text_decoding': False,
                                                 'reads': 'Static embedding tables and captured input payloads only'},
            'free_parameters_or_fitted_scalars': 0,
            'declared_transform_source': 'Pinned LUT provenance, pinned source quantization code revision and the recorded export-boundary contract; nothing fitted to QNN outputs.',
            'what_this_cannot_decide': ['Which decoder layer or operation diverges; no route saved internal activations.',
                                        'Whether the QNN repetition collapse is caused by any of this.',
                                        'Any QNN defect, quantization-only cause, or HTP kernel behaviour.',
                                        'Whether agreement at the input boundary implies agreement later.'],
            'endpoint_packet_and_budget_exception': 'unchanged',
            'executed_by_this_freeze': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    out = args.output_dir.resolve()
    require(out.is_relative_to(ROOT), 'owned fresh freeze root required')
    out.mkdir(parents=True, exist_ok=False, mode=0o700)
    os.umask(0o077)
    start = time.monotonic()
    try:
        result = contract()
        result['seconds'] = time.monotonic() - start
        result['source_sha256'] = sha(Path(__file__))
    except Exception as error:
        result = {'classification': 'input_boundary_freeze_failed', 'error_type': type(error).__name__, 'error': str(error)[:512], 'executed_by_this_freeze': False}
        (out / 'contract.json').write_text(json.dumps(result, indent=2) + '\n')
        raise
    (out / 'contract.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'classification': result['classification'], 'chunk0': result['captured_chunk0_check'], 'seconds': result['seconds']}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
