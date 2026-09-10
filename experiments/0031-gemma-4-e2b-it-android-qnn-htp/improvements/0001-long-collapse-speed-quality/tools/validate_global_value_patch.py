#!/usr/bin/env python3
"""Independently compare a prepared patch to hash-bound source ONNX/encodings.

This proves patch scope only, not the converted DLC/runtime datatype or fidelity.
"""
import argparse
import hashlib
import json
from pathlib import Path

import onnx

EXP = Path(__file__).resolve().parents[3]
SOURCE = EXP / '.local/qairt-2.49.40-position-id-aligned'
LAYERS = (4, 9, 14)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(run):
    receipt = json.loads((run / 'patch-receipt.json').read_text())
    results = []
    for ar, identity in zip((1, 128), receipt['variants'], strict=True):
        stem = f'ar{ar}_cl4096_1_of_1'
        old_dir, new_dir = SOURCE / stem, run / 'onnx' / stem
        for suffix, key in (('onnx', 'onnx'), ('encodings', 'encodings')):
            assert digest(old_dir / f'{stem}.{suffix}') == identity[f'source_{key}_sha256']
            assert digest(new_dir / f'{stem}.{suffix}') == identity[f'candidate_{key}_sha256']
        old_enc = json.loads((old_dir / f'{stem}.encodings').read_text())
        new_enc = json.loads((new_dir / f'{stem}.encodings').read_text())
        old_entries = {x['name']: x for x in old_enc['activation_encodings']}
        new_entries = {x['name']: x for x in new_enc['activation_encodings']}
        removed = {f'past_value_{i}_h0_in' for i in LAYERS}
        if ar == 1:
            removed |= {f'past_value_{i}_h0_out' for i in LAYERS}
        assert set(old_entries) - set(new_entries) == removed
        assert new_entries == {k: v for k, v in old_entries.items() if k not in removed}
        assert {k: v for k, v in old_enc.items() if k != 'activation_encodings'} == {
            k: v for k, v in new_enc.items() if k != 'activation_encodings'}
        old = onnx.load(old_dir / f'{stem}.onnx', load_external_data=False)
        new = onnx.load(new_dir / f'{stem}.onnx', load_external_data=False)
        changed_io = []
        for role in ('input', 'output'):
            old_io = {x.name: x for x in getattr(old.graph, role)}
            new_io = {x.name: x for x in getattr(new.graph, role)}
            assert old_io.keys() == new_io.keys()
            selected = {f'past_value_{i}_h0_{"in" if role == "input" else "out"}' for i in LAYERS}
            for name in old_io:
                expected = type(old_io[name])()
                expected.CopyFrom(old_io[name])
                if name in selected:
                    expected.type.tensor_type.elem_type = onnx.TensorProto.FLOAT16
                    changed_io.append({'role': role, 'name': name, 'datatype': 'FLOAT16',
                                       'dimensions': [d.dim_value for d in expected.type.tensor_type.shape.dim]})
                assert expected == new_io[name], (ar, name)
        old_init = {x.name: x.SerializeToString() for x in old.graph.initializer}
        new_init = {x.name: x.SerializeToString() for x in new.graph.initializer}
        removed_init = {f'past_value_{i}_h0_out__{suffix}' for i in LAYERS for suffix in ('scale', 'zero_point')} if ar == 1 else set()
        assert set(old_init) - set(new_init) == removed_init
        assert new_init == {k: v for k, v in old_init.items() if k not in removed_init}
        results.append({'ar': ar, 'exact_removed_encodings': sorted(removed),
                        'other_encodings_unchanged': True, 'other_io_unchanged': True,
                        'changed_io': changed_io, 'weight_initializers_unchanged': True,
                        'removed_boundary_initializers': sorted(removed_init)})
    return {'classification': 'host_patch_scope_only', 'variants': results,
            'dlc_datatypes_proven': False, 'inference': False, 'phone_access': False}


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--run-dir', type=Path, required=True)
    args = p.parse_args()
    result = check(args.run_dir)
    (args.run_dir / 'patch-validation.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
