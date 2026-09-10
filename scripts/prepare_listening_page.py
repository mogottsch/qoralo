#!/usr/bin/env python3
"""Create a local player ONLY for an existing, exact-hash PCM WAV. No device/model/server work."""
import argparse
from datetime import datetime, timezone
import hashlib
import html
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import wave

REPO = Path(__file__).resolve().parents[1]
ROOT = Path.home() / '.cache/vibevoice-listening'


def atomic_text(path, value):
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.page-')
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(value)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def prepare(run_id, wav_path, expected_sha, title='Listening sample', note='', root=ROOT):
    """Never creates a pending/failure page or overwrites any existing sample directory."""
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,120}', run_id):
        raise ValueError('Use a safe distinct run ID')
    if not wav_path or not re.fullmatch(r'[a-f0-9]{64}', expected_sha or ''):
        raise ValueError('An existing WAV and expected SHA-256 are required; no audio means no page')
    if len(note) > 1000 or len(title) > 200:
        raise ValueError('Use a short safe summary, not raw logs')
    source = Path(wav_path).resolve()
    if not source.is_file():
        raise ValueError('WAV does not exist; no listening page created')
    folder = root / run_id
    folder.mkdir(parents=True, mode=0o700)  # Exclusive: existing/accepted pages are untouched.
    fd, name = tempfile.mkstemp(dir=folder, prefix='.wav-')
    committed_audio = False
    try:
        digest = hashlib.sha256()
        with os.fdopen(fd, 'wb') as dst, source.open('rb') as src:
            for chunk in iter(lambda: src.read(1024 * 1024), b''):
                digest.update(chunk)
                dst.write(chunk)
        if digest.hexdigest() != expected_sha:
            raise ValueError('WAV hash mismatch; no audio/page published')
        with wave.open(name, 'rb') as wav:
            channels, width, rate, frames = wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getnframes()
            if wav.getcomptype() != 'NONE' or min(channels, width, rate, frames) <= 0:
                raise ValueError('Not a nonempty PCM WAV')
            actual = 0
            while chunk := wav.readframes(65536):
                actual += len(chunk)
            if actual != frames * channels * width:
                raise ValueError('Truncated WAV payload')
        os.replace(name, folder / 'sample.wav')
        committed_audio = True
        prepared = datetime.now(timezone.utc).isoformat(timespec='seconds')
        receipt = dict(schema_version=1, run_id=run_id, state='audio_available', title=title,
                       note=note, prepared_at=prepared, listening_verdict='not_reviewed',
                       wav=dict(source_path=str(source), path='sample.wav', sha256=expected_sha,
                                bytes=(folder/'sample.wav').stat().st_size, sample_rate_hz=rate,
                                channels=channels, bits_per_sample=width*8, frames=frames,
                                duration_seconds=frames/rate))
        esc = lambda text: html.escape(str(text), quote=True)
        body = ('<h2 class="state">Audio available · not reviewed</h2>'
                '<audio controls preload="metadata" src="sample.wav"></audio>'
                '<p><a href="sample.wav" download>Open / save the exact WAV</a></p>'
                f'<dl><dt>Actual duration / format</dt><dd>{frames/rate:.6f} s · '
                f'{rate:,} Hz · {channels} channel(s) · PCM{width*8}</dd>'
                f'<dt>SHA-256</dt><dd><code>{expected_sha}</code></dd></dl>')
        fields = {'TITLE':esc(title), 'RUN':esc(run_id), 'BODY':body, 'NOTE':esc(note), 'PREPARED':esc(prepared)}
        template = (REPO/'docs/listening-sample.template.html').read_text()
        page = re.sub(r'@@([A-Z_]+)@@', lambda m: fields[m[1]], template)
        atomic_text(folder/'listening-page.json', json.dumps(receipt, ensure_ascii=False, indent=2)+'\n')
        atomic_text(folder/'index.html', page)
        return folder/'index.html', receipt
    finally:
        if os.path.exists(name):
            os.unlink(name)
        if not committed_audio:
            folder.rmdir()  # Only this call's empty scratch folder; never an original/sample.


def open_page(page):
    # xdg-open can remain attached to a newly started browser. Never wait for that
    # browser or let a shell timeout kill it. Opening does not start audio playback.
    return subprocess.Popen(['xdg-open', str(page)], stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            start_new_session=True, close_fds=True).pid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--wav', required=True, type=Path)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--title', default='Listening sample')
    parser.add_argument('--note', default='')
    parser.add_argument('--open', action='store_true')
    args = parser.parse_args()
    page, receipt = prepare(args.run_id, args.wav, args.sha256, args.title, args.note)
    print(json.dumps({'page':str(page), 'url':page.as_uri(), 'wav':receipt['wav'],
                      'listening_verdict':receipt['listening_verdict']}, indent=2))
    if args.open:
        print(json.dumps({'opener_pid': open_page(page)}), flush=True)


if __name__ == '__main__':
    main()
