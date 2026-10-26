"""Independent decoder checks use synthetic fixtures, not generated comparison data."""
import hashlib
import importlib.util
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

SPEC = importlib.util.spec_from_file_location('verify', Path(__file__).with_name('verify.py'))


def test_ffmpeg_checks_native_frames_and_rejects_changed_hash(tmp_path):
    module = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(module)
    path = tmp_path / 'native.wav'
    x = np.array([0.0, 0.125, -0.375, 0.01], dtype=np.float32)
    sf.write(path, x, 24000, subtype='FLOAT')
    expected = {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'frames': 4,
                'sample_rate': 24000, 'channels': 1, 'peak': 0.375,
                'pcm_f32le_sha256': hashlib.sha256(x.astype('<f4').tobytes()).hexdigest()}
    report, pcm = module.inspect_wav(path, expected, 'pcm_f32le')
    assert report['finite'] and report['frames'] == 4
    assert np.array_equal(x, pcm)
    with pytest.raises(AssertionError, match='SHA256'):
        module.inspect_wav(path, dict(expected, sha256='0' * 64), 'pcm_f32le')
    with pytest.raises(AssertionError, match='frames'):
        module.inspect_wav(path, dict(expected, frames=5), 'pcm_f32le')
