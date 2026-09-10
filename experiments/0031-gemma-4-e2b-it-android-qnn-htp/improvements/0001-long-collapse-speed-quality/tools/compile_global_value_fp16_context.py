#!/usr/bin/env python3
"""Execute the hash-pinned accepted compiler recipe with only bound DLC substitutions.

The compile observer records/checks arguments but does not change options. No
inference or phone operation is implemented. Run under run_host_guarded.py.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

HERE = Path(__file__).resolve()
TRACK = HERE.parents[1]
EXP = HERE.parents[3]
SDK = Path('/home/moritz/opt/qairt/2.49.40.260810')
LEGACY = EXP / 'tools/compile_qairt_cache_aligned.py'
LEGACY_SHA = 'cf997a64ec255d53b51f4b26e42ff426e8a06acce1c8626077be79698272a67b'
PAIR = TRACK / 'results/global-value-fp16-attempt-06/result.json'
PAIR_SHA = 'e44860de456dc7718233813f28a1529dcb1add2f21a4a859ab402f990bf22a03'
EXPECTED = {
    1: (2356848948, '4e67d80ea342088f5235a9238dc209739d8961083b08895fa066d6857687a6cc'),
    128: (2356859020, '48fc15f0cbec88963f7b4d0f9007b82ca5a1e1d812ca320ceec776e00a917b64'),
}


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-dir', type=Path, required=True)
    args = parser.parse_args()
    run = args.run_dir.resolve()
    if (run / 'context-cache').exists() or (run / 'compile-inputs.json').exists():
        raise RuntimeError('refusing an in-place compilation retry')
    if os.environ.get('QAIRT_SDK_ROOT') != str(SDK):
        raise RuntimeError('QAIRT SDK environment mismatch')
    scratch = Path(os.environ['QAIRT_TMP_DIR']).resolve()
    if scratch.parent != run or not scratch.is_dir():
        raise RuntimeError('compile scratch must be owned by the fresh run')
    if sha256(LEGACY) != LEGACY_SHA or sha256(PAIR) != PAIR_SHA:
        raise RuntimeError('accepted recipe or paired-DLC evidence hash mismatch')
    evidence = json.loads(PAIR.read_text())
    inspector = load_module('pair_inspector', TRACK / 'tools/inspect_global_value_dlc.py')
    prior = TRACK / 'results/global-value-fp16-attempt-05'
    current = PAIR.parent
    ar1 = inspector.compare(1, prior / 'raw/inspection-02/ar1.csv.gz', prior / 'raw/baseline-ar1.csv.gz')
    ar128 = inspector.compare(128, current / 'raw/inspection-01/ar128.csv.gz', current / 'raw/baseline-ar128.csv.gz')
    pair = inspector.require_cache_pair(ar1, ar128)
    if pair != evidence['paired_cache_gate']:
        raise RuntimeError('recomputed pair gate differs from accepted evidence')
    models = {item['ar']: item for item in evidence['candidate_models']}
    paths = {}
    for ar, (size, digest) in EXPECTED.items():
        item = models[ar]
        path = Path(item['path']).resolve()
        if (item['sha256'] != digest or item['bytes'] != size or not path.is_file()
                or path.stat().st_size != size or sha256(path) != digest):
            raise RuntimeError(f'AR{ar} DLC identity mismatch')
        paths[ar] = path
    (run / 'compile-inputs.json').write_text(json.dumps({
        'paired_result_path': str(PAIR), 'paired_result_sha256': PAIR_SHA,
        'paired_evidence_commit': 'ce3b021', 'recomputed_pair_gate': pair,
        'models': [models[ar] for ar in (1, 128)],
        'legacy_recipe_path': str(LEGACY), 'legacy_recipe_sha256': LEGACY_SHA,
        'legacy_recipe_commit': 'bda9216',
        'substitutions': ['DLC paths and their expected hashes', 'fresh output/cache/scratch directories'],
        'compile_options_overridden': False, 'inference': False, 'phone_access': False,
    }, indent=2) + '\n')

    sys.path.insert(0, str(EXP / 'tools'))
    legacy = load_module('accepted_compile_recipe', LEGACY)
    legacy.COMPILE_CACHE = run / 'context-cache'
    legacy.EXPECTED_DLCS = {ar: digest for ar, (_, digest) in EXPECTED.items()}
    legacy.find_dlc = lambda ar: paths[ar]
    from qairt.gen_ai_api.gen_ai_builder_factory import GenAIBuilderFactory
    real_create = GenAIBuilderFactory.create
    invocation_count = 0

    def observe_create(*factory_args, **factory_kwargs):
        builder = real_create(*factory_args, **factory_kwargs)
        real_compile = builder.compile

        def observe_compile(actual_models, config):
            nonlocal invocation_count
            invocation_count += 1
            if invocation_count != 1:
                raise RuntimeError('only one native context compilation is authorized')
            names = [m.name for m in actual_models]
            expected_names = [f'ar{ar}_cl4096_1_of_1' for ar in (1, 128)]
            if names != expected_names or [g.name for g in config.graph_custom_configs] != names:
                raise RuntimeError('accepted graph aliases/order changed')
            if [Path(m.module.path).resolve() for m in actual_models] != [paths[1], paths[128]]:
                raise RuntimeError('unexpected DLC substitution')
            if builder._prepare_embedding_lut is not False:
                raise RuntimeError('accepted embedding preparation option changed')
            (run / 'compiler-config.json').write_text(json.dumps(config.model_dump(mode='json'), indent=2) + '\n')
            print(json.dumps({'event': 'accepted_recipe_observer', 'invocation': invocation_count,
                              'graph_aliases': names, 'options_mutated_by_observer': False}), flush=True)
            # The original accepted recipe set every option, including weight
            # sharing, SM8550/v73 and its two graph configs. Observe, do not edit.
            compiled = real_compile(actual_models, config)
            path = Path(compiled.module.path)
            (run / 'compiled-context.json').write_text(json.dumps({
                'path': str(path), 'bytes': path.stat().st_size, 'sha256': sha256(path),
                'name': compiled.name, 'compile_invocations': invocation_count,
                'physical_execution_proven': False,
            }, indent=2) + '\n')
            return compiled
        builder.compile = observe_compile
        return builder

    with patch.object(GenAIBuilderFactory, 'create', side_effect=observe_create):
        legacy.main()


if __name__ == '__main__':
    main()
