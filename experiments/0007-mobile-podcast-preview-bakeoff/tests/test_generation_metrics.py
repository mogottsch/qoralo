import json
import sys
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from generation_metrics import (
    AUDIBLE_THRESHOLD_RMS,
    GenerationTimer,
    ProcessTreeRssSampler,
    RSS_SAMPLE_INTERVAL_MS,
    first_audible_sample,
    raw_duration_rtf,
    result_is_publishable,
)


class Clock:
    def __init__(self, *values):
        self.values = iter(values)

    def __call__(self):
        return next(self.values)


def test_timer_is_monotonic_and_rtf_uses_raw_duration():
    timer = GenerationTimer(Clock(100.0, 100.5, 104.0)).start()
    timer.mark_api_output([0.0] * 240 + [0.1] * 240, 24000)
    timing = timer.finish(20.0)
    assert timing["clock"] == "CLOCK_MONOTONIC"
    assert timing["api_first_output_seconds"] == 0.5
    assert timing["first_audible_output_seconds"] == pytest.approx(0.51)
    assert timing["generation_wall_seconds"] == 4.0
    assert timing["rtf"] == 0.2
    assert timing["rtf_denominator"] == "raw_native_audio_duration_seconds"
    assert raw_duration_rtf(4.0, 15.0) != timing["rtf"]


def test_unavailable_timings_require_null_plus_reason():
    with pytest.raises(ValueError, match="non-empty.*reason"):
        GenerationTimer(Clock(1.0, 2.0)).start().finish(1.0)
    result = GenerationTimer(Clock(1.0, 2.0)).start().finish(
        1.0,
        api_first_output_unavailable_reason="API exposes no payload callback",
        first_audible_output_unavailable_reason="No decodable audio payload was returned",
    )
    assert result["api_first_output_seconds"] is None
    assert result["first_audible_output_seconds"] is None
    assert result["api_first_output_unavailable_reason"]
    assert result["first_audible_output_unavailable_reason"]


def test_monotonic_clock_regression_fails_closed():
    timer = GenerationTimer(Clock(2.0, 1.0)).start()
    with pytest.raises(RuntimeError, match="backwards"):
        timer.finish(1.0)


def test_audible_detection_uses_complete_nonoverlapping_ten_ms_frames():
    below = AUDIBLE_THRESHOLD_RMS * 0.99
    above = AUDIBLE_THRESHOLD_RMS * 1.01
    samples = [below] * 240 + [above] * 240
    assert first_audible_sample(samples, 24000) == 240
    assert first_audible_sample([above] * 239, 24000) is None


def test_rss_sampler_recurses_and_tolerates_process_exit_race():
    children = {10: [11, 12], 11: [13], 12: [], 13: []}

    def rss(pid):
        if pid == 12:
            raise FileNotFoundError("child exited")
        return {10: 100, 11: 20, 13: 5}[pid]

    sampler = ProcessTreeRssSampler(10, rss_reader=rss, children_reader=children.__getitem__)
    assert sampler.sample_now() == 125
    assert sampler.process_race_count == 1
    assert sampler.peak_process_tree_rss_bytes == 125


def test_rss_baseline_peak_and_fixed_interval(monkeypatch):
    import generation_metrics

    class Thread:
        def __init__(self, *args, **kwargs): pass
        def start(self): pass
        def join(self, timeout): pass
        def is_alive(self): return False

    monkeypatch.setattr(generation_metrics.threading, "Thread", Thread)
    values = iter([100, 250, 150])
    sampler = ProcessTreeRssSampler(10, rss_reader=lambda _pid: next(values), children_reader=lambda _pid: [])
    sampler.start_before_model_load()
    sampler.sample_now()
    result = sampler.stop()
    assert result["baseline_rss_bytes"] == 100
    assert result["peak_process_tree_rss_bytes"] == 250
    assert result["sample_interval_ms"] == RSS_SAMPLE_INTERVAL_MS == 20
    with pytest.raises(ValueError, match="fixed"):
        ProcessTreeRssSampler(interval_seconds=0.1)


def test_blocked_or_incomplete_results_never_unlock_publication():
    complete = {
        "status": "accepted",
        "raw": {"duration_seconds": 15.1, "preserved_unchanged": True},
        "normalized": {"sample_count": 360000},
    }
    assert result_is_publishable(complete)
    for change in (
        {"status": "blocked", "blocker": "duration"},
        {"status": "accepted", "blocker": "integrity"},
        {"status": "accepted", "raw": {"duration_seconds": 14.9, "preserved_unchanged": True}},
        {"status": "accepted", "normalized": None},
    ):
        candidate = complete | change
        assert not result_is_publishable(candidate)


def test_old_results_remain_schema_valid_and_blocked_normalized_is_rejected():
    schema = json.loads((ROOT / "schemas" / "preview-result.schema.json").read_text())
    for path in sorted((ROOT / "results").glob("*-preview.json")):
        jsonschema.validate(json.loads(path.read_text()), schema)
    blocked = json.loads((ROOT / "results" / "pocket-preview.json").read_text())
    blocked["normalized"] = {"sample_count": 360000}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(blocked, schema)


def test_new_model_accepted_result_requires_stronger_evidence():
    schema = json.loads((ROOT / "schemas" / "preview-result.schema.json").read_text())
    result = json.loads((ROOT / "results" / "kokoro-preview.json").read_text())
    for model in ("supertonic-3", "inflect-nano-v1", "kitten-tts-mini-0.8"):
        candidate = result | {"model": model}
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(candidate, schema)


def test_historical_review_is_strictly_ranked_without_claiming_new_reviews():
    review = json.loads((ROOT / "results" / "user-listening-review.json").read_text())
    assert review["assessment"]["strict_order"] == ["C", "B", "A"]
    assert review["assessment"]["ranked_models"] == [
        "hexgrad/Kokoro-82M",
        "kyutai-labs/pocket-tts",
        "microsoft/VibeVoice-Realtime-0.5B",
    ]
    assert review["review_scope"]["reviewed_candidates"] == ["A", "B", "C"]
    assert review["review_scope"]["unreviewed_candidates"] == ["D", "E", "F"]
