#!/usr/bin/env python3
"""Weight-free CPU reference preparation. No QNN import, compiler or runtime CLI."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import sys

from audit_conv_history_metadata import scalar_qdq

EXP = Path(__file__).resolve().parents[1]
TRACE = EXP / 'results/conv-history-encoding-audit-20260910/qdq-metadata-trace.json'
MEMBER_SHA = '2d879235c4d4a47643378e3ec3739bd587d4b0a68b23097b8ba64092ce20ad86'
CASES = ('fullchain', 'outputonly', 'aligned')
HISTORY_SHAPE = (1, 6144, 1, 4)
PROJECTION_SHAPE = (1, 6144, 1, 1)
SELECTED = (0, 6053, 0, 2)
COMMON_VALUE = 23.721895217895508


def digest(data):
    return hashlib.sha256(data).hexdigest()


class Evidence:
    """Fresh directory, immutable files, raw output before validation; no resume."""
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=False)
        self.records = {}

    def raw(self, name, data):
        path = self.directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as f:
            f.write(data); f.flush(); os.fsync(f.fileno())
        self.records[name] = {'bytes': len(data), 'sha256': digest(data)}
        return self.records[name]

    def json(self, name, value):
        return self.raw(name, (json.dumps(value, indent=2, allow_nan=False) + '\n').encode())


def encodings():
    raw = TRACE.read_bytes()
    trace = json.loads(raw)
    if trace['archive_metadata']['member_sha256'] != MEMBER_SHA:
        raise ValueError('Not the accepted source metadata member')
    rows = trace['encodings']
    expected = [(0.0007933978922665119, 37640), (0.0009200899512507021, 32457),
                (0.0008176580304279923, 36523)]
    result = {}
    for row, (scale, zero) in zip(rows, expected, strict=True):
        if (row['scale'], row['zero_point'], row['quant_min'], row['quant_max'], row['dtype']) != (scale, zero, 0, 65535, 4):
            raise ValueError('Pinned activation encoding changed')
        result[row['stage']] = {k: row[k] for k in ('scale', 'zero_point', 'quant_min', 'quant_max', 'dtype')}
    return result


def case_spec(case):
    if case not in CASES:
        raise ValueError(f'Unknown variant: {case}')
    e = encodings()
    stages = {'history': None, 'projection': None, 'concat': None, 'output': e['slice_output']}
    if case == 'fullchain':
        stages.update(history=e['state_input'], projection=e['slice_output'], concat=e['concat'])
    elif case == 'aligned':
        stages = {key: e['slice_output'] for key in stages}
    return {'case': case, 'history_shape': HISTORY_SHAPE, 'projection_shape': PROJECTION_SHAPE,
            'stages': stages, 'qdq_pair_count': sum(v is not None for v in stages.values()),
            'concat_dim': -1, 'slice_dim': 3, 'slice_start': -4,
            'selected_input': (0, 6053, 0, 3), 'selected_output': SELECTED,
            'selected_input_value': COMMON_VALUE,
            'source_member_sha256': MEMBER_SHA, 'source_trace_sha256': digest(TRACE.read_bytes())}


def cpu_torch():
    # Registration of the exact public CPU Q/DQ operators; no ExecuTorch/QNN imports.
    import torch
    import torch.ao.quantization.fx._decomposed  # noqa: F401
    return torch


def make_module(case):
    torch = cpu_torch()
    spec = case_spec(case)

    def qdq(x, encoding):
        if encoding is None:
            return x
        args = (encoding['scale'], encoding['zero_point'], 0, 65535, torch.int32)
        q = torch.ops.quantized_decomposed.quantize_per_tensor.default(x, *args)
        return torch.ops.quantized_decomposed.dequantize_per_tensor.default(q, *args)

    class Boundary(torch.nn.Module):
        def forward(self, history, projection):
            h = qdq(history, spec['stages']['history'])
            p = qdq(projection, spec['stages']['projection'])
            joined = qdq(torch.cat((h, p), dim=-1), spec['stages']['concat'])
            return qdq(joined[:, :, :, -4:], spec['stages']['output'])

    return Boundary().eval()


def make_inputs():
    torch = cpu_torch()
    history = torch.empty(HISTORY_SHAPE, dtype=torch.float32)
    for slot, value in enumerate((-0.25, 0.5, -0.75, 1.0)):
        history[:, :, :, slot] = value
    history[0, 6053, 0, 3] = COMMON_VALUE
    projection = torch.full(PROJECTION_SHAPE, 0.125, dtype=torch.float32)
    projection[0, 0, 0, 0] = -0.125
    projection[0, 1, 0, 0] = 0.0
    projection[0, 6143, 0, 0] = 0.25
    return history, projection


def tensor_bytes(tensor):
    if sys.byteorder != 'little' or str(tensor.dtype) != 'torch.float32' or tensor.device.type != 'cpu':
        raise ValueError('Raw evidence requires little-endian CPU float32')
    return tensor.detach().contiguous().numpy().tobytes()


def oracle(case, history_bytes, projection_bytes):
    """Independent stdlib scalar FP32 reconstruction of ALL output positions."""
    if len(history_bytes) != 98304 or len(projection_bytes) != 24576:
        raise ValueError('Wrong input geometry')
    h = struct.unpack('<24576f', history_bytes)
    p = struct.unpack('<6144f', projection_bytes)
    stages = case_spec(case)['stages']
    def apply(value, encoding):
        return value if encoding is None else scalar_qdq(value, encoding)['output_fp32']
    values = []
    for channel in range(6144):
        for slot in range(4):
            value = h[channel*4 + slot+1] if slot < 3 else p[channel]
            value = apply(value, stages['history'] if slot < 3 else stages['projection'])
            value = apply(apply(value, stages['concat']), stages['output'])
            values.append(value)
    return struct.pack('<24576f', *values)


def validate_output(case, output, inputs_raw):
    raw = tensor_bytes(output)
    expected = oracle(case, *inputs_raw)
    values = struct.unpack('<24576f', raw) if len(raw) == 98304 else ()
    finite = len(values) == 24576 and all(math.isfinite(v) for v in values)
    return {'shape': list(output.shape), 'dtype': str(output.dtype), 'finite': finite,
            'all_output_bytes_match_scalar_oracle': raw == expected,
            'scalar_oracle_sha256': digest(expected), 'output_sha256': digest(raw),
            'selected_index': SELECTED,
            'selected_actual': values[6053*4+2] if finite else None,
            'selected_expected': struct.unpack_from('<f', expected, (6053*4+2)*4)[0]}


def runtime_plan():
    return {'status': 'proposal_not_authorized_not_executed', 'cases': list(CASES),
            'scope': 'three separate weight-free host QNN-x86 boundary controls, not model or physical HTP evidence',
            'per_case': {'compile_invocations_max': 1, 'forward_calls_max': 1,
                         'compile_deadline_seconds': 120, 'runtime_deadline_seconds': 60,
                         'total_case_deadline_seconds': 240, 'termination_grace_seconds': 20,
                         'fresh_process': True, 'math_threads': 4, 'expected_tensor_payload_bytes': 221184},
            'aggregate_active_deadline_seconds': 720,
            'stop_after_first_failure_interruption_or_missing_route_proof': True,
            'automatic_retry_or_resume': False, 'automatic_follow_on_authorized': False,
            'release': 'Pi must review this harness and explicitly authorize case(s); no release inferred from preparation',
            'resources': 'nice15/ionice2:7, owned disk scratch, external qwen_host_guard STOP/PSI/deadline with TERM/grace/KILL/reap; app priority',
            'route_gate': 'zero nondelegated tensor compute, retain any compile artifacts/errors before checking; no fallback execution',
            'interpretation_gate': 'missing encoding taps remain null with reasons; retain outputs but do not attribute frontend/SDK behavior',
            'metadata_taps': ['pre/post capture and preprocess passes', 'per-consumer get_quant_encoding_conf',
                              'actual QNN op-wrapper tensor getters before Compile', 'optional manager-reported graph IO after Compile'],
            'not_available': 'QNN internal finalized/fused graph is not established by pre-Compile wrappers or manager IO',
            'real_compile_runtime_adapter': 'not implemented or invoked in this source/CPU preparation release'}


def prepare(directory):
    store = Evidence(directory)
    status = {'evidence_class': 'tiny_weight_free_cpu_reference_preparation', 'status': 'started',
              'qnn_compile_calls': 0, 'qnn_runtime_calls': 0, 'full_model_loads': 0,
              'phone_access': False, 'cpu_reference_forwards': 0, 'cases': []}
    try:
        store.json('plan.json', runtime_plan())
        store.json('started.json', status)
        torch = cpu_torch(); torch.set_num_threads(4)
        import torch.ao.quantization.fx._decomposed as cpu_ops
        status['cpu_provenance'] = {'torch_version': torch.__version__, 'python_version': sys.version,
                                    'math_threads': torch.get_num_threads(),
                                    'qdq_source_path': cpu_ops.__file__,
                                    'qdq_source_sha256': digest(Path(cpu_ops.__file__).read_bytes()),
                                    'probe_source_sha256': digest(Path(__file__).read_bytes())}
        inputs = make_inputs()
        inputs_raw = tuple(tensor_bytes(x) for x in inputs)
        store.raw('raw/history.f32le', inputs_raw[0]); store.raw('raw/projection.f32le', inputs_raw[1])
        for case in CASES:
            store.json(f'{case}/spec.json', case_spec(case))
            model = make_module(case)
            if tuple(model.parameters()) or tuple(model.buffers()):
                raise ValueError('Probe must be weight/buffer-free')
            status['cpu_reference_forwards'] += 1
            with torch.no_grad():
                output = model(*inputs)
            store.raw(f'{case}/output.f32le', tensor_bytes(output))  # raw FIRST
            report = validate_output(case, output, inputs_raw)
            report['inputs_unchanged'] = inputs_raw == tuple(tensor_bytes(x) for x in inputs)
            store.json(f'{case}/comparison.json', report)
            status['cases'].append({'case': case, **report})
            if not (report['finite'] and report['all_output_bytes_match_scalar_oracle'] and report['inputs_unchanged'] and report['shape'] == list(HISTORY_SHAPE)):
                raise ValueError('CPU reference mismatch; raw evidence retained, no retry')
        status['status'] = 'complete'
    except BaseException as error:
        status.update(status='error', error={'type': type(error).__name__, 'message': str(error)})
        raise
    finally:
        status['files'] = dict(store.records)
        store.json('result.json', status)
    return status


def mock_case(case, directory, compiler, runtime):
    """Test orchestration only. Real compile/runtime adapters are NOT accepted."""
    if getattr(compiler, 'evidence_kind', None) != 'mock' or getattr(runtime, 'evidence_kind', None) != 'mock':
        raise PermissionError('Only explicitly mock interfaces in this preparation release')
    case_spec(case)  # reject unknown variants before any injected interface call
    store = Evidence(directory)
    state = {'evidence_class': 'mock_interfaces_not_qnn', 'case': case, 'compile_calls': 0, 'forward_calls': 0}
    try:
        spec = case_spec(case)
        inputs = make_inputs(); before = tuple(tensor_bytes(x) for x in inputs)
        store.raw('history.f32le', before[0]); store.raw('projection.f32le', before[1])
        state['compile_calls'] += 1
        artifact = compiler.compile(spec, store)
        store.raw('mock-compiled-artifact.bin', artifact['bytes'])
        store.json('delegation.json', artifact['delegation'])
        if not artifact['delegation'].get('all_tensor_compute_delegated'):
            raise ValueError('No runtime call permitted with fallback or missing delegation proof')
        state['forward_calls'] += 1
        output = runtime.forward(artifact, inputs)
        store.raw('output.f32le', tensor_bytes(output))
        store.json('comparison.json', validate_output(case, output, before))
        if before != tuple(tensor_bytes(x) for x in inputs):
            raise ValueError('Runtime mutated the reviewed inputs')
        state['status'] = 'complete'
    except BaseException as error:
        state.update(status='error', error={'type': type(error).__name__, 'message': str(error)})
        raise
    finally:
        store.json('result.json', state)
    return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('prepare-cpu', 'plan'))
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args()
    if args.mode == 'plan':
        print(json.dumps(runtime_plan(), indent=2)); return
    if args.output_dir is None:
        parser.error('--output-dir required for prepare-cpu')
    print(json.dumps(prepare(args.output_dir), indent=2))


if __name__ == '__main__':
    main()
