#!/usr/bin/env python3
"""Runtime-only frozen-PTE sweep adapter. Preparation does not import native APIs.

No Compile/export path. Native load/forward require a new request-bound release.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import threading
import time

import conv_history_probe as probe
import conv_history_qnn_adapter as base
import conv_history_sweep as sweep
from qwen_host_guard import supervise

LIMITS = {'runtime_seconds': 60, 'total_active_seconds': 90, 'termination_grace_seconds': 20,
          'threads': 4, 'maximum_compiles': 0, 'maximum_loads': 1, 'maximum_forwards': 1}
_PERMISSION = object()


def read_json(path):
    return json.loads(Path(path).read_text())


def sources():
    return [sweep.identity(p) for p in (Path(__file__), Path(sweep.__file__), Path(base.__file__),
                                      sweep.EXP / 'tools/qwen_host_guard.py')]


def runtime_files():
    # File reads only. These prospective runtime pins were not all recorded by
    # the firstcase; do not retroactively claim historical binary identity.
    site = base.PYTHON.parent.parent / 'lib/python3.11/site-packages'
    return [sweep.identity(path) for path in (
        site / 'executorch/extension/pybindings/portable_lib.py',
        site / 'executorch/extension/pybindings/_portable_lib.cpython-311-x86_64-linux-gnu.so',
        site / 'executorch/version.py', site / 'torch/version.py',
        base.SDK / 'lib/x86_64-linux-clang/libQnnHtp.so',
        base.SDK / 'lib/x86_64-linux-clang/libQnnHtpQemu.so',
        base.SDK / 'lib/x86_64-linux-clang/libQnnSystem.so')]


def prepare_request(pack, output):
    pack = Path(pack).absolute()
    sweep.verify(pack)
    route = sweep.frozen_route()
    if read_json(pack / 'frozen-route.json') != route:
        raise ValueError('Pack is not bound to the frozen firstcase')
    store = probe.Evidence(output)
    request = {'schema_version': 1, 'scope': 'one_runtime_load_forward_existing_fullchain_pte',
               'pack_directory': str(pack), 'pack_manifest': sweep.identity(pack / 'result.json'),
               'frozen_route': route, 'limits': LIMITS, 'adapter_sources': sources(),
               'runtime_file_pins': runtime_files(),
               'runtime_pins_scope': 'Prospective pins; not retroactive firstcase binary identity proof.',
               'execution_authorized': False, 'automatic_retry_resume_followon': False,
               'compile_allowed': False, 'physical_access_allowed': False}
    record = store.json('request.json', request)
    store.json('release-template.json', {'status': 'NOT_APPROVED', 'scope': request['scope'],
               'request_sha256': record['sha256'], 'output_directory': None, 'approval_reference': None})
    return request


def validate_request(path):
    request = read_json(path)
    if (request.get('scope') != 'one_runtime_load_forward_existing_fullchain_pte'
            or request.get('limits') != LIMITS or request.get('adapter_sources') != sources()
            or request.get('execution_authorized') is not False or request.get('compile_allowed') is not False
            or request.get('automatic_retry_resume_followon') is not False
            or request.get('physical_access_allowed') is not False):
        raise ValueError('Unreviewed runtime-only source/scope/budget')
    if request.get('runtime_file_pins') != runtime_files():
        raise ValueError('Prospective runtime binary/source pins changed')
    pack = Path(request['pack_directory'])
    if sweep.identity(pack / 'result.json') != request['pack_manifest']:
        raise ValueError('Pack manifest changed')
    sweep.verify(pack)
    if sweep.frozen_route() != request['frozen_route'] or read_json(pack / 'frozen-route.json') != request['frozen_route']:
        raise ValueError('Frozen PTE/context/source receipts changed')
    return request


def require_release(request_path, release_path, root):
    request = validate_request(request_path)
    release = read_json(release_path)
    expected = {'status': 'approved', 'scope': request['scope'],
                'request_sha256': probe.digest(Path(request_path).read_bytes()),
                'output_directory': str(Path(root).absolute())}
    if any(release.get(k) != v for k, v in expected.items()) or not release.get('approval_reference'):
        raise PermissionError('New runtime-only request/output-bound Pi release required')
    request['_permission'] = _PERMISSION
    return request


def worker(request, root, runtime=None):
    """One guarded call. Injected transports must explicitly claim mock provenance."""
    store = probe.Evidence(Path(root) / 'runtime/data')
    state = {'status': 'started', 'load_calls': 0, 'forward_calls': 0,
             'compile_calls': 0, 'actual_native_loads': 0, 'actual_native_forwards': 0}
    try:
        if runtime is not None and getattr(runtime, 'evidence_kind', None) != 'mock':
            raise ValueError('Injected runtime must be labelled mock')
        state['evidence_kind'] = 'mock' if runtime is not None else 'native_binding'
        if runtime is None and request.get('_permission') is not _PERMISSION:
            raise PermissionError('Native worker has no validated runtime-only release')
        # Hash-only revalidation immediately before any load; never a compiler call.
        if sweep.frozen_route() != request['frozen_route']:
            raise ValueError('Frozen route changed before worker')
        pack = Path(request['pack_directory'])
        if sweep.identity(pack / 'result.json') != request['pack_manifest']:
            raise ValueError('Pack identity changed before worker')
        sweep.verify(pack)
        torch = probe.cpu_torch(); torch.set_num_threads(4)
        before = tuple((pack / (name + '.f32le')).read_bytes() for name in ('history', 'projection'))
        for name, raw in zip(('history', 'projection'), before):
            store.raw(name + '.f32le', raw)
        inputs = tuple(torch.frombuffer(bytearray(raw), dtype=torch.float32).reshape(shape)
                       for raw, shape in zip(before, (probe.HISTORY_SHAPE, probe.PROJECTION_SHAPE)))
        adapter = runtime if runtime is not None else base.RealRuntime()
        state['load_calls'] = 1
        state['actual_native_loads'] = int(runtime is None)
        module = adapter.load(Path(request['frozen_route']['pte']['path']))
        store.json('abi.json', base.runtime_abi(module.method_meta('forward')))
        state['forward_calls'] = 1
        state['actual_native_forwards'] = int(runtime is None)
        outputs = module.forward(list(inputs))
        descriptors = []
        for index, tensor in enumerate(outputs):
            raw = tensor.detach().cpu().contiguous().view(torch.uint8).numpy().tobytes()
            descriptors.append({'shape': list(tensor.shape), 'dtype': str(tensor.dtype),
                                **store.raw(f'output-{index}.raw', raw)})
        store.json('raw-output-descriptors.json', descriptors)
        after = tuple(probe.tensor_bytes(tensor) for tensor in inputs)
        for name, raw in zip(('history', 'projection'), after):
            store.raw(name + '-after.f32le', raw)
        if len(outputs) != 1 or tuple(outputs[0].shape) != probe.HISTORY_SHAPE or outputs[0].dtype != torch.float32:
            raise ValueError('Wrong output ABI; raw tensors retained')
        comparison = probe.validate_output('fullchain', outputs[0], before)
        comparison['inputs_unchanged'] = before == after
        comparison['numerical_status'] = ('nonfinite' if not comparison['finite'] else
            'byte_equal' if comparison['all_output_bytes_match_scalar_oracle'] else 'finite_mismatch')
        store.json('comparison.json', comparison)
        if not comparison['inputs_unchanged']:
            raise ValueError('Inputs mutated; before/after bytes and output retained')
        state.update(status='complete', comparison=comparison,
                     claim='Collection only. Host synthetic observation, not numerical/model/FP32/physical acceptance.',
                     internal_sdk_calls={'value': None, 'reason': 'Analyze retained native logs separately; not inferred from logical counts.'})
    except BaseException as error:
        state.update(status='error', error={'type': type(error).__name__, 'message': str(error)})
        raise
    finally:
        store.json('result.json', state)
    return state


def run_one(request_path, release_path, root, supervisor=supervise):
    started = time.monotonic(); deadline = started + LIMITS['total_active_seconds']
    root = Path(root).absolute()
    require_release(request_path, release_path, root)
    root.mkdir(parents=True, exist_ok=False)
    result = {'status': 'started', 'scope': 'one_runtime_only_sweep', 'limits': LIMITS,
              'compile_calls': 0, 'automatic_retry_resume_followon': False, 'phases': [],
              'transport_kind': 'native_supervisor' if supervisor is supervise else 'injected_test_transport'}
    try:
        if (root / 'STOP').exists():
            raise RuntimeError('coordinator_requested_stop')
        folder = root / 'runtime'; folder.mkdir()
        guard = folder / 'guard'; guard.mkdir()
        scratch = folder / 'scratch'; scratch.mkdir()
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('Runtime-only active deadline')
        command = ['nice', '-n', '15', 'ionice', '-c', '2', '-n', '7', str(base.PYTHON), str(Path(__file__).absolute()),
                   '_worker', '--request', str(Path(request_path).absolute()), '--release', str(Path(release_path).absolute()),
                   '--output-dir', str(root)]
        (folder / 'command.json').write_text(json.dumps(command) + '\n')
        done = threading.Event()
        def watch_stop():
            while not done.wait(.1):
                if (root / 'STOP').exists():
                    (guard / 'STOP').touch(); return
        watcher = threading.Thread(target=watch_stop, daemon=True); watcher.start()
        try:
            observed = supervisor(command, guard, min(LIMITS['runtime_seconds'], remaining),
                                  env=base.environment(scratch), grace=LIMITS['termination_grace_seconds'])
        finally:
            done.set(); watcher.join()
        result['phases'].append(observed)
        if observed['exit_code'] != 0 or observed['reason'] != 'process_exit':
            raise RuntimeError('Runtime worker stopped; retain logs/partial data, no retry')
        state = read_json(folder / 'data/result.json')
        if state['status'] != 'complete':
            raise RuntimeError('Runtime collection did not complete')
        if time.monotonic() > deadline:
            raise TimeoutError('Runtime-only active deadline exceeded')
        result.update(status='complete', worker=state)
    except BaseException as error:
        result.update(status='error', error={'type': type(error).__name__, 'message': str(error)})
        raise
    finally:
        result['elapsed_seconds'] = time.monotonic() - started
        with (root / 'result.json').open('x') as out:
            json.dump(result, out, indent=2, allow_nan=False); out.write('\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('prepare-request', 'verify-request', 'execute-one', '_worker'))
    parser.add_argument('--pack', type=Path)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--request', type=Path)
    parser.add_argument('--release', type=Path)
    args = parser.parse_args()
    if args.mode == 'prepare-request':
        if args.pack is None: parser.error('--pack required')
        prepare_request(args.pack, args.output_dir)
    elif args.mode == 'verify-request':
        if args.request is None: parser.error('--request required')
        validate_request(args.request)
    else:
        if args.request is None or args.release is None: parser.error('New request/release required')
        if args.mode == 'execute-one': run_one(args.request, args.release, args.output_dir)
        else: worker(require_release(args.request, args.release, args.output_dir), args.output_dir)


if __name__ == '__main__':
    main()
