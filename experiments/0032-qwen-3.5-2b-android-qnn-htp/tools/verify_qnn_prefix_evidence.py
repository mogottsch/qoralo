#!/usr/bin/env python3
"""Verify retained prefix outputs/checkpoints; never loads or runs a model/PTE."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
from pathlib import Path
import struct
import subprocess
from types import SimpleNamespace


def verify(directory: Path, tensor_values=False):
    directory = directory.resolve()
    exp = directory.parents[1]
    raw = json.loads((directory / 'raw/result.json').read_text())
    supervisor = json.loads((directory / 'raw/supervisor.json').read_text())
    journal_bytes = (directory / 'raw/progress.jsonl').read_bytes()
    rows = [json.loads(line) for line in journal_bytes.splitlines()]
    compared = [x for x in rows if x['event'] == 'compared']
    if raw['status'] != 'bounded_segment_completed' or supervisor['exit_code'] != 0:
        raise ValueError('Prefix did not complete')
    if (raw['start_position'], raw['end_position_exclusive'], raw['state_origin']) != (0, 4, 'zero_initialization'):
        raise ValueError('Wrong prefix/state origin')
    if [r['position'] for r in compared] != [0, 1, 2, 3] or len(rows) != 8:
        raise ValueError('Missing/duplicate positional events')
    if hashlib.sha256(journal_bytes).hexdigest() != raw['progress_artifact']['sha256']:
        raise ValueError('Journal hash mismatch')
    input_bytes = (exp / 'protocol/token-ids/short.int32le').read_bytes()
    if hashlib.sha256(input_bytes).hexdigest() != raw['binding']['token_ids_sha256']:
        raise ValueError('Canonical input binding mismatch')
    ids = struct.unpack('<174i', input_bytes)
    reference_manifest_bytes = (exp / 'results/host-histogram-full-short-20260910/compression-manifest.json').read_bytes()
    if hashlib.sha256(reference_manifest_bytes).hexdigest() != raw['binding']['reference_manifest_sha256']:
        raise ValueError('Full QDQ reference manifest binding mismatch')
    reference_entries = {e['position']: e for e in json.loads(reference_manifest_bytes)['files'] if 'position' in e}
    params_path = directory / 'raw/params.json'
    if hashlib.sha256(params_path.read_bytes()).hexdigest() != raw['binding']['params_sha256']:
        raise ValueError('Parameter hash mismatch')
    manifest = json.loads((directory / 'compression-manifest.json').read_text())['files']
    table = {(e['kind'], e.get('position')): e for e in manifest}
    if len(table) != 13 or len(manifest) != 13:
        raise ValueError('Expected4 output bundles,4 checkpoints,4 QDQ tensors and telemetry')

    def data(entry, capture=False):
        path = directory / entry['compressed_path']
        with path.open('rb') as f:
            digest = hashlib.file_digest(f, 'sha256').hexdigest()
        if digest != entry['compressed_sha256'] or path.stat().st_size != entry['compressed_bytes']:
            raise ValueError('Compressed hash/size mismatch')
        proc = subprocess.Popen(['zstd', '-q', '-dc', str(path)], stdout=subprocess.PIPE)
        h = hashlib.sha256(); size = 0; buffer = io.BytesIO() if capture else None
        with proc.stdout:
            for block in iter(lambda: proc.stdout.read(1048576), b''):
                h.update(block); size += len(block)
                if buffer is not None: buffer.write(block)
        if proc.wait() or h.hexdigest() != entry['raw_sha256'] or size != entry['raw_bytes']:
            raise ValueError('Raw recovery mismatch')
        if buffer is not None: buffer.seek(0)
        return buffer

    for entry in manifest: data(entry)
    torch = states = config = None
    if tensor_values:
        import torch
        from diagnose_quantized_output import make_state_templates
        from replay_saved_qdq import advance_state
        torch.set_num_threads(1)
        config = SimpleNamespace(**json.loads(params_path.read_text()))
        states = make_state_templates(config, 4096)
    numerical = []
    for position, row in enumerate(compared):
        if row['input_token'] != ids[position]: raise ValueError('Input token mismatch')
        header_path = directory / f'raw/checkpoints/position-{position:03d}.json'
        header_data = header_path.read_bytes(); header = json.loads(header_data)
        if hashlib.sha256(header_data).hexdigest() != row['checkpoint']['sha256']:
            raise ValueError('Checkpoint header hash mismatch')
        if header['binding'] != raw['binding'] or header['next_position'] != position + 1:
            raise ValueError('Checkpoint prefix/route mismatch')
        if header['backend_state'] != 'qnn_x86_own_propagated_state' or header['prior_segment_checkpoint'] is not None:
            raise ValueError('Unexpected state origin/resume')
        prefix = struct.pack(f'<{position + 1}i', *ids[:position + 1])
        if hashlib.sha256(prefix).hexdigest() != header['consumed_prefix_sha256']:
            raise ValueError('Consumed input-prefix mismatch')
        bundle = table[('qnn_73_outputs', position)]; state_entry = table[('qnn_48_states', position)]
        if table[('qdq_logits', position)]['raw_sha256'] != reference_entries[position]['raw_sha256']:
            raise ValueError('Paired QDQ tensor is not from the bound reference trajectory')
        if row['raw_outputs']['sha256'] != bundle['raw_sha256'] or header['state_artifact']['sha256'] != state_entry['raw_sha256']:
            raise ValueError('Raw output/state binding mismatch')
        if tensor_values:
            outputs = torch.load(data(bundle, True), map_location='cpu', weights_only=True)
            saved = torch.load(data(state_entry, True), map_location='cpu', weights_only=True)
            reference = torch.load(data(table[('qdq_logits', position)], True), map_location='cpu', weights_only=True)
            if len(outputs) != 73 or len(saved) != 48: raise ValueError('Wrong output/state ABI')
            advance_state(config, states, outputs, position)
            for expected, actual in zip(states, saved):
                torch.testing.assert_close(expected, actual, rtol=0, atol=0, equal_nan=True)
            a, b = reference.float().reshape(-1), outputs[0].float().reshape(-1)
            if not bool(torch.isfinite(a).all() and torch.isfinite(b).all()): raise ValueError('Nonfinite logits')
            comp = {'cosine': float(torch.nn.functional.cosine_similarity(a,b,dim=0)),
                    'max_abs': float((a-b).abs().max()), 'mean_abs': float((a-b).abs().mean()),
                    'qdq_argmax': int(a.argmax()), 'qnn_argmax': int(b.argmax())}
            for name, value in comp.items():
                if not math.isclose(value, row['comparison'][name], rel_tol=0, abs_tol=1e-6):
                    raise ValueError(f'Comparison mismatch: {position}/{name}')
            numerical.append({'position': position, 'comparison': comp,
                              'state_checkpoint_materialization_exact': True,
                              'all73_output_tensors_finite': all(bool(torch.isfinite(x).all()) for x in outputs)})
    return {'journal_positions_verified': 4, 'raw_recoveries_verified': 13,
            'checkpoint_headers_verified': 4, 'model_or_pte_loaded_or_executed': False,
            'tensor_values_checked': tensor_values, 'numerical': numerical}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('directory', type=Path)
    p.add_argument('--tensor-values', action='store_true')
    args = p.parse_args()
    print(json.dumps(verify(args.directory, args.tensor_values), indent=2))


if __name__ == '__main__': main()
