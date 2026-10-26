#!/usr/bin/env python3
"""Read-only FFmpeg verifier: deliberately imports no synthesis/export code.

Without --report, prints JSON only and never changes delivered artifacts.
"""
import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import subprocess

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def inspect_wav(path, expected, codec):
    actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    assert actual_hash == expected['sha256'], f'SHA256 mismatch: {path}'
    probe = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams', '-of', 'json', str(path)]))
    assert len(probe['streams']) == 1
    stream = probe['streams'][0]
    assert stream['codec_name'] == codec, f'codec mismatch: {path}'
    assert int(stream['sample_rate']) == expected['sample_rate']
    assert stream['channels'] == expected['channels'] == 1
    # No -ar, -ac, filters, seek or duration options: decode every original frame.
    raw = subprocess.check_output(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(path), '-f', 'f32le', '-acodec', 'pcm_f32le', '-'])
    pcm = np.frombuffer(raw, dtype='<f4')
    assert pcm.size == expected['frames'], f'frames mismatch: {path}'
    assert np.isfinite(pcm).all(), f'nonfinite: {path}'
    peak = float(np.max(np.abs(pcm)))
    assert 0 < peak < 1, f'silent or sample-clipping: {path}'
    pcm_hash = hashlib.sha256(raw).hexdigest()
    if 'pcm_f32le_sha256' in expected:
        assert pcm_hash == expected['pcm_f32le_sha256'], f'PCM mismatch: {path}'
        assert peak == expected['peak']
    return {'path': str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else path.name,
            'sha256': actual_hash, 'pcm_f32le_sha256': pcm_hash, 'codec': codec,
            'sample_rate': int(stream['sample_rate']), 'channels': 1, 'frames': int(pcm.size),
            'duration_seconds': pcm.size / int(stream['sample_rate']), 'finite': True, 'peak': peak,
            'samples_at_or_above_full_scale': int(np.count_nonzero(np.abs(pcm) >= 1))}, pcm


class PageAssets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.audio = []
        self.links = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'audio':
            assert 'controls' in attrs and 'autoplay' not in attrs
            self.audio.append(attrs['src'])
        if tag == 'a':
            self.links.append(attrs['href'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT)
    parser.add_argument('--report', type=Path, help='Optional new verification JSON path; refuses overwrite')
    args = parser.parse_args()
    out = args.output.resolve()
    inputs = json.loads((out / 'protocol/inputs.json').read_text())
    cases = {c['id']: c for c in inputs['cases']}
    assert len(cases) == len(inputs['cases']) == 3
    assert cases['canonical']['sha256'] == '424b38073a00cf48e4c3ebaa246aec0b6549b3ed56a1bf7cfa26d037fb29db67'
    for case in cases.values():
        assert hashlib.sha256(case['text'].encode()).hexdigest() == case['sha256']
    report = {'status': 'passed_technical_checks_only', 'human_listening_accepted': False,
              'scope': 'Read-only independent FFmpeg decode, probe, peak and hash checks; no ASR or subjective judgment.',
              'ffmpeg': subprocess.check_output(['ffmpeg', '-version'], text=True).splitlines()[0], 'files': []}
    expected_files = set()
    expected_players = set()
    for model in ['phonon', 'supertonic']:
        provenance = json.loads((out / 'results' / f'{model}.json').read_text())
        assert len(provenance['samples']) == 3
        assert {s['id'] for s in provenance['samples']} == set(cases)
        for sample in provenance['samples']:
            assert sample['input_sha256'] == cases[sample['id']]['sha256']
            assert sample['input_utf8_bytes'] == len(cases[sample['id']]['text'].encode())
            native = sample['native']
            playable = sample['playable']
            assert native['path'] == f'samples/{model}/{sample["id"]}.native.wav'
            assert playable['path'] == f'samples/{model}/{sample["id"]}.wav'
            raw_check, raw = inspect_wav(out / native['path'], native, 'pcm_f32le')
            pcm_check, pcm = inspect_wav(out / playable['path'], dict(playable, frames=native['frames'],
                                        sample_rate=native['sample_rate'], channels=1), 'pcm_s16le')
            assert raw.shape == pcm.shape
            error = float(np.max(np.abs(raw.astype(np.float64) - pcm.astype(np.float64))))
            assert error <= 1 / 32768, 'Playable encoding is not unity gain within one PCM16 LSB'
            # True-peak analysis of the actual playable file, not its source array.
            process = subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-nostats', '-i', str(out / playable['path']),
                                      '-filter:a', 'ebur128=peak=true', '-f', 'null', '-'], capture_output=True, text=True, check=True)
            true_peaks = re.findall(r'Peak:\s+(-?[\d.]+) dBFS', process.stderr)
            assert true_peaks, 'FFmpeg did not report true peak'
            pcm_check['ffmpeg_true_peak_dbfs_rounded'] = float(true_peaks[-1])
            assert pcm_check['ffmpeg_true_peak_dbfs_rounded'] < 0
            pcm_check['max_absolute_error_vs_native'] = error
            report['files'].extend([raw_check, pcm_check])
            expected_files.update([native['path'], playable['path']])
            expected_players.add(playable['path'])
    assert {str(p.relative_to(out)) for p in (out / 'samples').rglob('*.wav')} == expected_files
    page = PageAssets()
    page.feed((out / 'index.html').read_text())
    assert len(page.audio) == 6 and set(page.audio) == expected_players
    for href in page.links:
        target = out / href
        if args.report and target.resolve() == args.report.resolve() and not target.exists():
            continue  # this exact new report is written only after every check passes
        assert target.is_file(), f'Broken local link: {href}'
    report.update(wav_files=len(report['files']), matched_text_pairs=3, html_players=6, local_links_exist=True)
    text = json.dumps(report, indent=2) + '\n'
    if args.report:
        with args.report.open('x') as stream:
            stream.write(text)
    print(text)


if __name__ == '__main__':
    main()
