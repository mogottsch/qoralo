#!/usr/bin/env python3
"""Fresh independent stage using the accepted preparer with four fixed bindings.

No SDK/model load, tokenizer execution, ADB or change to an older frozen stage.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import types

TRACK = Path(__file__).resolve().parents[1]
LEGACY = TRACK/'tools/prepare_frozen_genie_stage.py'
LEGACY_SHA = '34c56e7a2ec92c68a7a781ca7c7230a3ad8ce60d249dbd93e6c4cd359b403ccf'
RESULT_SHA = 'ca2d724d2d16c54459db8de4351e2d7681221083c7e53a8128d72ecc796e7228'
CONTEXT_SHA = '27e19e32ef479dfb39b53e6530cd25105c3c8e9ccf9fa4b9e9af4b5d770fabdd'
REPLACEMENTS = (
    ("COMPILE_RESULT = TRACK / 'results/global-value-fp16-context-attempt-01/result.json'",
     "COMPILE_RESULT = TRACK / 'results/value-precision-path-context-attempt-01/result.json'"),
    ("COMPILE_RESULT_SHA = '929de4c0bb7b5ddcbd0c2b229b0bf1eced324e01fdabd0ecf47e3aac9baaad56'",
     f"COMPILE_RESULT_SHA = '{RESULT_SHA}'"),
    ("CONTEXT_SHA = '1d80d01637f032ab0c5ec3135e9458c648b4c18e034574a56d42dbfbdbdca9f8'",
     f"CONTEXT_SHA = '{CONTEXT_SHA}'"),
    ("'context_provenance_commit_gemma_slice': 'f637a74'", "'context_provenance_commit': 'ef0bbb0'"),
)


def materialize(source: str) -> str:
    if hashlib.sha256(source.encode()).hexdigest() != LEGACY_SHA:
        raise ValueError('accepted stage-preparer source hash changed')
    for before, after in REPLACEMENTS:
        if source.count(before) != 1:
            raise ValueError('stage binding replacement is not unique')
        source = source.replace(before, after)
    return source


def load_preparer():
    source = materialize(LEGACY.read_text())
    module = types.ModuleType('precision_path_stage_preparer')
    module.__file__ = str(LEGACY)
    exec(compile(source, str(LEGACY), 'exec'), module.__dict__)
    return module, source


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--stage-dir', type=Path, required=True)
    p.add_argument('--evidence-dir', type=Path, required=True)
    args = p.parse_args()
    stage, evidence = args.stage_dir.resolve(), args.evidence_dir.resolve()
    if not stage.is_relative_to((TRACK/'.local/frozen-stages').resolve()):
        p.error('stage must be a fresh directory under the owned frozen-stages root')
    if stage.exists():
        raise FileExistsError('refusing an in-place stage rewrite')
    evidence.mkdir(parents=True, exist_ok=False, mode=0o700)
    os.umask(0o077)
    module, source = load_preparer()
    (evidence/'materialized-preparer.py').write_text(source)
    (evidence/'bindings.json').write_text(json.dumps({
        'original_source': str(LEGACY), 'original_source_sha256': LEGACY_SHA,
        'materialized_source_sha256': hashlib.sha256(source.encode()).hexdigest(),
        'module_file_for_path_resolution': str(LEGACY),
        'replacements': REPLACEMENTS, 'context_sha256': CONTEXT_SHA,
        'context_result_sha256': RESULT_SHA, 'context_commit': 'ef0bbb0',
        'source_or_old_stages_modified': False, 'phone_access': False,
    }, indent=2)+'\n')
    manifest = module.prepare(stage)
    digest = module.sha256(stage/'frozen-manifest.json')
    module.verify(stage, digest)
    result = {'stage': str(stage), 'manifest_sha256': digest,
              'payload_bytes': manifest['payload_bytes'], 'payload_files': len(manifest['files']),
              'context_sha256': CONTEXT_SHA, 'verified': True,
              'phone_access': False, 'inference': False}
    (evidence/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
