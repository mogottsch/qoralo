import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EXPERIMENT = ROOT.parents[1]
PINS = json.loads((ROOT / "pins.json").read_text(encoding="utf-8"))


def test_revisions_are_full_and_every_weight_file_is_pinned():
    full = re.compile(r"^[0-9a-f]{40}$")
    assert full.fullmatch(PINS["source"]["revision"])
    for key in ("preferred_revision", "stock_voice_revision", "stock_voice_model_revision"):
        assert full.fullmatch(PINS["weights"][key])
    setup = (ROOT / "setup.sh").read_text(encoding="utf-8")
    assert PINS["source"]["revision"] in setup
    assert "uv sync" in setup and "--frozen --no-dev" in setup
    assert "'numpy==2.5.1'" in setup


def test_protocol_reference_is_frozen_and_no_second_transcript_exists():
    import sys

    sys.path.insert(0, str(EXPERIMENT / "tools"))
    import protocol

    assert PINS["protocol"] == protocol.protocol_reference()
    assert not list(ROOT.glob("*transcript*"))
    assert "../../protocol/transcript.txt" in (ROOT / "README.md").read_text(encoding="utf-8")


def test_stock_voice_never_clones_and_public_fallback_is_explicit():
    assert PINS["voice"] == {
        "name": "alba",
        "kind": "official precomputed stock voice state",
        "language": "english",
        "source_audio_provenance": "kyutai/tts-voices/alba-mackenna/casual.wav",
        "cloning_performed": False,
    }
    assert PINS["weights"]["stock_voice_repository"] == "kyutai/pocket-tts-without-voice-cloning"
    smoke = (ROOT / "smoke_load.py").read_text(encoding="utf-8")
    assert 'get_state_for_audio_prompt(PINS["voice"]["name"])' in smoke
    assert "PREVIEW_RESOURCE_GRANT_KIND" in smoke


def test_smoke_wrapper_uses_atomic_shared_gate():
    wrapper = (ROOT / "smoke_load.sh").read_text(encoding="utf-8")
    assert "tools/with-resources.sh" in wrapper
    assert "--task task-3 --kind smoke-load" in wrapper
    assert wrapper.index("with-resources.sh") < wrapper.index("smoke_load.py")


def test_native_streaming_and_state_capability_are_documented():
    assert PINS["native_output"]["sample_rate_hz"] == 24000
    assert PINS["native_output"]["channels"] == 1
    generation = PINS["generation"]
    for field in ("determinism", "streaming", "persistent_voice_state", "thread_safety"):
        assert generation[field]
