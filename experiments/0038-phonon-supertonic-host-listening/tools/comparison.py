"""Small native-audio preservation and static audition helpers (no inference)."""
import hashlib
import html
from pathlib import Path

import numpy as np
import soundfile as sf


def sha256(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save_playable(path, pcm, rate):
    """Unity-gain PCM16 derivative; refuse clipping rather than normalize it."""
    if not np.isfinite(pcm).all() or np.max(np.abs(pcm)) >= 1:
        raise ValueError('PCM16 export would clip; preserve raw output and stop')
    path = Path(path)
    with path.open('xb') as stream:
        sf.write(stream, pcm, rate, format='WAV', subtype='PCM_16')
    return {'sha256': sha256(path), 'subtype': 'PCM_16', 'gain': 1.0,
            'processing': 'libsndfile float32 to PCM16 only; no dither, normalization, trimming, resampling or time manipulation'}


def render_html(cases):
    sections = []
    for case in cases:
        players = []
        for model, label in [('phonon', 'Phonon 31m · q8 · stock default voice · 24 kHz'),
                             ('supertonic', 'Supertonic 3 · FP32 CPU · M1/SID5 · 44.1 kHz')]:
            src = f'samples/{model}/{case["id"]}.wav'
            raw = f'samples/{model}/{case["id"]}.native.wav'
            players.append(f'<div><h3>{html.escape(label)}</h3><audio controls preload="metadata" src="{src}"></audio>'
                           f'<p><a href="{src}">PCM16 WAV</a> · <a href="{raw}">Original native float WAV</a></p></div>')
        sections.append(f'<section><h2>{html.escape(case["title"])}</h2><pre>{html.escape(case["text"])}</pre>'
                        f'<div class="players">{"".join(players)}</div></section>')
    return '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Phonon vs Qoralo Supertonic — host listening samples</title>
<style>body{font:17px/1.55 system-ui;background:#f5f5f0;color:#18232c;max-width:1100px;margin:40px auto;padding:0 20px}h1{line-height:1.2}section{background:white;border:1px solid #ced6d5;padding:24px;margin:24px 0;border-radius:12px}pre{white-space:pre-wrap;font:inherit}.players{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:28px}audio{width:100%}a{color:#185d70}</style>
<h1>Phonon 31m / Qoralo Supertonic 3</h1>
<p><strong>All speech is machine generated. Host CPU listening comparison only — not S23, Android or NPU performance evidence.</strong></p>
<p>Three identical original input strings; different documented stock voices, not a matched-speaker test. Supertonic follows Qoralo’s current provider recipe on its upstream FP32 CPU SDK, not the app’s QNN backend. Phonon uses its native English normalization; Supertonic uses its own frontend. No output normalization, trimming, resampling or time stretching. Supertonic’s model speed 1.05 and 0.3 s inter-segment gaps are recipe settings, not post-processing.</p>
<p>Players use direct PCM16 encodings at native rates with unity gain; full original float arrays are preserved alongside them. No subjective review or acceptance is claimed. Listen at a comfortable volume; native output levels differ.</p>
<p><a href="README.md">Recipe, licensing and limitations</a> · <a href="protocol/inputs.json">Exact texts</a> · <a href="results/phonon.json">Phonon provenance</a> · <a href="results/supertonic.json">Supertonic provenance</a> · <a href="results/verification.json">Independent technical verification</a></p>
''' + ''.join(sections) + '</html>\n'


def save_native(path, pcm, rate):
    """Write the returned float32 mono array without DSP or integer clipping."""
    path = Path(path)
    if path.exists():
        raise FileExistsError(path)
    pcm = np.asarray(pcm)
    if pcm.dtype != np.float32 or pcm.ndim != 1 or not pcm.size:
        raise ValueError('Expected nonempty native float32 mono PCM')
    if not np.isfinite(pcm).all() or not np.any(pcm):
        raise ValueError('Nonfinite or silent native output')
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        sf.write(stream, pcm, rate, format='WAV', subtype='FLOAT')
    decoded, actual_rate = sf.read(path, dtype='float32')
    if actual_rate != rate or not np.array_equal(pcm, decoded):
        raise AssertionError('Native WAV did not preserve samples')
    return {'sha256': sha256(path), 'pcm_f32le_sha256': hashlib.sha256(pcm.astype('<f4').tobytes()).hexdigest(),
            'frames': int(pcm.size), 'sample_rate': rate, 'channels': 1, 'subtype': 'FLOAT',
            'duration_seconds': pcm.size / rate, 'finite': True,
            'peak': float(np.max(np.abs(pcm))), 'rms': float(np.sqrt(np.mean(pcm.astype(np.float64)**2))),
            'samples_at_or_above_full_scale': int(np.count_nonzero(np.abs(pcm) >= 1))}
