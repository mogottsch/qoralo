#!/usr/bin/env python3
"""Fresh ignored stage for one baseline/candidate native AR171 prefill call each."""
import argparse
import hashlib
import json
import os
from pathlib import Path

BASELINE_SHA = 'd5ca624cc71a173c7de969fac777e2ce136db3b502e04c2991651b510dabba5a'
CANDIDATE_SHA = '62ad1261fd3181d5e4a3d8832d3bfd553d9d9e44aa4597face98b5268f315243'
TOKENS_SHA = 'eae8e828110f634d5c9954df0372e869f67f67aed846f9f544781faa1d4d29bc'


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 << 20), b''):
            h.update(block)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('baseline-context', 'candidate-context', 'runtime-stage', 'runner', 'tokens', 'output-dir'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    for path, expected in ((args.baseline_context, BASELINE_SHA), (args.candidate_context, CANDIDATE_SHA), (args.tokens, TOKENS_SHA)):
        if sha(path) != expected:
            raise ValueError(f'Frozen artifact mismatch: {path}')
    runtime_manifest = args.runtime_stage / 'stage.json'
    if sha(runtime_manifest) != 'bb2b3635134280cd2edeccbb610793eda3bb4524d6ee11a5e7af6cf6a3574721':
        raise ValueError('Reviewed QAIRT/embedding stage manifest changed')
    runtime_entries = {x['path']: x for x in json.loads(runtime_manifest.read_text())['files']}
    output = args.output_dir
    output.mkdir(parents=True, exist_ok=False)
    (output / 'contexts').mkdir()
    sources = {'contexts/baseline.bin': args.baseline_context, 'contexts/candidate.bin': args.candidate_context,
               'short.int32le': args.tokens, 'direct_lfm2_qnn_runner': args.runner}
    for name in ('embedding-quant.u8', 'embedding-scales.f32le', 'embedding-zp.u8', 'libQnnHtp.so', 'libQnnSystem.so',
                 'libQnnHtpV73Stub.so', 'libQnnHtpV73Skel.so', 'libc++_shared.so'):
        sources[name] = args.runtime_stage / name
    entries = []
    for relative, source in sorted(sources.items()):
        before = sha(source)
        if relative not in ('contexts/baseline.bin', 'contexts/candidate.bin', 'short.int32le', 'direct_lfm2_qnn_runner'):
            expected = runtime_entries[relative]
            if before != expected['sha256'] or source.stat().st_size != expected['bytes']:
                raise ValueError(f'Reviewed runtime/embedding asset changed: {relative}')
        os.link(source, output / relative)
        copied, after = sha(output / relative), sha(source)
        if not before == copied == after:
            raise ValueError(f'Stage/source hash changed: {relative}')
        entries.append({'path': relative, 'source': str(source.resolve()), 'bytes': source.stat().st_size, 'sha256': copied})
    metadata = {'schema_version': 1, 'classification': 'ignored_native_ar171_prefill_pair_stage',
                'phone_execution': False, 'runtime': 'QAIRT2.49.40.260810',
                'expected_backend_build': 'v2.49.40.260810104044',
                'runtime_source_manifest_sha256': sha(runtime_manifest), 'ordered_phases': ['baseline', 'candidate'],
                'processes': 2, 'graph_executions_per_process': 1, 'ar1_executions': 0,
                'native_positions': 'INT64[1,171], values0..170', 'initial_state': 'fresh zero38states in each process',
                'snapshot': 'All41 actual native input buffers before graphExecute; all60 output buffers afterward, including finite-scan failures after successful execution',
                'timing_boundary': 'API call alone excludes input/output snapshot, copies, finite scan, argmax, bridge, profile and context setup/free; other phase boundaries reported separately',
                'host_storage': 'Read-only hardlinks of existing contexts/runtime/assets; no duplication of model/context data and no source writes',
                'payload_files': len(entries), 'logical_payload_bytes': sum(x['bytes'] for x in entries), 'files': entries,
                'claim_boundary': 'One ordered fresh-process physical pair when scheduled, not a statistical/warm campaign or quality/AR1 claim.'}
    (output / 'stage.json').write_text(json.dumps(metadata, indent=2, sort_keys=True) + '\n')
    paths = sorted(p for p in output.rglob('*') if p.is_file())
    (output / 'SHA256SUMS').write_text(''.join(f'{sha(p)}  {p.relative_to(output)}\n' for p in paths))
    print(json.dumps({'stage': str(output), 'stage_sha256': sha(output / 'stage.json'),
                      'manifest_sha256': sha(output / 'SHA256SUMS'), 'runner_sha256': sha(args.runner),
                      'logical_payload_bytes': metadata['logical_payload_bytes']}, indent=2))


if __name__ == '__main__':
    main()
