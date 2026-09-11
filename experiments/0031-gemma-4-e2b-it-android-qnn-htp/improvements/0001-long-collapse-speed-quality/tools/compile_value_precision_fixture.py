#!/usr/bin/env python3
"""Small host-only SM8550/v73 compile of a precision-gated source island."""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import resource
import time


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--converted', type=Path, required=True)
    p.add_argument('--run-dir', type=Path, required=True)
    args = p.parse_args()
    root = args.run_dir.resolve()
    root.mkdir(parents=True, exist_ok=False, mode=0o700)
    os.umask(0o077)
    bound = json.loads((args.converted/'result.json').read_text())
    assert bound['candidate'] and bound['gate']['passed']
    path = Path(bound['dlc']['path'])
    assert digest(path) == bound['dlc']['sha256']
    track = Path(__file__).resolve().parents[1]
    config_path = track/'results/global-value-fp16-context-attempt-01/raw/compiler-config.json'
    assert digest(config_path) == '36c3f95dae0cfa8f2b9da510b24cfd9a2b4278a777ba602a9ed351bc4d63225e'
    config_dict = json.loads(config_path.read_text())
    result = {'scope': 'one source-island fixture, not the full Gemma model',
              'classification': 'started', 'inference': False, 'phone_access': False,
              'dlc': bound['dlc'], 'converted_result_sha256': digest(args.converted/'result.json'),
              'compiler_config_template_sha256': digest(config_path), 'script_sha256': digest(Path(__file__))}
    start = time.monotonic()
    def retain():
        result['elapsed_seconds'] = time.monotonic()-start
        result['ru_maxrss_kib'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        (root/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    retain()
    try:
        import qairt
        model = qairt.Model.load(path)
        graph_config = copy.deepcopy(config_dict['graph_custom_configs'][0])
        graph_config['name'] = model.name
        config_dict['graph_custom_configs'] = [graph_config]
        result['compiler_config'] = config_dict
        result['graph_alias'] = model.name
        retain()
        compiled = qairt.compile(model, config=qairt.CompileConfig(**config_dict))
        context = Path(compiled.module.path)
        result['context'] = {'path': str(context), 'bytes': context.stat().st_size, 'sha256': digest(context)}
        result['classification'] = 'source_island_sm8550_v73_host_compile_passed'
        result['internal_compiled_kernel_precision_proven'] = False
        result['physical_execution_proven'] = False
        retain()
        return 0
    except Exception as e:
        result['classification'] = 'source_island_host_compile_error'
        result['error'] = {'type': type(e).__name__, 'message': str(e)}
        retain()
        raise


if __name__ == '__main__':
    raise SystemExit(main())
