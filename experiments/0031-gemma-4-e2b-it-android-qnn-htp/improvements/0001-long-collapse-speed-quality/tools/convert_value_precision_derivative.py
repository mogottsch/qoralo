#!/usr/bin/env python3
"""Convert one exact-source island (not Gemma weights) and gate its DLC edges."""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import subprocess
import sys
import time

from value_precision_path import fixture_gate, parse_dlc_csv


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--prepared', type=Path, required=True)
    p.add_argument('--run-dir', type=Path, required=True)
    p.add_argument('--candidate', action='store_true')
    args = p.parse_args()
    prep = args.prepared.resolve()
    root = args.run_dir.resolve()
    root.mkdir(parents=True, exist_ok=False, mode=0o700)
    os.umask(0o077)
    metadata = json.loads((prep/'preparation.json').read_text())
    model = prep/'derivative.onnx'
    assert sha(model) == metadata['derivative_onnx_sha256']
    enc = prep/('candidate.encodings' if args.candidate else 'control.encodings')
    result = {'ar': metadata['ar'], 'candidate': args.candidate, 'inference': False, 'phone_access': False,
              'scope': metadata['derivative_scope'], 'preparation_sha256': sha(prep/'preparation.json'),
              'source_model_sha256': sha(model), 'encodings_sha256': sha(enc),
              'script_sha256': sha(Path(__file__)),
              'helper_sha256': sha(Path(__file__).with_name('value_precision_path.py'))}
    start = time.monotonic()
    def retain():
        result['elapsed_seconds'] = time.monotonic()-start
        result['parent_ru_maxrss_kib'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        result['children_ru_maxrss_kib'] = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
        (root/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    retain()
    try:
        exp = Path(__file__).resolve().parents[3]
        sys.path.insert(0, str(exp/'tools'))
        from qairt_constant_compat import install
        install()
        import qairt
        config = {'float_precision': 32, 'float_bias_precision': 32,
                  'input_tensor_config': [{'name': name, 'layout': 'NONTRIVIAL'} for name in metadata['derivative_inputs']],
                  'output_tensor_config': [], 'use_quantize_v2': False}
        result['requested_conversion_config'] = copy.deepcopy(config)
        retain()
        converted = qairt.convert(model, encodings=enc, backend='HTP', **config)
        result['resolved_conversion_config'] = config
        dlc = root/'derivative.dlc'
        shutil.copyfile(converted.module.path, dlc)
        result['dlc'] = {'path': str(dlc), 'bytes': dlc.stat().st_size, 'sha256': sha(dlc)}
        retain()
        csv = root/'derivative.csv'
        cmd = [sys.executable, str(Path(os.environ['QAIRT_SDK_ROOT'])/'bin/x86_64-linux-clang/qairt-dlc-info'),
               '-i', str(dlc), '--save', str(csv)]
        result['inspection_command'] = cmd
        with (root/'dlc-info.stdout').open('w') as out, (root/'dlc-info.stderr').open('w') as err:
            info = subprocess.run(cmd, stdout=out, stderr=err, timeout=60, close_fds=True)
        result['inspection_exit'] = info.returncode
        if info.returncode:
            raise RuntimeError('DLC inspection failed')
        result['csv_sha256'] = sha(csv)
        result['gate'] = fixture_gate(parse_dlc_csv(csv), args.candidate, metadata['derivative_outputs'][0])
        result['classification'] = 'source_derivative_precision_gate_passed' if result['gate']['passed'] else 'source_derivative_precision_gate_failed'
        retain()
        return 0 if result['gate']['passed'] else 2
    except Exception as e:
        result['classification'] = 'source_derivative_error'
        result['error'] = {'type': type(e).__name__, 'message': str(e)}
        retain()
        raise


if __name__ == '__main__':
    raise SystemExit(main())
