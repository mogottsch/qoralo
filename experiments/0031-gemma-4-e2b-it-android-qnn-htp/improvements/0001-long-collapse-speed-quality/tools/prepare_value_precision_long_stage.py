#!/usr/bin/env python3
"""Independent exact-long stage, bound to this candidate's actual short success."""
import argparse
import hashlib
import json
from pathlib import Path
import types
import os

from prepare_frozen_genie_stage import verify, sha256

TRACK = Path(__file__).resolve().parents[1]
LEGACY = TRACK/'tools/prepare_long_genie_stage.py'
LEGACY_SHA = '8a9631b4e515bee4b93f5dd8739f37698738060799c3f7eeee741d2022c64b97'
SHORT_RESULT_SHA = '6bd6114f2fcaddf10db666727bc36712ea9aa1b6dae46ab640eba8bfd24d0f3f'
SHORT_RESULT = TRACK/'results/value-precision-path-phone-short-attempt-01/result.json'
REPLACEMENTS = (
    ('stage-freeze-20260910T105830Z-01', 'value-path-short-20260911T115043Z-01'),
    ('584841604ecf97a1a916c9a7f765e49ff9f7a2ee751a61fda9e9e6588f02fe25',
     '206ca960a69f915f81cb5c61dde5684259f8fbee8a37e14ef8b8bbf9fcafc78b'),
    ('1d80d01637f032ab0c5ec3135e9458c648b4c18e034574a56d42dbfbdbdca9f8',
     '27e19e32ef479dfb39b53e6530cd25105c3c8e9ccf9fa4b9e9af4b5d770fabdd'),
    ('results/phone-return-short-attempt-01/result.json',
     'results/value-precision-path-phone-short-attempt-01/result.json'),
    ('1290cc51948e82fd974b175c46a1a67cd0ff0db382ad1db047993f9ad7849aff', SHORT_RESULT_SHA),
    ("'gate_a_commit': '81f4ede'", "'gate_a_commit': 'df07102'"),
)


def load_preparer():
    source = LEGACY.read_text()
    if hashlib.sha256(source.encode()).hexdigest() != LEGACY_SHA:
        raise RuntimeError('original long-stage preparer changed')
    if sha256(SHORT_RESULT) != SHORT_RESULT_SHA:
        raise RuntimeError('new candidate short result changed')
    gate = json.loads(SHORT_RESULT.read_text())
    if gate['analysis_issues'] or not gate['observations']['query_completion_observed_beyond_exit_code']:
        raise RuntimeError('new candidate short prerequisite not met')
    for before, after in REPLACEMENTS:
        if source.count(before) != 1:
            raise RuntimeError('long-stage binding not unique')
        source = source.replace(before, after)
    module = types.ModuleType('gemma_value_long_preparer')
    module.__file__ = str(LEGACY)
    exec(compile(source, str(LEGACY), 'exec'), module.__dict__)
    return module, source


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stage-dir', required=True, type=Path)
    p.add_argument('--evidence-dir', required=True, type=Path)
    args = p.parse_args()
    stage, evidence = args.stage_dir.resolve(), args.evidence_dir.resolve()
    if not stage.is_relative_to((TRACK/'.local/frozen-stages').resolve()):
        p.error('stage must be a fresh directory under the owned frozen-stages root')
    if stage.exists():
        raise FileExistsError('refusing to rewrite an existing stage')
    os.umask(0o077)
    evidence.mkdir(parents=True, exist_ok=False, mode=0o700)
    module, source = load_preparer()
    (evidence/'materialized-preparer.py').write_text(source)
    (evidence/'bindings.json').write_text(json.dumps({'original_source_sha256': LEGACY_SHA,
        'materialized_source_sha256': hashlib.sha256(source.encode()).hexdigest(),
        'replacements': REPLACEMENTS, 'original_module_file': str(LEGACY),
        'adapter_sha256': sha256(Path(__file__)), 'phone_access': False}, indent=2)+'\n')
    manifest = module.prepare(stage)
    digest = sha256(stage/'frozen-manifest.json')
    verify(stage, digest)
    result = {'stage': str(stage), 'manifest_sha256': digest, 'verified': True,
              'payload_bytes': manifest['payload_bytes'], 'payload_files': len(manifest['files']),
              'short_result_sha256': SHORT_RESULT_SHA, 'phone_access': False, 'inference': False}
    (evidence/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
