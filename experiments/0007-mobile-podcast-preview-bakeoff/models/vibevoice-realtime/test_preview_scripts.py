import ast
from pathlib import Path

HERE = Path(__file__).resolve().parent


def test_generation_is_gated_and_preserves_streaming_chunks():
    text = (HERE / "generate_preview.py").read_text(encoding="utf-8")
    ast.parse(text)
    assert 'VIBEVOICE_PREVIEW_GATE") != "task-6:generation-realtime"' in text
    assert 'chunk-{index:04d}.npy' in text
    assert '.open("xb")' in text
    assert 'artifacts/raw/realtime/v2/capture.json' in text
    assert '350c8d3d57525e65085b1d7c5ec733985c5467797cf50508b5e2a4eee313471f' in text
    wrapper = (HERE / "generate-preview.sh").read_text(encoding="utf-8")
    assert "--task task-6 --kind generation-realtime" in wrapper


def test_finalizer_refuses_overwrite_and_checks_raw_hash_after_derivation():
    text = (HERE / "finalize_preview.py").read_text(encoding="utf-8")
    ast.parse(text)
    assert "refusing to overwrite existing evidence" in text
    assert "raw_hash_after != raw_hash_before" in text
    assert '"sample_count": 360_000' in text
    assert '"output_format": "WAV PCM_S16LE"' in text
    assert 'artifacts/normalized/realtime/v2' in text
    assert "Host-preview-only" in text
