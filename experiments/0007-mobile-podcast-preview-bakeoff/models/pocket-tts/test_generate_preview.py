import json
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def test_blocked_short_result_and_revision_request_match_schemas():
    result = json.loads((ROOT / "results/pocket-preview.json").read_text(encoding="utf-8"))
    result_schema = json.loads((ROOT / "schemas/preview-result.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(result, result_schema)
    request = json.loads((ROOT / "results/pocket-protocol-revision-request.json").read_text(encoding="utf-8"))
    request_schema = json.loads((ROOT / "schemas/protocol-revision-request.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(request, request_schema)
    assert result["status"] == "blocked"
    assert result["raw"]["duration_seconds"] == request["raw_duration_seconds"] < 15.0
    assert "normalized" not in result


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
    request = json.loads((ROOT / "results/pocket-protocol-revision-request.json").read_text(encoding="utf-8"))
    assert result["voice"]["name"] == "alba"
    assert result["voice"]["cloning_performed"] is False
    assert result["provenance"]["persistent_voice_states"]["exercised_count"] == 1
    assert request["forbidden_methods_not_used"] == ["silence-padding", "looping", "time-stretching"]
    assert request["worker_did_not_edit_protocol"] is True
