#!/usr/bin/env python3
"""Assemble ONE new data-only pack from independently pinned inputs; no model/runtime calls."""
from __future__ import annotations
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil

from prepare_wiring_gate import PROJECT
from prepare_local_runtime import sha256, verify_file

PACK_ID = 'supertonic-3-t2048-l2048-parity'
AUTHORITY = PROJECT / 'config/trusted-supertonic-long.json'
OLD_ROOT = PROJECT / '.local/model-packs/supertonic-3/current'
NEW_ROOT = PROJECT / '.local/model-packs' / PACK_ID / 'current'


def manifest_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def expected_pack(authority_path=AUTHORITY, old_root=OLD_ROOT):
    authority = json.loads(authority_path.read_text())
    assert authority['schemaVersion'] == 1 and authority['packId'] == PACK_ID
    export_path = PROJECT.parent / authority['contextExport']['path']
    verify_file(export_path, authority['contextExport'], 'independent eight-context export authority')
    export = json.loads(export_path.read_text())
    assert export['namespace'] == PACK_ID and export['context_file_count'] == 8
    assert not export['descriptor_bytes_changed']
    verify_file(old_root / 'manifest.json', {'sha256': authority['companionSourceManifestSha256']}, 'accepted companion manifest')
    original = json.loads((old_root / 'manifest.json').read_text())
    expected = deepcopy(original)
    expected.update(id=PACK_ID, version=authority['version'], contract=authority['contract'])
    exported = {item['layout_path']: item for item in export['files']}
    assert len(exported) == 8
    assert set(exported) == {f'contexts/{component}-context{suffix}' for component in ('duration', 'text', 'vector', 'vocoder') for suffix in ('.onnx', '_qnn.bin')}
    for component, value in export['components'].items():
        assert not value['descriptor_rebinding_required']
        assert value['descriptor_external_binary_basename'] == f'{component}-context_qnn.bin'
    sources = {}
    for entry in expected['files']:
        path = entry['path']
        if path in exported:
            item = exported[path]
            entry.update(bytes=item['bytes'], sha256=item['sha256'])
            sources[path] = Path(item['source_path'])
        else:
            assert path.startswith('assets/')
            sources[path] = old_root / path
    assert len(sources) == 13 and sum(p.startswith('assets/') for p in sources) == 5
    return expected, sources, original


def verify_pack(root, expected):
    assert root.is_dir() and not root.is_symlink()
    assert not any(p.is_symlink() for p in root.rglob('*'))
    assert (root / 'manifest.json').read_bytes() == manifest_bytes(expected)
    assert {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()} == {'manifest.json', *(e['path'] for e in expected['files'])}
    for entry in expected['files']:
        verify_file(root / entry['path'], entry, entry['path'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, required=True)
    args = parser.parse_args()
    args.evidence.mkdir(parents=True, exist_ok=False)
    expected, sources, original = expected_pack()
    # Validate all old bytes before/after; never link to or write the old pack or Ben's exports.
    verify_pack(OLD_ROOT, original)
    for entry in expected['files']:
        verify_file(sources[entry['path']], entry, 'source ' + entry['path'])
    NEW_ROOT.mkdir(parents=True, exist_ok=False)
    for entry in expected['files']:
        output = NEW_ROOT / entry['path']; output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(sources[entry['path']], output)
    (NEW_ROOT / 'manifest.json').write_bytes(manifest_bytes(expected))
    verify_pack(NEW_ROOT, expected)
    verify_pack(OLD_ROOT, original)
    proof = {
        'kind': 'new data-only pack; copy/hash/JSON only', 'packId': PACK_ID, 'root': str(NEW_ROOT),
        'manifestSha256': sha256(NEW_ROOT / 'manifest.json'), 'manifestBytes': (NEW_ROOT / 'manifest.json').stat().st_size,
        'authoritySha256': sha256(AUTHORITY), 'oldManifestSha256': sha256(OLD_ROOT / 'manifest.json'),
        'oldPackAllFileHashesUnchanged': True, 'exactUnmodifiedContextCopies': 8, 'exactCompanionCopies': 5,
        'descriptorRewrite': False, 'modelOrRuntimeOrDeviceCalls': 0,
        'sourceBindings': [{**entry, 'origin': str(sources[entry['path']])} for entry in expected['files']],
        'warningBoundary': 'four nonfatal StridedSlice tiler warnings retained by Ben; not warning-free, no physical/fidelity/listening claim',
    }
    (args.evidence / 'pack-proof.json').write_text(json.dumps(proof, indent=2) + '\n')
    shutil.copy2(NEW_ROOT / 'manifest.json', args.evidence / 'pack-manifest.json')
    print(json.dumps({k: proof[k] for k in ('root', 'manifestSha256', 'authoritySha256', 'exactUnmodifiedContextCopies', 'exactCompanionCopies')}, indent=2))


if __name__ == '__main__':
    main()
