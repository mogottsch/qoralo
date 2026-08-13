import hashlib
import json
import subprocess
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[3]
EXP = ROOT / "experiments/0008-sherpa-onnx-android-tts-benchmark"
OLD = ROOT / "experiments/0007-mobile-podcast-preview-bakeoff"
SHA = "350c8d3d57525e65085b1d7c5ec733985c5467797cf50508b5e2a4eee313471f"


def load(path):
    return json.loads(path.read_text())


def test_transcript_is_exact_frozen_copy():
    old = (OLD / "protocol/transcript.txt").read_bytes()
    new = (EXP / "protocol/transcript.txt").read_bytes()
    assert new == old
    assert len(new) == 230 and not new.endswith(b"\n")
    assert hashlib.sha256(new).hexdigest() == SHA


def test_protocol_and_candidate_manifests_validate():
    for data_name, schema_name in (("benchmark-protocol.json", "protocol.schema.json"), ("candidates.json", "candidates.schema.json")):
        jsonschema.validate(load(EXP / "protocol" / data_name), load(EXP / "schemas" / schema_name))


def test_fixed_order_voice_and_thermal_contract():
    protocol = load(EXP / "protocol/benchmark-protocol.json")
    candidates = load(EXP / "protocol/candidates.json")
    assert protocol["candidate_order"] == ["pocket", "kokoro", "supertonic_3"]
    pocket = candidates["candidates"][0]
    assert {"requested_voice", "actual_reference", "actual_reference_sha256", "voice_match"} <= pocket.keys()
    assert pocket["requested_voice"] == "Alba"
    assert protocol["runs"]["canonical"] == {"cold_count": 1, "minimum_warm_count": 3, "threads": 1}
    assert protocol["runs"]["two_thread_follow_up"]["runs"]["threads"] == 2
    assert "> 1.0" in protocol["runs"]["two_thread_follow_up"]["trigger"]
    assert protocol["thermal"]["poll_interval_seconds"] == 60
    assert protocol["thermal"]["maximum_wait_seconds"] == 1200
    assert protocol["thermal"]["required_android_status"] == "NONE"
    assert protocol["thermal"]["maximum_battery_temperature_c"] == 35.0
    assert protocol["thermal"]["maximum_above_campaign_baseline_c"] == 1.0


def observation(value=None, reason=None):
    return {"availability": "measured", "value": value, "reason": None, "source": "observed"} if value is not None else {"availability": "unavailable", "value": None, "reason": reason, "source": "observed"}


def result(outcome="blocked"):
    missing = observation(reason="not run: provenance block")
    return {"schema_version": 1, "experiment": "0008", "candidate_id": "pocket", "outcome": outcome, "outcome_reason": "voice provenance unavailable", "provider": "cpu", "threads": 1, "transcript_sha256": SHA, "voice": {"requested_voice": "Alba", "actual_reference": None, "actual_reference_sha256": None, "voice_match": None}, "metrics": {key: missing for key in ("load_wall_seconds", "warm_median_rtf", "boundary_pss_bytes", "boundary_rss_bytes", "vm_hwm_bytes", "sampled_peak_pss_bytes", "sampled_peak_rss_bytes")}, "runs": [], "evidence": [], "listening": "not_performed"}


def test_schema_covers_success_and_all_negative_outcomes_without_estimates():
    schema = load(EXP / "schemas/result.schema.json")
    successful = result("success")
    successful["outcome_reason"] = "completed canonical campaign"
    successful["voice"] = {"requested_voice": "Alba", "actual_reference": "test_wavs/bria.wav", "actual_reference_sha256": "a" * 64, "voice_match": False}
    successful["metrics"] = {key: observation(1.0) for key in successful["metrics"]}
    run = {"kind": "warm", "synthesis_wall_seconds": observation(1.0), "sample_count": observation(24000), "sample_rate_hz": observation(24000), "audio_duration_seconds": observation(1.0), "rtf": observation(1.0), "first_non_empty_callback_seconds": observation(0.1), "wav_sha256": "b" * 64, "audio_validation": "valid"}
    successful["runs"] = [{**run, "kind": "cold"}, run, run, run]
    jsonschema.validate(successful, schema)
    for outcome in ("partial_success", "blocked", "timeout", "native_crash", "oom", "invalid_audio", "failure"):
        jsonschema.validate(result(outcome), schema)
    bad = result()
    bad["metrics"]["load_wall_seconds"] = {"availability": "unavailable", "value": 1.2, "reason": "estimated", "source": "estimated"}
    with __import__("pytest").raises(jsonschema.ValidationError):
        jsonschema.validate(bad, schema)


def test_retired_candidates_are_not_pending_follow_up():
    report = load(ROOT / "docs/candidate-decision-report.json")
    retired = {"vibevoice_realtime_0_5b", "inflect_nano_v1", "kitten_tts_mini_80m_v0_8"}
    assert set(report["candidate_status"]["historical_only"]) == retired
    assert not retired.intersection(report["candidate_status"]["selected_pending_experiment_0008_device_measurement"])
    for key in ("realtime_0_5b", "inflect_nano_v1", "kitten_tts_mini_0_8"):
        assert report["android_measurements"][key]["status"] == "historical_only"


def test_experiment_0007_tracked_evidence_tree_is_unchanged():
    names = subprocess.check_output(["git", "ls-files", "experiments/0007-mobile-podcast-preview-bakeoff"], cwd=ROOT, text=True).splitlines()
    digest = hashlib.sha256()
    for name in names:
        digest.update(name.encode() + b"\0")
        digest.update((ROOT / name).read_bytes())
    assert len(names) == 114
    assert digest.hexdigest() == "c37e0a4a4bd95ddeda3ddf4407dde520abcb1e6a5f9615891cc4dbae545fa216"
