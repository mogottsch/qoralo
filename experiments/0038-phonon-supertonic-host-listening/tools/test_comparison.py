import hashlib
import importlib.util
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('comparison', ROOT / 'tools/comparison.py')
comparison = importlib.util.module_from_spec(spec)


def test_native_float_is_preserved_and_overwrite_refused(tmp_path):
    spec.loader.exec_module(comparison)
    x = np.array([0.0, 0.125, -0.375, 0.01], dtype=np.float32)
    out = tmp_path / 'test.wav'
    report = comparison.save_native(out, x, 24000)
    y, rate = sf.read(out, dtype='float32')
    assert np.array_equal(x, y)
    assert rate == 24000
    assert report['frames'] == 4
    assert report['duration_seconds'] == 4 / 24000
    assert report['peak'] == 0.375
    assert report['sha256'] == hashlib.sha256(out.read_bytes()).hexdigest()
    with pytest.raises(FileExistsError):
        comparison.save_native(out, x, 24000)


@pytest.mark.parametrize('x', [np.array([], dtype=np.float32), np.zeros(4, dtype=np.float32),
                                  np.array([np.nan], dtype=np.float32), np.array([np.inf], dtype=np.float32),
                                  np.ones((1, 2), dtype=np.float32), np.array([0.2], dtype=np.float64)])
def test_invalid_native_arrays_are_rejected(tmp_path, x):
    spec.loader.exec_module(comparison)
    with pytest.raises(ValueError):
        comparison.save_native(tmp_path / 'invalid.wav', x, 24000)
    assert not (tmp_path / 'invalid.wav').exists()


def test_html_escapes_text_and_labels_native_and_playable_assets():
    spec.loader.exec_module(comparison)
    page = comparison.render_html([{'id': 'case', 'title': 'A < B', 'text': '<unsafe> & text'}])
    assert '<unsafe>' not in page
    assert '&lt;unsafe&gt; &amp; text' in page
    assert page.count('<audio ') == 2
    assert 'samples/phonon/case.wav' in page
    assert 'samples/supertonic/case.wav' in page
    assert 'autoplay' not in page


def test_pcm16_is_unity_gain_and_refuses_clipping(tmp_path):
    spec.loader.exec_module(comparison)
    x = np.array([0.25, -0.25, 0.00001], dtype=np.float32)
    path = tmp_path / 'play.wav'
    comparison.save_playable(path, x, 24000)
    y, _ = sf.read(path, dtype='float32')
    assert np.max(np.abs(x - y)) <= 1 / 32768
    assert y[0] == x[0] and y[1] == x[1]
    with pytest.raises(ValueError):
        comparison.save_playable(tmp_path / 'clipped.wav', np.array([1.1], dtype=np.float32), 24000)
    with pytest.raises(FileExistsError):
        comparison.save_playable(path, x, 24000)
