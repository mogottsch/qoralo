from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import track
import verify_pins


def _load_generator():
    spec = importlib.util.spec_from_file_location("inflect_generate_attempt", ROOT / "generate_attempt.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def test_exact_v1_identity_weights_frontend_and_licenses_are_pinned():
    verify_pins.validate()
    pins = track.PINS
    assert pins["identity"]["repository"] == "owensong/Inflect-Nano-v1"
    assert pins["identity"]["revision"] == "ab0302781cb0cb9969a9a28ce8e1b259539275dd"
    assert pins["artifacts"]["files"][pins["artifacts"]["acoustic_path"]]["sha256"] == "0129f730a25a1e44d1799a1d47166c9a3a5644e58fb84a3b554d5c036827ec89"
    assert pins["artifacts"]["files"][pins["artifacts"]["vocoder_path"]]["sha256"] == "57482bee18ef72c2df0153f44dafd14f1666ce11cd1558e3437272b13fa18d08"
    frontend = [name for name in pins["artifacts"]["files"] if name.startswith("third_party/tiny_tts_frontend/")]
    assert len(frontend) >= 20
    assert pins["licenses"]["model_and_source"]["spdx"] == "Apache-2.0"
    assert pins["licenses"]["vendored_tiny_tts_frontend"]["spdx"] == "Apache-2.0"


@pytest.mark.parametrize("repository", [
    "owensong/Inflect-Nano-v2", "owensong/inflect-nano-v1", "someone/Inflect-Nano-v1", "Inflect-Nano-v1",
])
def test_verifier_rejects_v2_aliases_and_substitutes(monkeypatch, repository):
    changed = copy.deepcopy(track.PINS)
    changed["identity"]["repository"] = repository
    monkeypatch.setattr(verify_pins, "PINS", changed)
    with pytest.raises(ValueError, match="only exact"):
        verify_pins.validate()


def test_default_first_finite_grid_and_first_passing_rule_are_exact():
    plan = track.PLAN
    assert plan["values"] == [1.0, 1.05, 1.1, 1.15, 1.2, 1.25, 1.3, 1.35, 1.4, 1.45, 1.5]
    assert plan["bounds"] == {"minimum": 1.0, "maximum": 1.5}
    assert plan["step"] == 0.05 and plan["direction"] == "ascending"
    assert plan["minimum_accepted_raw_duration_seconds"] == 15.0
    assert "first" in plan["selection_rule"].lower()
    assert plan["fixed_controls"] == {"energy_scale": 1.0, "pitch_scale": 1.0}


def test_fixed_stock_voice_cpu_and_native_output_have_no_cloning_path():
    pins = track.PINS
    assert pins["voice"] == {
        "cloning_performed": False,
        "description": "single English male voice built into the acoustic checkpoint",
        "id": "mark",
        "kind": "fixed stock model voice",
        "reference_audio_allowed": False,
        "selectable_voice_input": False,
        "source_revision": pins["identity"]["revision"],
    }
    assert "--device cpu" in pins["implementation"]["cpu_command"]
    assert pins["native_output"]["sample_rate_hz"] == 24000
    generator = (ROOT / "generate_attempt.py").read_text(encoding="utf-8")
    assert "pitch_scale=1.0, energy_scale=1.0" in generator
    assert "reference" not in " ".join(track.PLAN["fixed_controls"])


def test_mocked_attempt_order_stops_after_first_pass_and_requires_no_skips(tmp_path):
    generator = _load_generator()
    with pytest.raises(RuntimeError, match="cannot skip"):
        generator.validate_attempt_order(tmp_path, 1, False)
    first = track.attempt_directory(tmp_path, 0)
    first.mkdir()
    (first / "attempt.json").write_text(json.dumps({"raw_duration_seconds": 14.9}))
    generator.validate_attempt_order(tmp_path, 1, False)
    second = track.attempt_directory(tmp_path, 1)
    second.mkdir()
    (second / "attempt.json").write_text(json.dumps({"raw_duration_seconds": 15.0}))
    with pytest.raises(RuntimeError, match="prior attempt passed"):
        generator.validate_attempt_order(tmp_path, 2, False)
    generator.validate_attempt_order(tmp_path, 1, True)


def test_attempt_and_repeat_paths_are_unique_and_write_once(tmp_path):
    paths = {track.attempt_directory(tmp_path, index) for index in range(len(track.PLAN["values"]))}
    repeats = {track.attempt_directory(tmp_path, index, repeat=True) for index in range(len(track.PLAN["values"]))}
    assert len(paths) == len(track.PLAN["values"])
    assert paths.isdisjoint(repeats)
    path = track.attempt_directory(tmp_path, 0)
    path.mkdir()
    with pytest.raises(FileExistsError):
        path.mkdir()


def test_smoke_and_generation_are_globally_gated_without_full_transcript_smoke():
    smoke_wrapper = (ROOT / "smoke-load.sh").read_text(encoding="utf-8")
    smoke = (ROOT / "smoke_load.py").read_text(encoding="utf-8")
    generation_wrapper = (ROOT / "generate-attempt.sh").read_text(encoding="utf-8")
    generator = (ROOT / "generate_attempt.py").read_text(encoding="utf-8")
    assert "--kind model-load" in smoke_wrapper
    assert 'PREVIEW_RESOURCE_GRANT_KIND") != "model-load"' in smoke
    assert '"synthesis_performed": False' in smoke
    assert "--kind full-generation" in generation_wrapper
    assert 'PREVIEW_RESOURCE_GRANT_KIND") != "full-generation"' in generator
    assert 'output_dir.mkdir()' in generator and 'wav.open("xb")' in generator


def test_only_shared_frozen_transcript_is_consumed():
    assert not list(ROOT.glob("*transcript*"))
    assert track.PINS["protocol"]["transcript_sha256"] == "350c8d3d57525e65085b1d7c5ec733985c5467797cf50508b5e2a4eee313471f"
    assert "frozen_transcript()" in (ROOT / "generate_attempt.py").read_text(encoding="utf-8")
