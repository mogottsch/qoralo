#!/usr/bin/env python3
"""Copy/hash a private candidate stage without importing a runtime or accessing ADB.

Payloads are independent copies, not links into the completed baseline. A failed
preparation is retained; existing stage directories are never overwritten.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import struct

HERE = Path(__file__).resolve()
TRACK = HERE.parents[1]
EXP = HERE.parents[3]
REPO = EXP.parents[1]
BASE = EXP / '.local/phone-stage'
COMPILE_RESULT = TRACK / 'results/value-precision-path-context-attempt-01/result.json'
COMPILE_RESULT_SHA = 'ca2d724d2d16c54459db8de4351e2d7681221083c7e53a8128d72ecc796e7228'
CONTEXT_SHA = '27e19e32ef479dfb39b53e6530cd25105c3c8e9ccf9fa4b9e9af4b5d770fabdd'
SOURCE_MANIFEST_SHA = 'e74f21a3478146b9afe332a42b3e39ec4b9c3dc38280bfab8ff94cce01172096'
CONTEXT_ALIAS = 'models/weight_sharing_model_ar128_ar1_cl4096_scl512_1_of_1.serialized.bin'
CONFIG = 'gemma4-e2b-htp-cl4096-greedy.json'
INPUTS = {
    'short': {'rendered_sha256': 'b286f8dda746e8056836a2e71049df866527bee51e368363dd80cfbe27e60e7a',
              'token_sha256': '31a85f9c813266bbbb3505a04a226a9b184882b636cc2f6f67193a6b1eb2ad78',
              'tokens': 170, 'workload_sha256': '81d23ec04cb821625d3717ab50db7df3d9821a8d2987f1eb107fc90df9d1f2ae'},
    'long': {'rendered_sha256': '450b519d417e29c4239e39aef856db1813d2580cd62e9db9adaae3d94ba8f260',
             'token_sha256': '3b5c04febbc9d55c529ee7ece510607203dbdc8256a6abc05ba0498cf4e52b64',
             'tokens': 1929, 'workload_sha256': '092840fbe879259110fa4d0b15bc383012f16b7b42a38d224b2ead231e86aad8'},
}
SCRIPT = f'''log create log1 verbose evidence/genie-verbose.log
profile create profile1
dialog config create config1 {CONFIG}
dialog config bind profile config1 profile1
dialog config bind log config1 log1
dialog create dialog1 config1
profile save profile1 evidence/setup-profile.json
dialog setMaxNumTokens dialog1 16
dialog query dialog1 prompts/short.txt evidence/short-output.txt
profile save profile1 evidence/short-profile.json
dialog free dialog1
dialog config free config1
profile free profile1
log free log1
exit
'''


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def copy_bound(source, dest, expected):
    if source.stat().st_size != expected['bytes']:
        raise RuntimeError(f'source size mismatch: {source.name}')
    dest.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    digest = hashlib.sha256()
    with source.open('rb') as src, dest.open('xb') as out:
        for chunk in iter(lambda: src.read(4 * 1024 * 1024), b''):
            digest.update(chunk)
            out.write(chunk)
    if digest.hexdigest() != expected['sha256'] or dest.stat().st_size != expected['bytes']:
        raise RuntimeError(f'copied payload identity mismatch: {source.name}; partial stage retained')
    # Independent files: chmod never changes any baseline/source inode.
    dest.chmod(0o555 if dest.name == 'genie-app' else 0o400)
    return {'bytes': dest.stat().st_size, 'sha256': digest.hexdigest()}


def write_input(path, data):
    with path.open('xb') as dst:
        dst.write(data)
    path.chmod(0o400)
    return {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def prepare(stage):
    if stage.exists():
        raise FileExistsError('frozen stage already exists; never overwrite it')
    if sha256(COMPILE_RESULT) != COMPILE_RESULT_SHA:
        raise RuntimeError('compiled-context provenance changed')
    evidence = json.loads(COMPILE_RESULT.read_text())
    if (evidence['context']['sha256'] != CONTEXT_SHA
            or not evidence['metadata_validation']['metadata_gate_passed']
            or evidence['metadata_validation']['cache_data_format_counts'] != {'QNN_TENSOR_DATA_FORMAT_FLAT_BUFFER': 120}):
        raise RuntimeError('candidate context/flat-buffer gate mismatch')
    source_manifest = BASE / 'runtime-manifest.json'
    if sha256(source_manifest) != SOURCE_MANIFEST_SHA:
        raise RuntimeError('accepted baseline runtime manifest changed')
    baseline = json.loads(source_manifest.read_text())
    stage.mkdir(parents=True, exist_ok=False, mode=0o700)
    files = {}
    for name, identity in sorted(baseline['files'].items()):
        source = BASE / name
        if name == CONTEXT_ALIAS:
            source = Path(evidence['context']['path'])
            identity = {'bytes': evidence['context']['bytes'], 'sha256': CONTEXT_SHA}
        files[name] = copy_bound(source, stage / name, identity)
    config = json.loads((stage / CONFIG).read_text())
    if config['dialog']['context']['bos-token'] != -1 or config['dialog']['max-num-tokens'] != 2048:
        raise RuntimeError('BOS or base output ceiling changed')
    if config['dialog']['engine']['model']['binary']['ctx-bins'] != ['./' + CONTEXT_ALIAS]:
        raise RuntimeError('context alias changed')
    if config['dialog']['engine']['backend']['type'] != 'QnnHtp':
        raise RuntimeError('unexpected neural backend')
    for tier, identity in INPUTS.items():
        for src, name, digest in (
            (EXP / f'protocol/rendered/{tier}.txt', f'prompts/{tier}.txt', identity['rendered_sha256']),
            (EXP / f'protocol/token-ids/{tier}.int32le', f'token-ids/{tier}.int32le', identity['token_sha256']),
            (REPO / f'protocols/android-llm-benchmark/workloads/inference-v1/{tier}.json', f'workloads/{tier}.json', identity['workload_sha256']),
        ):
            files[name] = copy_bound(src, stage / name, {'bytes': src.stat().st_size, 'sha256': digest})
        token_bytes = (stage / f'token-ids/{tier}.int32le').read_bytes()
        ids = struct.unpack('<' + 'i' * identity['tokens'], token_bytes)
        if ids[0] != 2 or ids[1] == 2 or identity['tokens'] + 2048 > 4096:
            raise RuntimeError('bound single-BOS/context-capacity proof mismatch')
    files['first-short.script'] = write_input(stage / 'first-short.script', SCRIPT.encode())
    manifest = {
        'schema_version': 1, 'classification': 'frozen_host_stage_preparation_only',
        'stage_id': stage.name, 'context_sha256': CONTEXT_SHA,
        'context_provenance_commit': 'ef0bbb0', 'context_result_sha256': COMPILE_RESULT_SHA,
        'source_runtime_manifest_sha256': SOURCE_MANIFEST_SHA,
        'files': files, 'payload_bytes': sum(x['bytes'] for x in files.values()),
        'copy_policy': 'Independent regular-file copies; inputs read-only, genie-app owner read/execute. Baseline never chmodded or linked.',
        'manifest_freeze_boundary': 'Hash-frozen inputs, not hardware-enforced immutability; reverify exact external manifest hash and all payloads before future use.',
        'bos_token_config': -1, 'automatic_bos_suppressed': True,
        'input_identities': INPUTS, 'token_identity_basis': 'Existing accepted tokenizer/token-ID/BOS proof; tokenizer not executed in this preparation.',
        'context_length': 4096, 'base_output_ceiling': 2048,
        'first_diagnostic': {'script': 'first-short.script', 'tier': 'short', 'queries': 1,
                             'output_ceiling': 16, 'canonical_campaign': False,
                             'model_instances': 1, 'fresh_dialog': True,
                             'request_timeout_seconds': 1800},
        'later_long': {'input_bytes_frozen': True, 'script_present': False, 'authorized': False,
                       'output_ceiling_if_separately_reviewed': 2048},
        'forbidden_paths': ['NativeKV/HMX cache layout', 'cache export/import/spec operations', 'hidden fallback'],
        'physical_execution': False, 'runtime_loaded': False, 'model_loaded': False,
        'adb_used': False, 'phone_authorized': False, 'registry_eligible': False,
    }
    write_input(stage / 'frozen-manifest.json', (json.dumps(manifest, indent=2, sort_keys=True) + '\n').encode())
    sums = ''.join(f'{v["sha256"]}  {k}\n' for k, v in sorted(files.items()))
    sums += f'{sha256(stage / "frozen-manifest.json")}  frozen-manifest.json\n'
    write_input(stage / 'SHA256SUMS', sums.encode())
    for directory in stage.rglob('*'):
        if directory.is_dir():
            directory.chmod(0o700)
    return manifest


def verify(stage, expected_manifest):
    if sha256(stage / 'frozen-manifest.json') != expected_manifest:
        raise RuntimeError('external frozen-manifest hash mismatch')
    manifest = json.loads((stage / 'frozen-manifest.json').read_text())
    sums = ''.join(f'{v["sha256"]}  {k}\n' for k, v in sorted(manifest['files'].items()))
    sums += f'{expected_manifest}  frozen-manifest.json\n'
    if (stage / 'SHA256SUMS').read_text() != sums:
        raise RuntimeError('checksum list differs from the frozen manifest')
    for name in ('frozen-manifest.json', 'SHA256SUMS'):
        path = stage / name
        if path.is_symlink() or stat.S_IMODE(path.stat().st_mode) & 0o222:
            raise RuntimeError('frozen metadata must be read-only regular files')
    actual_files = {str(p.relative_to(stage)) for p in stage.rglob('*') if p.is_file()}
    if actual_files != set(manifest['files']) | {'frozen-manifest.json', 'SHA256SUMS'}:
        raise RuntimeError('unexpected/missing stage files')
    for name, identity in manifest['files'].items():
        path = stage / name
        if path.is_symlink() or not path.resolve().is_relative_to(stage.resolve()):
            raise RuntimeError('stage input must be an owned regular copy')
        if path.stat().st_size != identity['bytes'] or sha256(path) != identity['sha256']:
            raise RuntimeError(f'frozen input mismatch: {name}')
        mode = stat.S_IMODE(path.stat().st_mode)
        if mode & 0o222:
            raise RuntimeError(f'frozen input is writable: {name}')
        if name == 'bin/genie-app' and mode != 0o555:
            raise RuntimeError('frozen runner must retain read-only executable mode0555')
    return manifest


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--stage-dir', type=Path, required=True)
    p.add_argument('--verify-only', action='store_true')
    p.add_argument('--expected-manifest-sha256')
    args = p.parse_args()
    stage = args.stage_dir.resolve()
    if not stage.is_relative_to((TRACK / '.local/frozen-stages').resolve()):
        p.error('stage directory must be under this track .local/frozen-stages')
    if args.verify_only:
        if not args.expected_manifest_sha256:
            p.error('--verify-only requires an externally pinned --expected-manifest-sha256')
        manifest = verify(stage, args.expected_manifest_sha256)
    else:
        os.umask(0o077)
        manifest = prepare(stage)
    print(json.dumps({'stage': str(stage), 'manifest_sha256': sha256(stage / 'frozen-manifest.json'),
                      'payload_bytes': manifest['payload_bytes'], 'phone_access': False,
                      'runtime_loaded': False, 'model_loaded': False}, indent=2))
