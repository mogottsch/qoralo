import json
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def test_blocked_after_shared_revision_matches_schema():
    result = json.loads((ROOT / "results/pocket-preview.json").read_text(encoding="utf-8"))
    result_schema = json.loads((ROOT / "schemas/preview-result.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(result, result_schema)
    assert result["status"] == "blocked"
    assert result["protocol"]["protocol_version"] == 2
    assert result["raw"]["duration_seconds"] < 15.0
    assert result["provenance"]["determinism"]["repeated_sha256_identical"] is True
    assert result["forbidden_transformations_used"] == []
    assert "normalized" not in result


def test_blocked_result_retains_complete_measurement_evidence():
    result = json.loads((ROOT / "results/pocket-preview.json").read_text(encoding="utf-8"))
    raw = result["raw"]
    assert raw["sample_count"] == 332160
    assert raw["byte_count"] == raw["sample_count"] * 4
    assert raw["duration_seconds"] == raw["sample_count"] / raw["sample_rate_hz"]
    assert raw["chunk_count"] == len(raw["chunk_manifest"])
    assert sum(chunk["bytes"] for chunk in raw["chunk_manifest"]) == raw["byte_count"]
    assert set(raw["statistics"]) == {
        "integrated_loudness_lufs",
        "peak",
        "peak_dbfs",
        "rms",
        "rms_dbfs",
    }
    assert result["timing"]["api_first_output_seconds"] <= result["timing"]["generation_wall_seconds"]
    assert result["timing"]["first_audible_output_seconds"] is not None
    assert result["memory"]["peak_process_tree_rss_bytes"] >= result["memory"]["baseline_rss_bytes"]
    assert result["provenance"]["download_bytes_during_generation"] == 0
    assert result["provenance"]["anomalies"]


def test_generation_uses_one_atomic_policy_grant():
    wrapper = (HERE / "generate_preview.sh").read_text(encoding="utf-8")
    generator = (HERE / "generate_preview.py").read_text(encoding="utf-8")
    assert wrapper.count("with-resources.sh") == 1
    assert "--kind generation-pocket" in wrapper
    assert "PREVIEW_RESOURCE_GRANT_KIND=generation-pocket" in wrapper
    assert "generation-realtime" not in wrapper
    assert "ResourceGrant(" not in generator
    assert "generation-pocket" in generator


def test_fair_voice_and_forbidden_transformations_are_explicit():
    result = json.loads((ROOT / "results/pocket-preview.json").read_text(encoding="utf-8"))
    assert result["voice"]["name"] == "alba"
    assert result["voice"]["cloning_performed"] is False
    assert result["provenance"]["persistent_voice_states"]["exercised_count"] == 1
    assert result["forbidden_transformations_used"] == []
    assert "one permitted shared punctuation revision" in result["blocker"]
