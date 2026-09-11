#!/usr/bin/env python3
"""Separate geometry and Softplus effects, reusing preserved native CPU outputs.

Two offline-only source controls, neither is a synthesis input or HTP model pack:
1. static native-boundary Gather + ORIGINAL Softplus vs original native output;
2. dynamic NATIVE shapes + stable Softplus vs saved static Gather/stable output.
"""
import argparse
import json
import os
from pathlib import Path
import resource
import signal
import time
from check_padding import EXP, compare, pad, sha
from materialize import capacity, edge_indices, lower_native_edges


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    if '.local' not in args.output.resolve().parts:
        p.error('private output only')
    resource.setrlimit(resource.RLIMIT_AS, (8 << 30, 8 << 30))
    signal.alarm(900)
    os.environ.update(OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='4', MKL_NUM_THREADS='1')
    import numpy as np
    import onnx
    import onnxruntime as ort
    args.output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    freeze = json.loads((EXP / 'protocol/freeze.json').read_text())
    baseline = json.loads((args.baseline / 'result.json').read_text())
    bundle = EXP / '.local/common/bundle'
    result = dict(status='started', numpy=np.__version__, onnxruntime=ort.__version__,
        baseline_sha256=sha(args.baseline / 'result.json'), android_execution=False,
        cpu_features_for_htp=False, original_strict_numeric_gate_unchanged=True, chunks=[])
    try:
        for name, expected in freeze['bundle_files_sha256'].items():
            if sha(bundle / name) != expected:
                raise ValueError('shared bundle changed')
        for binding in freeze['cpu_original_model_bindings'].values():
            if sha(binding['source']) != binding['sha256']:
                raise ValueError('source pin mismatch')
        original = onnx.load(freeze['cpu_original_model_bindings']['vector']['source'])
        static = capacity.specialize(original, 'vector', 320, 512)
        native_boundary, edges = lower_native_edges(static, 512)
        onnx.checker.check_model(native_boundary, full_check=True)
        onnx.save(native_boundary, args.output / 'native-softplus-static-boundary.onnx')
        del native_boundary, static
        # Keep T/L dynamic; bind only the actual batch1 so the audited identity
        # can verify its time-encoder tensor is float32[2,256]. No node/weight edit.
        for value in [*original.graph.input, *original.graph.output]:
            value.type.tensor_type.shape.dim[0].dim_value = 1
        original = onnx.shape_inference.infer_shapes(original, strict_mode=True, data_prop=False)
        stable_dynamic = capacity.stable_softplus(original)
        result['stable_dynamic_control_batch'] = 1
        onnx.save(stable_dynamic, args.output / 'stable-softplus-dynamic.onnx')
        del stable_dynamic, original
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 4
        opts.inter_op_num_threads = 1
        opts.log_severity_level = 3
        def session(path):
            return ort.InferenceSession(str(path), opts, providers=['CPUExecutionProvider'])
        text = session(freeze['cpu_original_model_bindings']['text']['source'])
        boundary = session(args.output / 'native-softplus-static-boundary.onnx')
        stable = session(args.output / 'stable-softplus-dynamic.onnx')
        ttl = np.fromfile(bundle / 'style_ttl.f32', '<f4').reshape(1, 50, 256)
        total = np.fromfile(bundle / 'total_steps.f32', '<f4')
        schedule = np.fromfile(bundle / 'current_steps.f32', '<f4')
        for row in baseline['chunks']:
            i, t, length = row['index'], row['text_extent'], row['native_latent']
            with np.load(args.baseline / f'chunk-{i:03d}.npz') as saved:
                initial, original_final, candidate_final = saved['initial'], saved['native'], saved['bucket']
            folder = bundle / f'{i:03d}'
            ids = np.fromfile(folder / 'text_ids.i64', '<i8').reshape(1, t)
            mask = np.fromfile(folder / 'text_mask.f32', '<f4').reshape(1, 1, t)
            emb = text.run(None, dict(text_ids=ids, text_mask=mask, style_ttl=ttl))[0]
            record = dict(index=i, text_extent=t, native_latent=length)
            final_outputs = {}
            for label, s, tb, lb in [('native_softplus_boundary', boundary, 320, 512),
                                     ('stable_softplus_native', stable, t, length)]:
                latent = pad(initial, lb)
                extra = edge_indices(length, lb) if s is boundary else {}
                for step in schedule:
                    latent = s.run(None, dict(extra, noisy_latent=latent, text_emb=pad(emb, tb),
                        text_mask=pad(mask, tb), latent_mask=pad(np.ones((1, 1, length), np.float32), lb),
                        style_ttl=ttl, current_step=np.asarray([step], np.float32), total_step=total))[0]
                final_outputs[label] = latent[..., :length]
            record['geometry_original_softplus'] = compare(original_final, final_outputs['native_softplus_boundary'])
            record['geometry_stable_softplus'] = compare(final_outputs['stable_softplus_native'], candidate_final[..., :length])
            record['softplus_alone_native_shapes'] = compare(original_final, final_outputs['stable_softplus_native'])
            result['chunks'].append(record)
            print(json.dumps(record), flush=True)
        result['geometry_bitwise_equal_all'] = all(c[k]['bitwise_equal'] for c in result['chunks']
            for k in ['geometry_original_softplus', 'geometry_stable_softplus'])
        result['status'] = 'geometry_bitwise_equal' if result['geometry_bitwise_equal_all'] else 'geometry_not_bitwise_equal'
    except BaseException as e:
        result.update(status='error', error=str(e))
        raise
    finally:
        result.update(elapsed_seconds=time.monotonic()-started,
                      process_ru_maxrss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        (args.output / 'result.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')


if __name__ == '__main__':
    main()
