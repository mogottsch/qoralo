#!/usr/bin/env python3
"""Freeze an independent exact-long stage using only accepted short-stage bytes.

File copying/hashing only. No tokenizer replay, SDK/runtime, model load or ADB.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct

from prepare_frozen_genie_stage import copy_bound, write_input, sha256

TRACK = Path(__file__).resolve().parents[1]
SOURCE = TRACK / '.local/frozen-stages/stage-freeze-20260910T105830Z-01'
SOURCE_DIGEST = '584841604ecf97a1a916c9a7f765e49ff9f7a2ee751a61fda9e9e6588f02fe25'
CONTEXT_SHA = '1d80d01637f032ab0c5ec3135e9458c648b4c18e034574a56d42dbfbdbdca9f8'
GATE_A = TRACK / 'results/phone-return-short-attempt-01/result.json'
GATE_A_SHA = '1290cc51948e82fd974b175c46a1a67cd0ff0db382ad1db047993f9ad7849aff'
COPY_HELPER_SHA = '34c56e7a2ec92c68a7a781ca7c7230a3ad8ce60d249dbd93e6c4cd359b403ccf'
SCRIPT = '''log create log1 verbose evidence/genie-verbose.log
profile create profile1
dialog config create config1 gemma4-e2b-htp-cl4096-greedy.json
dialog config bind profile config1 profile1
dialog config bind log config1 log1
dialog create dialog1 config1
profile save profile1 evidence/setup-profile.json
dialog setMaxNumTokens dialog1 2048
dialog query dialog1 prompts/long.txt evidence/long-output.txt
profile save profile1 evidence/long-profile.json
dialog free dialog1
dialog config free config1
profile free profile1
log free log1
exit
'''


def prepare(stage):
    if stage.exists():
        raise FileExistsError('separate frozen stage already exists; no overwrite')
    if sha256(TRACK / 'tools/prepare_frozen_genie_stage.py') != COPY_HELPER_SHA:
        raise RuntimeError('accepted copy/verification helper changed')
    if sha256(SOURCE / 'frozen-manifest.json') != SOURCE_DIGEST or sha256(GATE_A) != GATE_A_SHA:
        raise RuntimeError('accepted source stage/GateA identity changed')
    source = json.loads((SOURCE / 'frozen-manifest.json').read_text())
    gate = json.loads(GATE_A.read_text())
    if source['context_sha256'] != CONTEXT_SHA or gate['analysis_issues']:
        raise RuntimeError('accepted context/GateA gate mismatch')
    stage.mkdir(parents=True, exist_ok=False, mode=0o700)
    excluded = {'first-short.script', 'prompts/short.txt', 'token-ids/short.int32le', 'workloads/short.json'}
    files = {}
    for name, identity in sorted(source['files'].items()):
        if name in excluded:
            continue
        files[name] = copy_bound(SOURCE / name, stage / name, identity)
    files['exact-long.script'] = write_input(stage / 'exact-long.script', SCRIPT.encode())
    ids = struct.unpack('<1929i', (stage / 'token-ids/long.int32le').read_bytes())
    config = json.loads((stage / 'gemma4-e2b-htp-cl4096-greedy.json').read_text())
    workload = json.loads((stage / 'workloads/long.json').read_text())
    if ids[:2] != (2, 105) or config['dialog']['context']['bos-token'] != -1:
        raise RuntimeError('long input/BOS binding mismatch')
    if config['dialog']['max-num-tokens'] != 2048 or 1929 + 2048 > config['dialog']['context']['size']:
        raise RuntimeError('ceiling/capacity changed')
    manifest = {
        'schema_version': 1, 'classification': 'frozen_host_exact_long_stage_only',
        'stage_id': stage.name, 'context_sha256': CONTEXT_SHA,
        'source_short_stage_digest': SOURCE_DIGEST, 'gate_a_commit': '81f4ede',
        'gate_a_result_sha256': GATE_A_SHA, 'files': files,
        'payload_bytes': sum(v['bytes'] for v in files.values()),
        'copy_policy': 'Independent readonly copies; runner0555. Source short stage and all model/config/tokenizer bytes unchanged.',
        'input_identities': {'long': source['input_identities']['long']},
        'tokenizer_replayed_now': False, 'bos_token_config': -1,
        'context_length': 4096, 'base_output_ceiling': 2048,
        'diagnostic': {'script': 'exact-long.script', 'tier': 'long', 'queries': 1,
                       'output_ceiling': 2048, 'model_instances': 1, 'fresh_dialog': True,
                       'request_timeout_seconds': 1800, 'canonical_campaign': False,
                       'no_short_request': True, 'automatic_retry': False},
        'input_boundary': 'Unchanged1929-token rendered long bytes/IDs from accepted tokenizer proof; no truncation, prefix or padding.',
        'forbidden_paths': source['forbidden_paths'],
        'runtime_loaded': False, 'model_loaded': False, 'adb_used': False,
        'phone_authorized': False, 'registry_eligible': False,
    }
    write_input(stage / 'frozen-manifest.json', (json.dumps(manifest, indent=2, sort_keys=True) + '\n').encode())
    sums = ''.join(f'{item["sha256"]}  {name}\n' for name, item in sorted(files.items()))
    sums += f'{sha256(stage / "frozen-manifest.json")}  frozen-manifest.json\n'
    write_input(stage / 'SHA256SUMS', sums.encode())
    for path in stage.rglob('*'):
        if path.is_dir(): path.chmod(0o700)
    return manifest


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--stage-dir', required=True, type=Path)
    args = p.parse_args()
    stage = args.stage_dir.resolve()
    if not stage.is_relative_to((TRACK / '.local/frozen-stages').resolve()):
        p.error('stage must be inside this track .local/frozen-stages')
    os.umask(0o077)
    manifest = prepare(stage)
    print(json.dumps({'stage': str(stage), 'manifest_sha256': sha256(stage / 'frozen-manifest.json'),
                      'payload_bytes': manifest['payload_bytes'], 'phone_access': False,
                      'runtime_loaded': False, 'model_loaded': False}, indent=2))
