#!/usr/bin/env python3
"""Pinned, sequential host CPU synthesis. Run one --model per process."""
import argparse
import datetime
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import sys
import time
import urllib.request

# Set thread limits before importing any numerical runtime.
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
import numpy as np
from comparison import render_html, save_native, save_playable, sha256

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', required=True, choices=['phonon', 'supertonic'])
    parser.add_argument('--output', type=Path, default=ROOT, help='New output root, never overwrite samples')
    args = parser.parse_args()
    signal.alarm(1800)
    pins = json.loads((ROOT / 'protocol/models.json').read_text())[args.model]
    inputs = json.loads((ROOT / 'protocol/inputs.json').read_text())
    assert len(inputs['cases']) == 3
    versions = {d.metadata['Name'].lower(): d.version for d in importlib.metadata.distributions()}
    for line in (ROOT / 'requirements.in').read_text().splitlines():
        name, version = line.split('==')
        if importlib.metadata.version(name) != version:
            raise RuntimeError(f'Runtime pin mismatch: {line}')
    if sys.version_info[:2] != (3, 11):
        raise RuntimeError('Use Python 3.11 (Unicode 14 app frontend authority)')
    out = args.output.resolve()
    sample_dir = out / 'samples' / args.model
    result_path = out / 'results' / f'{args.model}.json'
    if sample_dir.exists() or result_path.exists():
        raise FileExistsError('Use a new --output directory; prior renders are immutable')
    model_dir = ROOT / '.local/models' / args.model
    for item in pins['files']:
        path = model_dir / item['path']
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(path.suffix + '.download')
            urllib.request.urlretrieve(f'https://huggingface.co/{pins["repo_id"]}/resolve/{pins["revision"]}/{item["path"]}', temporary)
            if sha256(temporary) != item['sha256']:
                raise RuntimeError(f'Download hash mismatch: {item["path"]}')
            temporary.rename(path)
        if path.stat().st_size != item['bytes'] or sha256(path) != item['sha256']:
            raise RuntimeError(f'Model pin mismatch: {item["path"]}')
    started = time.perf_counter()
    if args.model == 'phonon':
        import ptts
        ptts.set_num_threads(1)
        tts = ptts.TTS(str(model_dir), device='cpu', quant='q8', voice='default', lang='en',
                       temperature=0.3, seed=4242424242424242, cfg_coef=None, eos_threshold=4.0,
                       rewrites='default', conditions=None)
        assert tts.device == 'cpu' and tts.quant == 'q8_0' and tts.sample_rate == 24000
        runtime = {'package': 'ptts', 'version': ptts.__version__, 'build': ptts.build_info(),
                   'source_commit': 'cc0c32bcad4e79121e98cb16d9a1b19f87772e82',
                   'registered_voices': tts.voices, 'loaded_device': tts.device, 'loaded_quant': tts.quant}
        settings = {'voice': 'default', 'voice_asset': 'default-voice.safetensors', 'language': 'en',
                    'temperature': 0.3, 'seed_per_case': 4242424242424242, 'cfg_coef': None,
                    'eos_threshold': 4.0, 'rewrites': 'default', 'conditions': 'checkpoint defaults; no overrides',
                    'decode_steps': 1, 'post_process': [], 'cpu_tensor_threads': 1,
                    'segmentation': 'ptts native sentence/token chunk planner; no external splitting or added silence'}
        source_files = [Path(ptts.__file__), *Path(ptts.__file__).parent.glob('*.so')]
    else:
        import supertonic
        from supertonic import TTS
        from supertonic.utils import chunk_text
        expected = json.loads((ROOT.parent / '0037-supertonic-provider-pipeline/protocol/inputs.json').read_text())['upstream']['files']
        source_files = [Path(supertonic.__file__).parent / entry['file'] for entry in expected]
        for entry, path in zip(expected, source_files):
            assert sha256(path) == entry['sha256'], f'Upstream SDK source changed: {path.name}'
        tts = TTS(model='supertonic-3', model_dir=model_dir, auto_download=False,
                  intra_op_num_threads=1, inter_op_num_threads=1)
        style = tts.get_voice_style('M1')
        providers = {name: getattr(tts.model, name).get_providers() for name in ['dp_ort', 'text_enc_ort', 'vector_est_ort', 'vocoder_ort']}
        assert all(value == ['CPUExecutionProvider'] for value in providers.values())
        runtime = {'package': 'supertonic', 'version': versions['supertonic'], 'providers': providers,
                   'source_commit': '908a56486e821e833a80530ff0cae3ad0b046fce'}
        settings = {'voice': 'M1/SID5', 'voice_asset': 'voice_styles/M1.json', 'language': 'en', 'steps': 8,
                    'speed': 1.05, 'max_chunk_length': 300, 'silence_duration': 0.3, 'gap_frames': 13230,
                    'rng': 'NumPy legacy MT19937 np.random.randn cast float32', 'seed_per_case': 20260911,
                    'wave_extent': 'FULL_NATIVE_VOCODER', 'intra_op_threads': 1, 'inter_op_threads': 1,
                    'precision': 'original dynamic FP32 ONNX; not QNN app contexts'}
    setup_seconds = time.perf_counter() - started
    report = {'schema_version': 1, 'status': 'generated_not_listening_reviewed', 'human_listening_accepted': False,
              'scope': 'Host CPU listening samples only. No phone, S23, NPU or speed comparison claim.',
              'generated_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'qoralo_base_commit': '07b197580a73411019fbb291eb16b4ffafacbca8',
              'model': pins, 'runtime': runtime, 'settings': settings,
              'python': sys.version, 'platform': platform.platform(), 'machine': platform.machine(),
              'dependencies': versions, 'libsndfile': __import__('soundfile').__libsndfile_version__,
              'runtime_source_files': [{'file': p.name, 'sha256': sha256(p)} for p in source_files],
              'recipe_sources': {'generate.py': sha256(Path(__file__)), 'comparison.py': sha256(ROOT / 'tools/comparison.py'),
                                 'requirements.lock': sha256(ROOT / 'requirements.lock'), 'inputs.json': sha256(ROOT / 'protocol/inputs.json')},
              'load_wall_seconds_diagnostic_only': setup_seconds, 'samples': []}
    sample_dir.mkdir(parents=True)
    result_path.parent.mkdir(parents=True, exist_ok=True)
    for case in inputs['cases']:
        text = case['text']
        assert hashlib.sha256(text.encode()).hexdigest() == case['sha256']
        start = time.perf_counter()
        if args.model == 'phonon':
            normalized = ptts.normalize(text, lang='en', rewrites='default')
            pcm = tts.synth(text, voice='default', temperature=0.3, seed=4242424242424242, cfg_coef=None)
            frontend = {'normalized_text': normalized, 'normalization_api': 'ptts.normalize; same language/rules as synthesis',
                        'note': 'ptts planner handles terminal punctuation and chunking internally; not externally rewritten'}
            prediction = None
        else:
            np.random.seed(20260911)
            chunks = chunk_text(text, 300)
            processed = [tts.model.text_processor._preprocess_text(t, 'en') for t in chunks]
            # Match the current app admission bound as well as the upstream recipe.
            assert all(len(t) <= 320 for t in processed), 'Text exceeds current app text bucket'
            frontend = {'raw_chunks': chunks, 'processed_chunks': processed, 'text_extents': list(map(len, processed))}
            pcm, duration = tts.synthesize(text, voice_style=style, total_steps=8, speed=1.05,
                                            max_chunk_length=300, silence_duration=0.3, lang='en')
            pcm = pcm[0]  # remove the batch axis, never crop the native waveform
            prediction = float(duration[0])
        elapsed = time.perf_counter() - start
        native_path = sample_dir / f'{case["id"]}.native.wav'
        playable_path = sample_dir / f'{case["id"]}.wav'
        raw = save_native(native_path, pcm, tts.sample_rate)
        playable = save_playable(playable_path, pcm, tts.sample_rate)
        report['samples'].append({'id': case['id'], 'input_sha256': case['sha256'], 'input_utf8_bytes': case['utf8_bytes'],
                                  'frontend': frontend, 'native': dict(raw, path=str(native_path.relative_to(out))),
                                  'playable': dict(playable, path=str(playable_path.relative_to(out))),
                                  'sdk_predicted_duration_seconds_not_emitted_extent': prediction,
                                  'generation_wall_seconds_diagnostic_only': elapsed})
        # Persist each completed sample before the next inference.
        result_path.write_text(json.dumps(report, indent=2) + '\n')
        print(f'{args.model}/{case["id"]}: {raw["duration_seconds"]:.6f}s, peak={raw["peak"]:.6f}, finite={raw["finite"]}', flush=True)
    (out / 'protocol').mkdir(exist_ok=True)
    if out != ROOT:
        for name in ['inputs.json', 'models.json']:
            shutil.copy2(ROOT / 'protocol' / name, out / 'protocol' / name)
    (out / 'index.html').write_text(render_html(inputs['cases']))
    print(f'Provenance: {result_path}', flush=True)


if __name__ == '__main__':
    main()
