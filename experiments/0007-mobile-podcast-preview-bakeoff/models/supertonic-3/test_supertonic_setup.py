from __future__ import annotations
import importlib.util, json, os, re, sys, types
from pathlib import Path
import pytest

HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parents[1]


def load(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, HERE / path); module = importlib.util.module_from_spec(spec); assert spec.loader; spec.loader.exec_module(module); return module


def test_official_immutable_identity_license_voice_and_native_format():
    pins = json.loads((HERE / "pins.json").read_text())
    assert pins["model"]["repo_id"] == "Supertone/supertonic-3"
    assert re.fullmatch(r"[0-9a-f]{40}", pins["model"]["revision"])
    assert pins["implementation"]["repository"] == "https://github.com/supertone-inc/supertonic-py.git"
    assert pins["implementation"]["version"] == "1.3.1"
    assert re.fullmatch(r"[0-9a-f]{64}", pins["implementation"]["wheel_sha256"])
    assert pins["model"]["license"].startswith("OpenRAIL-M") and pins["implementation"]["license"] == "MIT"
    assert pins["model"]["gated"] is False and pins["model"]["credentials_required"] is False
    assert pins["voice"]["id"] == "M1" and pins["voice"]["personal_or_cloned_input_used"] is False and pins["voice"]["custom_voice_allowed"] is False
    assert pins["native_output"]["sample_rate_hz"] == 44100 and pins["native_output"]["library_tensor"].startswith("numpy float32")


def test_speed_grid_is_finite_exact_default_first_and_precommitted():
    plan = json.loads((HERE / "speed-attempts.json").read_text())
    assert plan["attempts"][0]["argument"] == "omitted"
    assert [x["effective_speed"] for x in plan["attempts"]] == [1.05, 1.0, .95, .9, .85, .8, .75, .7]
    assert plan["direction"] == "descending" and plan["step"] == .05 and plan["endpoint"] == .7
    assert "first" in plan["selection_rule"] and "at least 15.0 seconds" in plan["selection_rule"]


def test_scripts_are_local_cpu_gated_and_reject_credentials():
    setup = (HERE / "setup.sh").read_text(); smoke = (HERE / "smoke_load.py").read_text(); wrapper = (HERE / "generate_preview.sh").read_text(); generator = (HERE / "generate_preview.py").read_text()
    commands = [x.strip() for x in setup.splitlines() if x.strip() and not x.lstrip().startswith("#")]
    assert not any(x.startswith(("sudo ", "apt ", "apt-get ", "pip ")) for x in commands)
    assert "--no-python-downloads" in setup and "uv sync" in setup and "--locked" in setup
    assert "HF_TOKEN" in smoke and 'token=False' in smoke and 'auto_download=False' in smoke
    assert 'value != ["CPUExecutionProvider"]' in smoke and "active_session_providers" in smoke
    assert "tools/with-resources.sh" in wrapper and "--kind full-generation" in wrapper
    assert 'PREVIEW_RESOURCE_GRANT_KIND") != "full-generation"' in generator
    assert "custom_style" not in generator and "get_voice_style(\"M1\")" in generator


def test_frozen_transcript_and_local_pin_validation():
    import hashlib
    assert hashlib.sha256((EXPERIMENT / "protocol/transcript.txt").read_bytes()).hexdigest() == "350c8d3d57525e65085b1d7c5ec733985c5467797cf50508b5e2a4eee313471f"
    load("verify_supertonic_pins", "verify_pins.py").validate()


def test_generation_timer_stops_before_post_api_analysis(monkeypatch, tmp_path):
    generator = load("supertonic_timing_generator", "generate_preview.py")
    generator.ARTIFACT_ROOT = tmp_path
    generator.CAPTURE_ROOT = tmp_path / "captures/generation-api-boundary-v2"
    monkeypatch.setenv("SUPERTONIC_ATTEMPT_GRANT", "1"); monkeypatch.setenv("PREVIEW_RESOURCE_GRANT_KIND", "full-generation")
    monkeypatch.delenv("HF_TOKEN", raising=False); monkeypatch.delenv("HUGGING_FACE_HUB_TOKEN", raising=False)
    fake_smoke = types.ModuleType("smoke_load"); fake_smoke.verify_snapshot = lambda _path: {}
    fake_ort = types.ModuleType("onnxruntime"); fake_ort.get_available_providers = lambda: ["CPUExecutionProvider"]
    events = []
    class FakeTimer:
        api_first_output_seconds = 1.0
        first_audible_output_seconds = None
        def start(self): events.append("start"); return self
        def mark_api_output(self): events.append("api")
        def stop(self): events.append("stop"); return 1.0
        def finish(self, duration, **_kwargs):
            return {"clock": "CLOCK_MONOTONIC", "generation_wall_seconds": 1.0,
                    "api_first_output_seconds": 1.0, "first_audible_output_seconds": self.first_audible_output_seconds,
                    "rtf": 1.0 / duration, "rtf_denominator": "raw_native_audio_duration_seconds"}
    class FakeSession:
        def get_providers(self): return ["CPUExecutionProvider"]
    class FakeTTS:
        def __init__(self, **_kwargs): self.model = types.SimpleNamespace(**{name: FakeSession() for name in ("dp_ort", "text_enc_ort", "vector_est_ort", "vocoder_ort")})
        def get_voice_style(self, _name): return object()
        def synthesize(self, _text, **_kwargs):
            import numpy as np
            return np.zeros((1, 44100 * 15), dtype=np.float32), [15.0]
    fake_sdk = types.ModuleType("supertonic"); fake_sdk.TTS = FakeTTS
    monkeypatch.setitem(sys.modules, "smoke_load", fake_smoke); monkeypatch.setitem(sys.modules, "onnxruntime", fake_ort); monkeypatch.setitem(sys.modules, "supertonic", fake_sdk)
    monkeypatch.setattr(generator, "GenerationTimer", FakeTimer)
    monkeypatch.setattr(generator, "first_audible_offset_seconds", lambda *_args: events.append("audible"))
    metadata = generator.render(0)
    assert events[:4] == ["start", "api", "stop", "audible"]
    assert metadata["measurement_contract"] == "generation-api-boundary-v2"


def test_finalizer_fails_closed_and_analyzes_native_rate(monkeypatch):
    finalizer = load("supertonic_finalizer", "finalize_preview.py")
    manifest = finalizer.protocol.load_protocol()
    monkeypatch.setattr(finalizer.importlib.metadata, "version", lambda name: manifest["implementation"][name])
    versions = finalizer.require_protocol_environment()
    assert versions["numpy"] == "2.5.1" and versions["scipy"] == "1.18.0"
    monkeypatch.setattr(finalizer.importlib.metadata, "version", lambda name: "0.0.0" if name == "numpy" else manifest["implementation"][name])
    with pytest.raises(SystemExit, match="numpy==2.5.1"):
        finalizer.require_protocol_environment()
    import numpy as np
    tone = np.sin(2 * np.pi * 1000 * np.arange(44100) / 44100) * .1
    got = finalizer.statistics(tone, 44100)
    expected_lufs = finalizer.audio_protocol.audio_statistics(finalizer.audio_protocol.resample_mono(tone, 44100))["integrated_loudness_lufs"]
    assert got["integrated_loudness_lufs"] == pytest.approx(expected_lufs)
    assert got["rms"] == pytest.approx(np.sqrt(np.mean(tone ** 2)))


def test_corrected_result_is_schema_valid_protocol_current_and_publishable():
    jsonschema = pytest.importorskip("jsonschema")
    result = json.loads((EXPERIMENT / "results/supertonic-3-preview.json").read_text())
    schema = json.loads((EXPERIMENT / "schemas/preview-result.schema.json").read_text())
    jsonschema.Draft202012Validator(schema).validate(result)
    sys.path.insert(0, str(EXPERIMENT / "tools"))
    import generation_metrics, protocol
    protocol.validate_result_protocol(result)
    assert result["status"] == "accepted" and result["publication_eligible"] is True
    assert result["normalized"]["sample_count"] == 360000
    assert result["provenance"]["environment"]["normalization_numpy"] == "2.5.1"
    assert generation_metrics.result_is_publishable(result)


def test_generator_mock_preserves_default_raw_write_once(monkeypatch, tmp_path):
    generator = load("supertonic_generator", "generate_preview.py")
    generator.ARTIFACT_ROOT = tmp_path
    generator.CAPTURE_ROOT = tmp_path / "captures/generation-api-boundary-v2"
    generator.PINS = generator.PINS | {"model": generator.PINS["model"] | {"files": {}}}
    monkeypatch.setenv("SUPERTONIC_ATTEMPT_GRANT", "1"); monkeypatch.setenv("PREVIEW_RESOURCE_GRANT_KIND", "full-generation")
    monkeypatch.delenv("HF_TOKEN", raising=False); monkeypatch.delenv("HUGGING_FACE_HUB_TOKEN", raising=False)
    fake_smoke = types.ModuleType("smoke_load"); fake_smoke.verify_snapshot = lambda _path: {}
    fake_ort = types.ModuleType("onnxruntime"); fake_ort.get_available_providers = lambda: ["CPUExecutionProvider"]
    calls = {}
    class FakeSession:
        def get_providers(self): return ["CPUExecutionProvider"]
    class FakeTTS:
        def __init__(self, **kwargs):
            calls["init"] = kwargs
            self.model = types.SimpleNamespace(**{name: FakeSession() for name in ("dp_ort", "text_enc_ort", "vector_est_ort", "vocoder_ort")})
        def get_voice_style(self, name): calls["voice"] = name; return object()
        def synthesize(self, text, **kwargs):
            import numpy as np
            calls["kwargs"] = kwargs
            return np.array([[0.0, .25, -.25]], dtype=np.float32), [3 / 44100]
    fake_sdk = types.ModuleType("supertonic"); fake_sdk.TTS = FakeTTS
    monkeypatch.setitem(sys.modules, "smoke_load", fake_smoke); monkeypatch.setitem(sys.modules, "onnxruntime", fake_ort); monkeypatch.setitem(sys.modules, "supertonic", fake_sdk)
    metadata = generator.render(0)
    assert calls["init"] == {"model": "supertonic-3", "model_dir": tmp_path / "snapshot", "auto_download": False}
    assert calls["voice"] == "M1" and "speed" not in calls["kwargs"]
    assert metadata["sample_count"] == 3 and (tmp_path / "captures/generation-api-boundary-v2/attempts/attempt-00/native.f32le").stat().st_size == 12
    with pytest.raises(SystemExit, match="write-once"): generator.render(0)
