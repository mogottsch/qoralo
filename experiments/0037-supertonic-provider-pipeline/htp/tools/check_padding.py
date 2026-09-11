#!/usr/bin/env python3
"""Offline source-CPU padding probe, NOT Android proof or a listening render.

Original four dynamic graphs, unchanged weights/native Softplus. Native and
bucket calls use the same sessions and active noise. Host CPU features never
become HTP inference inputs. All activations/PCM stay under the private output.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import time

ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT.parent
MAX_ABS = 1e-4
MAX_RMSE = 1e-5


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for part in iter(lambda: f.read(1 << 20), b''):
            h.update(part)
    return h.hexdigest()


def extent(raw):
    import numpy as np
    d = np.float32(np.float32(raw) / np.float32(1.05))
    wf = np.float32(d * np.float32(44100))
    length = int(np.int32(np.float32(np.float32(np.float32(wf + np.float32(3072)) - np.float32(1)) / np.float32(3072))))
    mask_length = (int(np.int64(wf)) + 3071) // 3072
    if not np.isfinite(d) or d <= 0 or length != mask_length or not 1 <= length <= 1000:
        raise ValueError('invalid provider duration/nativeL/maskL; no correction')
    return float(d), length


def pad(array, size):
    import numpy as np
    if array.shape[-1] > size:
        raise ValueError('native extent exceeds candidate bucket; no truncation')
    return np.pad(array, [(0, 0)] * (array.ndim - 1) + [(0, size - array.shape[-1])])


def compare(a, b):
    import numpy as np
    if a.shape != b.shape or not np.isfinite(a).all() or not np.isfinite(b).all():
        raise ValueError('shape or finite-value violation')
    difference = a.astype(np.float64) - b.astype(np.float64)
    maximum = float(np.max(np.abs(difference)))
    rmse = float(np.sqrt(np.mean(difference * difference)))
    return dict(max_abs=maximum, rmse=rmse, reference_rms=float(np.sqrt(np.mean(a.astype(np.float64) ** 2))),
                bitwise_equal=bool(np.array_equal(a, b)), passed=maximum <= MAX_ABS and rmse <= MAX_RMSE)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--chunks', type=int, nargs='+', default=list(range(15)))
    p.add_argument('--text-bucket', type=int, default=320)
    p.add_argument('--latent-bucket', type=int, default=512)
    p.add_argument('--vector-candidate', type=Path)
    p.add_argument('--vocoder-candidate', type=Path)
    args = p.parse_args()
    if '.local' not in args.output.resolve().parts:
        p.error('content-bearing output must stay in .local')
    if any(i not in range(15) for i in args.chunks) or len(set(args.chunks)) != len(args.chunks):
        p.error('invalid chunk selection')
    resource.setrlimit(resource.RLIMIT_AS, (8 << 30, 8 << 30))
    signal.alarm(900)
    # Bound BLAS before importing NumPy/ORT; ORT has its own four-thread setting.
    os.environ.update(OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='4', MKL_NUM_THREADS='1')
    import numpy as np
    import onnxruntime as ort
    args.output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    freeze_path = EXP / 'protocol/freeze.json'
    freeze = json.loads(freeze_path.read_text())
    protocol = json.loads((EXP / 'protocol/inputs.json').read_text())
    bundle = EXP / '.local/common/bundle'
    result = dict(status='started', probe='original_dynamic_CPU_native_vs_bucket_padding', android_execution=False,
                  cpu_features_for_htp=False, audio_assembly=False, listening_verdict='not_reviewed',
                  numpy=np.__version__, onnxruntime=ort.__version__, intra_threads=4, inter_threads=1,
                  address_space_limit_bytes=8 << 30, timeout_seconds=900, text_bucket=args.text_bucket,
                  latent_bucket=args.latent_bucket, freeze_sha256=sha(freeze_path),
                  bundle_manifest_sha256=freeze['bundle_manifest_sha256'],
                  acceptance=dict(max_abs=MAX_ABS, rmse=MAX_RMSE, note='predeclared source-FP32 numerical gate, not perceptual acceptance'),
                  chunks=[])
    def save():
        result['elapsed_seconds'] = time.monotonic() - started
        result['process_ru_maxrss_kib'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        (args.output / 'result.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    try:
        if freeze['status'] != 'frozen' or sha(bundle / 'manifest.json') != freeze['bundle_manifest_sha256']:
            raise ValueError('freeze mismatch')
        for name, expected in freeze['bundle_files_sha256'].items():
            if sha(bundle / name) != expected:
                raise ValueError('shared bundle changed: ' + name)
        sessions = {}
        for name, binding in freeze['cpu_original_model_bindings'].items():
            source = Path(binding['source'])
            if sha(source) != binding['sha256'] or source.stat().st_size != binding['bytes']:
                raise ValueError('source pin mismatch')
            options = ort.SessionOptions()
            options.intra_op_num_threads = 4
            options.inter_op_num_threads = 1
            options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
            options.log_severity_level = 3
            sessions[name] = ort.InferenceSession(str(source), options, providers=['CPUExecutionProvider'])
        bucket_sessions = dict(sessions)
        result['candidates'] = {}
        for name, path in [('vector', args.vector_candidate), ('vocoder', args.vocoder_candidate)]:
            if path is not None:
                bucket_sessions[name] = ort.InferenceSession(str(path), options, providers=['CPUExecutionProvider'])
                result['candidates'][name] = dict(path=str(path), sha256=sha(path),
                    structural_delta_sha256=sha(path.parent / 'structural-delta.json'))
        if args.vector_candidate:
            result['probe'] = 'original_dynamic_CPU_vs_static_native_boundary_Gather_and_stable_Softplus'
        result['setup_seconds'] = time.monotonic() - started
        dp = np.fromfile(bundle / 'style_dp.f32', '<f4').reshape(1, 8, 16)
        ttl = np.fromfile(bundle / 'style_ttl.f32', '<f4').reshape(1, 50, 256)
        stream = np.fromfile(bundle / 'noise_stream.f32', '<f4')
        total = np.fromfile(bundle / 'total_steps.f32', '<f4')
        schedule = np.fromfile(bundle / 'current_steps.f32', '<f4')
        offset = 0
        # DP is evaluated in original order even if selecting a subset, so the
        # native Gaussian stream offsets remain those of this source CPU route.
        for chunk in protocol['chunks']:
            index = chunk['index']
            t = chunk['text_extent']
            folder = bundle / f'{index:03d}'
            ids = np.fromfile(folder / 'text_ids.i64', '<i8').reshape(1, t)
            mask = np.fromfile(folder / 'text_mask.f32', '<f4').reshape(1, 1, t)
            raw = sessions['duration'].run(None, dict(text_ids=ids, text_mask=mask, style_dp=dp))[0][0]
            duration, length = extent(raw)
            noise_offset = offset
            initial = stream[offset:offset + 144 * length].reshape(1, 144, length).copy()
            offset += 144 * length
            if index not in args.chunks:
                continue
            if t > args.text_bucket or length > args.latent_bucket:
                raise ValueError('observed nativeT/L exceeds candidate; preserve full chunk and stop')
            emb = sessions['text'].run(None, dict(text_ids=ids, text_mask=mask, style_ttl=ttl))[0]
            native = initial.copy()
            bucket = pad(initial, args.latent_bucket)
            row = dict(index=index, text_extent=t, native_latent=length, raw_duration=float(raw),
                       speed_adjusted_duration=duration, noise_offset=noise_offset,
                       active_noise_sha256=hashlib.sha256(initial.tobytes()).hexdigest(), vector_steps=[])
            boundaries = {}
            if args.vector_candidate:
                from materialize import edge_indices
                boundaries = edge_indices(length, args.latent_bucket)
            for step in schedule:
                common = dict(style_ttl=ttl, current_step=np.asarray([step], dtype=np.float32), total_step=total)
                native = sessions['vector'].run(None, dict(common, noisy_latent=native, text_emb=emb,
                    text_mask=mask, latent_mask=np.ones((1, 1, length), np.float32)))[0]
                bucket = bucket_sessions['vector'].run(None, dict(common, **boundaries, noisy_latent=bucket,
                    text_emb=pad(emb, args.text_bucket), text_mask=pad(mask, args.text_bucket),
                    latent_mask=pad(np.ones((1, 1, length), np.float32), args.latent_bucket)))[0]
                row['vector_steps'].append(dict(step=int(step), **compare(native, bucket[..., :length])))
            # Isolate vocoder padding: feed exactly the SAME final native latent
            # into native shape and zero-padded bucket, not different vector outputs.
            native_wave = sessions['vocoder'].run(None, {'latent': native})[0]
            zero_wave = bucket_sessions['vocoder'].run(None, {'latent': pad(native, args.latent_bucket)})[0][..., :length * 3072]
            row['vocoder_zero_padding'] = compare(native_wave, zero_wave)
            row['vocoder_first_hop'] = compare(native_wave[..., :3072], zero_wave[..., :3072])
            row['vocoder_last_hop'] = compare(native_wave[..., -3072:], zero_wave[..., -3072:])
            row['vocoder_middle_without_32_hops'] = compare(native_wave[..., 32*3072:-32*3072], zero_wave[..., 32*3072:-32*3072]) if length > 64 else None
            if args.vector_candidate:
                candidate_wave = bucket_sessions['vocoder'].run(None, {'latent': bucket})[0][..., :length * 3072]
                row['end_to_end_native_prefix'] = compare(native_wave, candidate_wave)
            row['passed'] = all(s['passed'] for s in row['vector_steps']) and row['vocoder_zero_padding']['passed'] and row.get('end_to_end_native_prefix', {'passed': True})['passed']
            np.savez(args.output / f'chunk-{index:03d}.npz', initial=initial, native=native, bucket=bucket,
                     native_wave=native_wave, zero_wave=zero_wave)
            result['chunks'].append(row)
            save()
            print(json.dumps({'index': index, 'nativeL': length, 'vector_final': row['vector_steps'][-1],
                              'vocoder_zero_padding': row['vocoder_zero_padding']}), flush=True)
        result['status'] = 'passed' if all(r['passed'] for r in result['chunks']) else 'padding_gate_failed'
        result['noise_draws_consumed_for_full_DP_route'] = offset
    except BaseException as e:
        result.update(status='error', error_type=type(e).__name__, error=str(e))
        raise
    finally:
        save()


if __name__ == '__main__':
    main()
