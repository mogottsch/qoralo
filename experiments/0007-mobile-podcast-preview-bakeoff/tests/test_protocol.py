import copy
import json
import sys
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import protocol


def test_transcript_is_frozen_and_in_range():
    manifest = protocol.load_protocol()
    assert manifest["transcript_word_count"] == 36
    assert manifest["protocol_version"] == 2
    assert manifest["transcript_sha256"] == "350c8d3d57525e65085b1d7c5ec733985c5467797cf50508b5e2a4eee313471f"


def test_manifest_and_result_schemas_are_valid():
    manifest = protocol.load_protocol()
    schema = json.loads((ROOT / "schemas" / "protocol.schema.json").read_text())
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.validate(manifest, schema)
    for name in ("preview-result.schema.json", "generation-policy.schema.json", "protocol-revision-request.schema.json"):
        jsonschema.Draft202012Validator.check_schema(json.loads((ROOT / "schemas" / name).read_text()))
    policy_schema = json.loads((ROOT / "schemas" / "generation-policy.schema.json").read_text())
    policy = json.loads((ROOT / "protocol" / "model-resource-policy-v1.json").read_text())
    jsonschema.validate(policy, policy_schema)


def test_protocol_v2_and_historical_audio_evidence_are_unchanged():
    manifest = protocol.load_protocol()
    assert protocol.protocol_reference()["protocol_fingerprint"] == "ca0987feca4c9a2e8744d4846d1b3f5da86799862f6f7d8ba7e3563f84245814"
    assert manifest["audio"] == {
        "sample_rate_hz": 24000,
        "channels": 1,
        "sample_format": "PCM_S16LE",
        "sample_count": 360000,
        "duration_seconds": 15.0,
        "mono_conversion": "arithmetic mean of channels in float64 before resampling",
        "resampler": "scipy.signal.resample_poly",
        "resampler_window": ["kaiser", 5.0],
        "resampler_padtype": "constant",
        "resampled_length_rule": "ceil(input_samples * 24000 / input_rate)",
        "zero_crossing_search_samples": 240,
        "zero_crossing_rule": "minimize abs(linear crossing amplitude), then distance from target end, then earliest index; select an exact-length window ending there",
        "fade_samples": 240,
        "fade_shape": "sine-squared inclusive endpoints",
        "integrated_loudness_target_lufs": -20.0,
        "peak_ceiling_dbfs": -1.0,
        "gain_rule": "minimum of loudness-target gain and peak-ceiling gain",
        "dither": "deterministic TPDF at one PCM16 LSB using numpy PCG64 seed 0",
        "short_input": "reject; regenerate only with documented model speed controls, or increment protocol version for any transcript change",
        "forbidden": ["time stretching", "looping", "fabricated speech", "overwriting raw output"],
    }
    expected = {
        "realtime": ("0daa06752efbdd2944ac66e02aa8f86792cf523dbb4846bb4fab9ac8741e28c1", "a010e2e685446cd5904a0b02ad806f04bb5b5c2bfa2bd7f1c002d1691e9d0d41"),
        "pocket": ("47edc30525bfdd70f7859391386a593c754def7c3e4f809a3cdd40eb58caffc1", None),
        "kokoro": ("b6d8d126dae93f3d1f52bebf96d695c48d07c8ddf79a97d429c4687007e57494", "24cdb3b81fff87a1ecc46ff4e6aa740512f3eab2e33f5ae4cbec541b12fed196"),
    }
    for model, hashes in expected.items():
        result = json.loads((ROOT / "results" / f"{model}-preview.json").read_text())
        assert (result["raw"]["sha256"], result.get("normalized", {}).get("sha256")) == hashes


def test_historical_review_is_strictly_ranked_without_reviewing_new_candidates():
    review = json.loads((ROOT / "results" / "user-listening-review.json").read_text())
    assert review["assessment"]["strict_order"] == ["C", "B", "A"]
    assert review["review_scope"]["reviewed_candidates"] == ["A", "B", "C"]
    assert review["review_scope"]["unreviewed_candidates"] == ["D", "E", "F"]
    assert review["candidate_mapping"] == {
        "A": "microsoft/VibeVoice-Realtime-0.5B",
        "B": "kyutai-labs/pocket-tts",
        "C": "hexgrad/Kokoro-82M",
        "D": "Supertone/supertonic-3",
        "E": "owensong/Inflect-Nano-v1",
        "F": "KittenML/kitten-tts-mini-0.8",
    }


def test_transcript_byte_drift_fails_closed(tmp_path):
    manifest = copy.deepcopy(protocol.load_protocol())
    (tmp_path / "transcript.txt").write_text((ROOT / "protocol" / "transcript.txt").read_text() + "!", encoding="utf-8")
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="drift"): protocol.load_protocol(tmp_path / "manifest.json")


def test_generated_artifacts_are_ignored():
    ignore = (ROOT.parents[1] / ".gitignore").read_text(encoding="utf-8")
    assert "artifacts/" in ignore and "*.wav" in ignore


def test_punctuation_change_requires_higher_version():
    previous = protocol.load_protocol()
    changed = copy.deepcopy(previous)
    changed["transcript_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="requires a higher protocol version"):
        protocol.validate_successor(previous, changed)
    changed["protocol_version"] += 1
    protocol.validate_successor(previous, changed)


def test_protocol_revision_invalidates_prior_preview(tmp_path):
    current = protocol.protocol_reference()
    protocol.validate_result_protocol({"protocol": current})
    changed = copy.deepcopy(protocol.load_protocol()); changed["protocol_version"] += 1
    path = tmp_path / "v2.json"
    path.write_text(json.dumps(changed), encoding="utf-8")
    (tmp_path / "transcript.txt").write_bytes((ROOT / "protocol" / "transcript.txt").read_bytes())
    for _model in ("realtime", "pocket", "kokoro"):
        with pytest.raises(ValueError, match="prior preview is invalid"):
            protocol.validate_result_protocol({"protocol": current}, path)
    reset = protocol.revision_invalidation_tasks()
    assert reset == ("task-6", "task-7", "task-8", "task-16", "task-17", "task-18")
    assert "task-9" not in reset


def test_any_normative_change_requires_version_increment():
    previous = protocol.load_protocol()
    changed = copy.deepcopy(previous)
    changed["audio"]["fade_samples"] += 1
    with pytest.raises(ValueError, match="normative protocol change"):
        protocol.validate_successor(previous, changed)
