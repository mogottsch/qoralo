#!/usr/bin/env python3
"""Convert one unchanged Gemma FP16-IO ONNX with scoped precision-path encodings.

Run sequentially under the shared-host resource supervisor. No inference or phone.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import sys
import time

from prepare_value_precision_derivative import SOURCES, discover, digest
from value_precision_path import override_float16

HERE = Path(__file__).resolve()
TRACK = HERE.parents[1]
EXP = HERE.parents[3]


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--prepared', type=Path, required=True)
    p.add_argument('--run-dir', type=Path, required=True)
    args = p.parse_args()
    run = args.run_dir.resolve()
    run.mkdir(parents=True, exist_ok=False, mode=0o700)
    os.umask(0o077)
    prep = args.prepared.resolve()
    meta = json.loads((prep/'preparation.json').read_text())
    ar = meta['ar']
    origin, source_sha, encoding_sha = SOURCES[ar]
    source = TRACK/'.local/runs'/origin/f'onnx/ar{ar}_cl4096_1_of_1/ar{ar}_cl4096_1_of_1.onnx'
    data = source.with_suffix('.data')
    enc_path = prep/'full-candidate.encodings'
    start = time.monotonic()
    result = {'classification': 'started', 'ar': ar, 'inference': False, 'phone_access': False,
              'original_fp16_candidate_onnx_unchanged': True,
              'preparation_sha256': digest(prep/'preparation.json'),
              'script_sha256': digest(HERE), 'helper_sha256': digest(HERE.with_name('value_precision_path.py'))}
    def retain():
        result['elapsed_seconds'] = time.monotonic()-start
        result['ru_maxrss_kib'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        (run/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    retain()
    try:
        assert digest(source) == source_sha
        assert digest(source.with_suffix('.encodings')) == encoding_sha
        assert digest(enc_path) == meta['full_candidate_encodings_sha256']
        # One full data hash before expensive loading; never modify the checkpoint.
        expected_data = 'b9b73b984c2258099bc77ce6d1e2aa92d12bb67abe456e5ef509136d7494a65d'
        assert digest(data) == expected_data
        result['inputs'] = {'onnx_path': str(source), 'onnx_sha256': source_sha,
                            'original_encodings_sha256': encoding_sha,
                            'new_encodings_path': str(enc_path), 'new_encodings_sha256': digest(enc_path),
                            'data_path': str(data), 'data_sha256': expected_data}
        import onnx
        model = onnx.load(source, load_external_data=False)
        plan = discover(model)
        assert plan == meta['all_layers']
        old = json.loads(source.with_suffix('.encodings').read_text())
        expected, changes = override_float16(old, set().union(*(set(x['float16_override_names']) for x in plan)))
        assert expected == json.loads(enc_path.read_text())
        assert changes == meta['full_changes']
        result['precision_scope'] = plan
        result['encoding_change_count'] = len(changes)
        del model, old, expected
        import gc
        gc.collect()
        retain()
        sys.path.insert(0, str(EXP/'tools'))
        from qairt_constant_compat import install
        install()
        from qairt.gen_ai_api.gen_ai_builder_factory import GenAIBuilderFactory
        from qairt.gen_ai_api.builders.gen_ai_utils import get_input_layout
        from qairt.optimizer.onnx.graph import ExportedFiles
        ckpt = EXP/'.local/checkpoint/extracted/gemma_4_e2b_it_w4a16'
        builder = GenAIBuilderFactory.create(str(ckpt), 'HTP', cache_root=str(run/'dlc-cache'),
                    tokenizer_path=str(ckpt/'tokenizer.json'), config_path=str(ckpt/'config.json'))
        builder.set_targets(['chipset:SM8550'])
        builder._conversion_config.input_tensor_config = get_input_layout(source)
        builder._conversion_config.output_tensor_config = []
        result['conversion_config'] = builder._conversion_config.model_dump(mode='json')
        result['calibration_config'] = None if builder._calibration_config is None else builder._calibration_config.model_dump(mode='json')
        retain()
        exported = ExportedFiles(onnx_path=source, data_path=data, encodings_path=enc_path)
        converted = builder.convert(exported, builder._conversion_config, builder._calibration_config)
        dlc = Path(converted.module.path)
        result['dlc'] = {'path': str(dlc), 'bytes': dlc.stat().st_size, 'sha256': digest(dlc)}
        result['classification'] = 'full_dlc_converted_internal_precision_gate_pending'
        result['internal_precision_validated'] = False
        retain()
        return 0
    except Exception as e:
        result['classification'] = 'full_conversion_error'
        result['error'] = {'type': type(e).__name__, 'message': str(e)}
        retain()
        raise


if __name__ == '__main__':
    raise SystemExit(main())
